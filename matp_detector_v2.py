"""
matp_detector_v2.py

Comprehensive post-hoc error detection over MATP's REAL intermediate pipeline
output, per completed task folder — not a reparse of the final flattened
results JSON like the original matp_error_adapter.py.

Reads, per task, from workspace/output/{PROJECT_NAME}/{TASK_NAME}/:
  - task_info.json   : real premise:_fol / steps:_fol / conclusion:_fol
                        (ref/fol/tptp triples, produced by FOL2Tptp) plus
                        original premises/filter_reasoning_steps
  - check_res.json   : Vampire's real per-step verdicts (AnswerCorrect,
                        step_correctness_label, has_valid_proof_path_label,
                        cate)

WHY THIS IS BETTER THAN THE ORIGINAL ADAPTER:
  - Uses the real ref/fol/tptp triples FOL2Tptp already produced, instead of
    regex-reparsing a flattened results blob.
  - cate == "Error" (VAMPIRE_ANSWER_ERROR) now correctly buckets as I-A
    (Vampire couldn't parse the TPTP at all — a real syntax/malformation
    failure), not III-A-ii. The original adapter conflated the two.
  - II-A-ii is now a REAL signal: leftover Unicode logic symbols
    (∧ ∨ ¬ → ↔ ≠ ∀ ∃ ⊕) in the tptp field mean convert_to_tptp failed to
    fully convert that statement — a genuine grounding/conversion defect,
    not a guessed heuristic. The old naive argument-swap detector (which
    produced ~227 false positives on legitimate bidirectional relational
    facts) has been dropped entirely.
  - II-B-ii checks real premise/step counts against what FOL2Tptp actually
    carried through, instead of crude keyword matching against a flattened
    ref string.

NOT PORTED (still doesn't apply to this domain):
  - II-B-i-f / II-B-i-nf (forgetting/stale facts) — MATP is single-shot.
  - III-A-i (policy violation) — no policy domain here.

Usage:
    python matp_detector_v2.py \
        --project-dir workspace/output/proofwriter_dev_filled \
        --output errors_matp_v2.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path


# ---------------------------------------------------------------------------
# PipelineError / ErrorLog — schema-compatible with your own errors.py
# ---------------------------------------------------------------------------

ERROR_TYPE_TO_CATEGORY = {
    "I-A": "I", "I-B-i": "I", "I-B-ii": "I",
    "II-A-i": "II", "II-A-ii": "II", "II-B-i": "II", "II-B-ii": "II",
    "III-A-ii": "III",
}


@dataclass
class PipelineError:
    layer: int
    error_type: str
    detail: str
    turn: int = -1
    symbol: str = ""
    upstream_confidence: float = 1.0

    @property
    def category(self) -> str:
        return ERROR_TYPE_TO_CATEGORY.get(self.error_type, "I")

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "category": self.category,
            "error_type": self.error_type,
            "detail": self.detail,
            "turn": self.turn,
            "symbol": self.symbol,
            "upstream_confidence": round(self.upstream_confidence, 4),
        }


@dataclass
class ErrorLog:
    _errors: list = field(default_factory=list)

    def add(self, error: PipelineError) -> None:
        self._errors.append(error)

    def errors(self) -> list:
        return list(self._errors)

    def count(self) -> int:
        return len(self._errors)

    def by_error_type(self) -> dict:
        result = {}
        for e in self._errors:
            result[e.error_type] = result.get(e.error_type, 0) + 1
        return result

    def merge(self, other: "ErrorLog") -> None:
        for e in other.errors():
            self.add(e)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump([e.to_dict() for e in self._errors], f, indent=2)
        print(f"Error log saved to {path} ({self.count()} errors)")

    def __repr__(self) -> str:
        return f"ErrorLog(total={self.count()}, by_type={self.by_error_type()})"


# ---------------------------------------------------------------------------
# FOL atom extraction (still needed for I-A/I-B-i/I-B-ii/II-A-i checks)
# ---------------------------------------------------------------------------

_ATOM_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^()]*)\)')
_NOT_PREDICATES = {"forall", "exists"}
_UNICODE_LOGIC_SYMBOLS = "∧∨¬→↔≠∀∃⊕"


def extract_atoms(fol_str: str) -> list[tuple[str, list[str]]]:
    atoms = []
    for match in _ATOM_RE.finditer(fol_str):
        pred = match.group(1).strip()
        if pred.lower() in _NOT_PREDICATES:
            continue
        args_str = match.group(2).strip()
        args = [a.strip() for a in args_str.split(",")] if args_str else []
        atoms.append((pred, args))
    return atoms


def _tokens(name: str) -> set:
    return set(name.lower().replace("-", "_").split("_"))


def _similarity_score(a: str, b: str) -> float:
    tokens_a, tokens_b = _tokens(a), _tokens(b)
    if not tokens_a and not tokens_b:
        return 1.0
    token_overlap = len(tokens_a & tokens_b) / len(tokens_a | tokens_b) if (tokens_a | tokens_b) else 0.0
    dist = (1 - SequenceMatcher(None, a, b).ratio()) * max(len(a), len(b))
    max_len = max(len(a), len(b), 1)
    char_sim = 1.0 - dist / max_len
    return 0.65 * token_overlap + 0.35 * char_sim


_MULTIPLICITY_THRESHOLD = 0.55


# ---------------------------------------------------------------------------
# Detectors — operate on real task_info.json / check_res.json structures
# ---------------------------------------------------------------------------

def build_premise_bank(premise_fol: list[dict]) -> dict[str, set]:
    bank: dict[str, set] = {}
    for entry in premise_fol:
        for pred, args in extract_atoms(entry.get("fol", "")):
            bank.setdefault(pred, set()).add(len(args))
    return bank


def detect_ia_malformed(all_entries: list[dict], idx: str, log: ErrorLog) -> None:
    """I-A: invalid predicate names, inconsistent arity for the same name."""
    arity_by_pred: dict[str, set] = {}
    for entry in all_entries:
        for pred, args in extract_atoms(entry.get("fol", "")):
            if not re.match(r'^[a-z][a-z0-9_]*$', pred):
                log.add(PipelineError(
                    layer=1, error_type="I-A",
                    detail=f"[{idx}] Predicate '{pred}' is not valid snake_case",
                    symbol=pred,
                ))
            arity_by_pred.setdefault(pred, set()).add(len(args))

    for pred, arities in arity_by_pred.items():
        if len(arities) > 1:
            log.add(PipelineError(
                layer=1, error_type="I-A",
                detail=f"[{idx}] Predicate '{pred}' used with inconsistent arities: {sorted(arities)}",
                symbol=pred,
            ))


def detect_ia_vampire_syntax_error(check_res: dict, idx: str, log: ErrorLog) -> None:
    """
    I-A (real signal): Vampire itself failed to parse/run the TPTP for this
    task (cate == 'Error'). This is a genuine malformed-symbol/syntax
    failure at the solver boundary — the strongest possible I-A signal,
    since it's not a heuristic, it's Vampire rejecting the formula outright.
    """
    if check_res.get("cate") == "Error":
        log.add(PipelineError(
            layer=1, error_type="I-A",
            detail=(
                f"[{idx}] Vampire returned ERROR — could not parse/run the "
                f"generated TPTP for one or more statements. Real syntax-level "
                f"malformation, not a semantic contradiction."
            ),
            symbol="",
        ))


def detect_ib_unsupported(steps_and_conclusion: list[dict], bank: dict[str, set], idx: str, log: ErrorLog) -> None:
    """I-B-i: predicate in steps/conclusion never appears in the premise bank."""
    for entry in steps_and_conclusion:
        for pred, args in extract_atoms(entry.get("fol", "")):
            if pred not in bank:
                log.add(PipelineError(
                    layer=2, error_type="I-B-i",
                    detail=(
                        f"[{idx}] Predicate '{pred}({', '.join(args)})' appears in "
                        f"reasoning/conclusion FOL but was never established by any "
                        f"premise — unsupported/hallucinated concept. ref: {entry.get('ref', '')!r}"
                    ),
                    symbol=pred,
                ))


def detect_ib_ill_formed(steps_and_conclusion: list[dict], bank: dict[str, set], idx: str, log: ErrorLog) -> None:
    """I-B-ii: arity mismatch against the premise bank's declared arity."""
    for entry in steps_and_conclusion:
        for pred, args in extract_atoms(entry.get("fol", "")):
            expected_arities = bank.get(pred)
            if expected_arities and len(args) not in expected_arities:
                log.add(PipelineError(
                    layer=2, error_type="I-B-ii",
                    detail=(
                        f"[{idx}] '{pred}' used with arity {len(args)} here, but "
                        f"premises establish arity {sorted(expected_arities)} — "
                        f"ref: {entry.get('ref', '')!r}"
                    ),
                    symbol=pred,
                ))


def detect_iia_multiplicity(all_entries: list[dict], idx: str, log: ErrorLog) -> None:
    """II-A-i: near-miss predicate name pairs within one task."""
    all_preds = sorted({pred for entry in all_entries for pred, _ in extract_atoms(entry.get("fol", ""))})
    seen_pairs = set()
    for i, p1 in enumerate(all_preds):
        for p2 in all_preds[i + 1:]:
            score = _similarity_score(p1, p2)
            if score >= _MULTIPLICITY_THRESHOLD:
                pair = tuple(sorted([p1, p2]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                log.add(PipelineError(
                    layer=2, error_type="II-A-i",
                    detail=(
                        f"[{idx}] '{p1}' and '{p2}' are near-miss predicate names "
                        f"(similarity={score:.2f}) — likely the same concept expressed "
                        f"with two different symbols within one example."
                    ),
                    symbol=p1,
                ))


def detect_iia_tptp_conversion_failure(all_entries: list[dict], idx: str, log: ErrorLog) -> None:
    """
    II-A-ii (real signal): the tptp field still contains raw Unicode logic
    symbols (∧ ∨ ¬ → ↔ ≠ ∀ ∃ ⊕) that FOL2Tptp.convert_to_tptp should have
    fully converted to TPTP syntax. Leftover symbols mean the conversion
    regex failed to match that statement's structure — a real grounding
    defect, replacing the old naive argument-swap heuristic (which produced
    ~227 false positives on legitimate bidirectional relational facts and
    has been removed).
    """
    for entry in all_entries:
        tptp = entry.get("tptp", "")
        leftover = set(tptp) & set(_UNICODE_LOGIC_SYMBOLS)
        if leftover:
            log.add(PipelineError(
                layer=3, error_type="II-A-ii",
                detail=(
                    f"[{idx}] TPTP conversion incomplete for '{entry.get('fol', '')}' — "
                    f"leftover symbol(s) {sorted(leftover)} in tptp field: {tptp!r}. "
                    f"convert_to_tptp failed to fully ground this statement."
                ),
                symbol="",
            ))


def detect_iib_i_translation_drift(all_entries: list[dict], idx: str, log: ErrorLog) -> None:
    """II-B-i: keyword-overlap check between a statement's real ref (NL) and
    its own fol translation, using the real ref/fol pairing from FOL2Tptp."""
    stopwords = {"a", "an", "the", "is", "are", "of", "for", "if", "to", "and",
                 "then", "not", "it", "that", "this", "something", "someone"}
    for entry in all_entries:
        ref = entry.get("ref", "").lower()
        fol = entry.get("fol", "")
        atoms = extract_atoms(fol)
        if not atoms or not ref:
            continue
        fol_tokens = set()
        for pred, args in atoms:
            fol_tokens |= _tokens(pred)
            for a in args:
                fol_tokens |= _tokens(a)
        ref_words = {w.strip(".,()") for w in ref.split() if w not in stopwords and len(w) > 2}
        if ref_words and not (ref_words & fol_tokens):
            log.add(PipelineError(
                layer=3, error_type="II-B-i",
                detail=(
                    f"[{idx}] Translation '{fol}' shares no content words with its own "
                    f"natural-language ref {ref!r} — possible mistranslation."
                ),
                symbol=atoms[0][0] if atoms else "",
            ))


def detect_iib_ii_dropped(task_info: dict, idx: str, log: ErrorLog) -> None:
    """
    II-B-ii (real signal): compares the ORIGINAL premise/step counts against
    what actually survived into premise:_fol / steps:_fol. A drop means a
    premise or reasoning step was silently never formalized at all.
    """
    original_premises = task_info.get("premises", [])
    premise_fol = task_info.get("premise:_fol", [])
    if len(premise_fol) < len(original_premises):
        log.add(PipelineError(
            layer=3, error_type="II-B-ii",
            detail=(
                f"[{idx}] {len(original_premises)} original premise(s) but only "
                f"{len(premise_fol)} made it into premise:_fol — "
                f"{len(original_premises) - len(premise_fol)} premise(s) dropped, "
                f"never formalized."
            ),
            symbol="",
        ))

    filter_steps = [s for s in task_info.get("filter_reasoning_steps", []) if s]
    final_steps = task_info.get("final_filter_reasoning_steps", [])
    # filter_steps includes the conclusion as its last element (see Constants.filter_step)
    expected_reasoning_steps = max(len(filter_steps) - 1, 0)
    if len(final_steps) < expected_reasoning_steps:
        log.add(PipelineError(
            layer=3, error_type="II-B-ii",
            detail=(
                f"[{idx}] {expected_reasoning_steps} filtered reasoning step(s) but only "
                f"{len(final_steps)} survived into final_filter_reasoning_steps — "
                f"{expected_reasoning_steps - len(final_steps)} step(s) dropped during "
                f"FOL2Tptp processing."
            ),
            symbol="",
        ))


def detect_iii_semantic(check_res: dict, idx: str, log: ErrorLog) -> None:
    """
    III-A-ii (real signal, using Vampire's actual verdicts):
      - cate == 'Semantic_Error' — Vampire's own p⊨c result disagrees with
        the dataset's ground-truth label (translation is internally
        consistent but doesn't mean what the dataset says it means).
      - A reasoning step was marked False/Unknown by Vampire, yet the task's
        final AnswerCorrect is still True — right answer via a broken
        step, i.e. an internally inconsistent chain.
    Note: cate == 'Error' is now handled separately under I-A (see
    detect_ia_vampire_syntax_error) — it is a syntax failure, not a
    semantic contradiction, so it is intentionally NOT counted here.
    """
    cate = check_res.get("cate", "")
    if cate == "Semantic_Error":
        log.add(PipelineError(
            layer=5, error_type="III-A-ii",
            detail=(
                f"[{idx}] Vampire's premises-entail-conclusion result disagrees "
                f"with the dataset ground-truth label — internally consistent "
                f"formalization that doesn't match the intended meaning."
            ),
            symbol="",
        ))
        return

    step_labels = check_res.get("step_correctness_label", [])
    if any(str(s) in ("False", "Unknown") for s in step_labels) and check_res.get("AnswerCorrect"):
        log.add(PipelineError(
            layer=5, error_type="III-A-ii",
            detail=(
                f"[{idx}] At least one reasoning step was marked False/Unknown by "
                f"Vampire ({step_labels}) but the final answer was still counted "
                f"correct — right answer via a broken step."
            ),
            symbol="",
        ))


# ---------------------------------------------------------------------------
# Per-task orchestration
# ---------------------------------------------------------------------------

def run_detectors_on_task(task_info: dict, check_res: dict, idx: str) -> ErrorLog:
    log = ErrorLog()

    premise_fol = task_info.get("premise:_fol", [])
    steps_fol = task_info.get("steps:_fol", [])
    conclusion_fol = task_info.get("conclusion:_fol")

    steps_and_conclusion = list(steps_fol)
    if conclusion_fol:
        steps_and_conclusion.append(conclusion_fol)
    all_entries = list(premise_fol) + steps_and_conclusion

    if check_res:
        detect_ia_vampire_syntax_error(check_res, idx, log)
        detect_iii_semantic(check_res, idx, log)

    if not premise_fol:
        # No usable formalization at all — Vampire-error signal (if any)
        # above is the only thing we can say about this task.
        return log

    bank = build_premise_bank(premise_fol)

    detect_ia_malformed(all_entries, idx, log)
    detect_ib_unsupported(steps_and_conclusion, bank, idx, log)
    detect_ib_ill_formed(steps_and_conclusion, bank, idx, log)
    detect_iia_multiplicity(all_entries, idx, log)
    detect_iia_tptp_conversion_failure(all_entries, idx, log)
    detect_iib_i_translation_drift(all_entries, idx, log)
    detect_iib_ii_dropped(task_info, idx, log)

    return log


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive error detection over MATP's real per-task pipeline output."
    )
    parser.add_argument("--project-dir", type=Path, required=True,
                         help="Path to workspace/output/{PROJECT_NAME} containing one subfolder per task")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    task_dirs = sorted(p.parent for p in args.project_dir.glob("*/task_info.json"))
    if not task_dirs:
        print(f"No task_info.json found under {args.project_dir} — check the path.")
        return

    combined = ErrorLog()
    n_missing_check_res = 0

    for task_dir in task_dirs:
        idx = task_dir.name
        task_info_path = task_dir / "task_info.json"
        check_res_path = task_dir / "check_res.json"

        task_info = json.loads(task_info_path.read_text(encoding="utf8"))
        check_res = {}
        if check_res_path.exists():
            check_res = json.loads(check_res_path.read_text(encoding="utf8"))
        else:
            n_missing_check_res += 1

        task_log = run_detectors_on_task(task_info, check_res, idx)
        combined.merge(task_log)

    print(f"Processed {len(task_dirs)} task(s) ({n_missing_check_res} missing check_res.json).")
    print(combined)
    combined.save(args.output)


if __name__ == "__main__":
    main()