"""
generate_reasoning.py

Fills in `reasoning_steps` and `reasoning_answer` for each ProofWriter example
in proofwriter_dev.json, using MATP's own reasoning-generation prompt template
(ProcessAgent/constant/prompt/reasoning_generation.txt) so the generated
reasoning chains match the style MATP's paper evaluated against.

This step is separate from and does not affect MATP's own NL2FOL formalization
step later in the pipeline (ProcessAgent/actions/nl2fol.py) - that always runs
with MATP's own fixed prompt regardless of how the reasoning chain was produced.

Usage:
    python generate_reasoning.py \
        --input workspace/dataset_v_last/proofwriter_dev.json \
        --output proofwriter_dev_filled.json \
        --prompt-template ProcessAgent/constant/prompt/reasoning_generation.txt \
        --limit 5          # optional, for a cheap test run first

Requires boto3 configured with credentials that can call Bedrock
(same AWS credentials already used elsewhere in this environment).
Set the model ID/ARN via --model, or the MATP_BEDROCK_MODEL_ID env var.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import boto3


# ---------------------------------------------------------------------------
# Bedrock calling — Anthropic Messages API via bedrock-runtime, matching the
# same request shape MetaGPT's AnthropicProvider uses for Bedrock.
# ---------------------------------------------------------------------------

def build_bedrock_client(region_name: str):
    return boto3.client("bedrock-runtime", region_name=region_name)


_IS_LLAMA_MODEL = None  # set lazily per model_id, see below

def call_claude_bedrock(
    client,
    model_id: str,
    prompt: str,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    max_retries: int = 3,
) -> str:
    # Converse API — provider-agnostic (Claude/Qwen/Llama all go through the
    # same shape), replacing the old Anthropic-only invoke_model body.
    is_llama = "llama" in model_id.lower()
    effective_max_tokens = min(max_tokens, 8192) if is_llama else max_tokens

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": effective_max_tokens, "temperature": temperature},
            )
            content = response["output"]["message"]["content"]
            for block in content:
                if "text" in block:
                    return block["text"]
            raise RuntimeError(f"No text block in Converse response: {content}")
        except Exception as e:  # noqa: BLE001 - want to retry on any transient error
            last_err = e
            wait = 2 ** attempt
            print(f"  [retry {attempt}/{max_retries}] Bedrock call failed: {e} — waiting {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"Bedrock call failed after {max_retries} attempts: {last_err}")


# ---------------------------------------------------------------------------
# Prompt formatting — mirrors MATP's own reasoning_generation.txt template
# ---------------------------------------------------------------------------

def format_prompt(template: str, premises: list[str], conclusion: str) -> str:
    premises_str = "\n".join(premises)
    return template.format(premises=premises_str, conclusion=conclusion)


# ---------------------------------------------------------------------------
# Response parsing — pulls out Thoughts (-> reasoning_steps) and
# Answer (-> reasoning_answer, using MATP's label convention: True -> 1, False -> -1)
# ---------------------------------------------------------------------------

_ANSWER_RE = re.compile(r"Answer:\s*\(?([AB])\)?", re.IGNORECASE)


def parse_reasoning_response(text: str) -> tuple[list[str], int]:
    """
    Returns (reasoning_steps, reasoning_answer).
    reasoning_answer: 1 for True, -1 for False.
    Raises ValueError if the response doesn't match the expected format,
    so the caller can retry or flag the example rather than silently
    saving garbage.
    """
    if "Thoughts:" not in text or "Answer:" not in text:
        raise ValueError(f"Response missing Thoughts/Answer sections: {text[:200]!r}")

    thoughts_part, answer_part = text.split("Answer:", 1)
    thoughts_part = thoughts_part.split("Thoughts:", 1)[1]

    reasoning_steps = [
        line.strip()
        for line in thoughts_part.strip().splitlines()
        if line.strip()
    ]

    match = _ANSWER_RE.search("Answer:" + answer_part)
    if not match:
        raise ValueError(f"Could not parse Answer field: {answer_part[:200]!r}")

    letter = match.group(1).upper()
    reasoning_answer = 1 if letter == "A" else -1

    return reasoning_steps, reasoning_answer


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate reasoning_steps/reasoning_answer for ProofWriter examples.")
    parser.add_argument("--input", type=Path, required=True, help="Path to proofwriter_dev.json")
    parser.add_argument("--output", type=Path, required=True, help="Path to write the filled-in JSON")
    parser.add_argument("--prompt-template", type=Path, required=True, help="Path to reasoning_generation.txt")
    parser.add_argument("--model", type=str, default=os.environ.get("MATP_BEDROCK_MODEL_ID"),
                         help="Bedrock model ID or inference-profile ARN. "
                              "Defaults to MATP_BEDROCK_MODEL_ID env var.")
    parser.add_argument("--region", type=str, default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N examples (for a cheap test run).")
    parser.add_argument("--max-tokens", type=int, default=2048)
    args = parser.parse_args()

    if not args.model:
        print("ERROR: no model ID given. Pass --model or set MATP_BEDROCK_MODEL_ID.", file=sys.stderr)
        sys.exit(1)

    template = args.prompt_template.read_text()
    examples = json.loads(args.input.read_text())

    if args.limit:
        examples = examples[: args.limit]

    client = build_bedrock_client(args.region)

    filled = 0
    failed = []

    for i, ex in enumerate(examples):
        idx = ex.get("idx", f"example_{i}")
        premises = ex["premises"]
        conclusion = ex["question"][0] if isinstance(ex["question"], list) else ex["question"]

        prompt = format_prompt(template, premises, conclusion)

        print(f"[{i + 1}/{len(examples)}] {idx}")
        try:
            raw_response = call_claude_bedrock(
                client, args.model, prompt, max_tokens=args.max_tokens,
            )
            reasoning_steps, reasoning_answer = parse_reasoning_response(raw_response)
            ex["reasoning_steps"] = reasoning_steps
            ex["reasoning_answer"] = reasoning_answer
            filled += 1
        except Exception as e:  # noqa: BLE001
            print(f"  FAILED: {e}")
            failed.append(idx)
            # Leave reasoning_steps/reasoning_answer as-is (empty/placeholder)
            # so this example is easy to spot and re-run later.

    args.output.write_text(json.dumps(examples, indent=2))

    print(f"\nDone. {filled}/{len(examples)} filled successfully.")
    if failed:
        print(f"{len(failed)} example(s) failed and were left unfilled:")
        for idx in failed:
            print(f"  - {idx}")
    print(f"Output written to {args.output}")


if __name__ == "__main__":
    main()