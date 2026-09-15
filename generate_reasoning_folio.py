"""
generate_reasoning_folio.py -- FOLIO-specific stage 1 for MATP.

generate_reasoning.py (the existing ProofWriter version) is hardcoded to a
BINARY True/False (A/B) answer and reads ProofWriter's own field names
(premises, question). FOLIO genuinely has a third label (Uncertain), and
uses different native field names (premise, conclusion, label as a string)
-- neither of those match what generate_reasoning.py assumes, so this is a
separate script rather than a flag on the existing one.

What this does:
  1. Reads a FOLIO NL dataset: list of {index, premise: [...], conclusion,
     label: "True"|"False"|"Uncertain"} (matches folio_train_groundtruth_
     dataset_2.json / folio_validation_<model>_bedrock_fol.json already in
     this project's separate FOLIO_work repo).
  2. Remaps to MATP's expected schema (see MATP.py: task["premises"],
     task["question"], task["idx"] -- "question" is the literal key MATP.py
     reads even for the conclusion field, on every dataset it supports).
  3. Converts the gold label string to the numeric convention MATP's own
     ProcessAgent/actions/vampire_run.py already expects: 1=True, -1=False,
     0=Uncertain (confirmed against vampire_run.py's own gt_label handling
     and the existing proofwriter_dev_filled.json's {1, -1} convention).
  4. Prompts the model for a genuine 3-way verdict (Answer: A/B/C for
     True/False/Uncertain), unlike generate_reasoning.py's A/B-only regex.
  5. Writes reasoning_steps/reasoning_answer into the same record shape
     MATP.py consumes directly with --dataset_name folio.

Reuses call_claude_bedrock from generate_reasoning.py unchanged (already
migrated to the Converse API earlier this project) rather than duplicating
the Bedrock-call logic.

Usage:
    python generate_reasoning_folio.py \\
        --input folio_train_groundtruth_dataset_2.json \\
        --output folio_reasoning_qwen.json \\
        --model qwen.qwen3-next-80b-a3b \\
        --region us-east-1 \\
        --limit 20
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generate_reasoning import call_claude_bedrock, build_bedrock_client


DEFAULT_TEMPLATE = """You are solving a FOLIO-style first-order logic reasoning problem.

Given the premises and conclusion below, reason step by step, then state whether the
conclusion is True, False, or Uncertain given the premises (Uncertain means the premises
do not determine the conclusion either way -- it could be true or false).

PREMISES:
{premises}

CONCLUSION:
{conclusion}

Respond in EXACTLY this format:
Thoughts:
<one reasoning step per line>
Answer: (A) True / (B) False / (C) Uncertain -- give just the letter, e.g. "Answer: A"
"""

_ANSWER_RE = re.compile(r"Answer:\s*\(?([ABC])\)?", re.IGNORECASE)

LABEL_TO_NUMERIC = {"true": 1, "false": -1, "uncertain": 0}
NUMERIC_TO_LETTER = {1: "A", -1: "B", 0: "C"}
LETTER_TO_NUMERIC = {"A": 1, "B": -1, "C": 0}


def format_prompt(template: str, premises: list[str], conclusion: str) -> str:
    premises_text = "\n".join(f"({i+1}) {p}" for i, p in enumerate(premises))
    return template.format(premises=premises_text, conclusion=conclusion)


def parse_reasoning_response(text: str) -> tuple[list[str], int]:
    """
    Returns (reasoning_steps, reasoning_answer).
    reasoning_answer: 1=True, -1=False, 0=Uncertain (matches vampire_run.py's
    own gt_label convention, extended from generate_reasoning.py's binary-only
    version to genuinely support the third value).
    """
    if "Thoughts:" not in text or "Answer:" not in text:
        raise ValueError(f"Response missing Thoughts/Answer sections: {text[:200]!r}")

    thoughts_part, answer_part = text.split("Answer:", 1)
    thoughts_part = thoughts_part.split("Thoughts:", 1)[1]

    reasoning_steps = [line.strip() for line in thoughts_part.strip().splitlines() if line.strip()]

    match = _ANSWER_RE.search("Answer:" + answer_part)
    if not match:
        raise ValueError(f"Could not parse Answer field: {answer_part[:200]!r}")

    letter = match.group(1).upper()
    reasoning_answer = LETTER_TO_NUMERIC[letter]

    return reasoning_steps, reasoning_answer


def main():
    parser = argparse.ArgumentParser(description="Generate reasoning_steps/reasoning_answer for FOLIO examples (3-way).")
    parser.add_argument("--input", type=Path, required=True, help="FOLIO NL dataset (premise/conclusion/label)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt-template", type=Path, default=None,
                         help="Optional override; defaults to the built-in 3-way template.")
    parser.add_argument("--model", type=str, default=os.environ.get("MATP_BEDROCK_MODEL_ID"),
                         help="Bedrock model ID or inference-profile ARN. Defaults to MATP_BEDROCK_MODEL_ID env var.")
    parser.add_argument("--region", type=str, default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=2048)
    args = parser.parse_args()

    if not args.model:
        print("ERROR: no model ID given. Pass --model or set MATP_BEDROCK_MODEL_ID.", file=sys.stderr)
        sys.exit(1)

    template = args.prompt_template.read_text() if args.prompt_template else DEFAULT_TEMPLATE
    raw_examples = json.loads(args.input.read_text())

    if args.limit:
        raw_examples = raw_examples[: args.limit]

    client = build_bedrock_client(args.region)

    filled = 0
    failed = []
    output_examples = []

    for i, ex in enumerate(raw_examples):
        idx = str(ex.get("index", f"example_{i}"))
        premises = ex.get("premise", ex.get("premises", []))
        conclusion = ex.get("conclusion", "")
        raw_label = str(ex.get("label", "")).strip().lower()
        gold_numeric = LABEL_TO_NUMERIC.get(raw_label)

        if gold_numeric is None:
            print(f"[{i+1}/{len(raw_examples)}] {idx}  SKIPPED: unrecognized label {ex.get('label')!r}")
            continue

        # Remap to MATP's expected schema -- "question" is the literal key
        # MATP.py reads for the conclusion field on every dataset it supports.
        out_record = {
            "idx": idx,
            "premises": premises,
            "question": [conclusion],
            "label": gold_numeric,
        }

        prompt = format_prompt(template, premises, conclusion)

        print(f"[{i + 1}/{len(raw_examples)}] {idx}")
        try:
            raw_response = call_claude_bedrock(client, args.model, prompt, max_tokens=args.max_tokens)
            reasoning_steps, reasoning_answer = parse_reasoning_response(raw_response)
            out_record["reasoning_steps"] = reasoning_steps
            out_record["reasoning_answer"] = reasoning_answer
            filled += 1
        except Exception as e:  # noqa: BLE001
            print(f"  FAILED: {e}")
            failed.append(idx)
            out_record["reasoning_steps"] = []
            out_record["reasoning_answer"] = None

        output_examples.append(out_record)

    args.output.write_text(json.dumps(output_examples, indent=2), encoding="utf-8")

    print(f"\nDone. {filled}/{len(output_examples)} filled successfully.")
    if failed:
        print(f"Failed ({len(failed)}): {failed}")
    print(f"Output written to {args.output}")


if __name__ == "__main__":
    main()