import os
import re
from difflib import SequenceMatcher
from metagpt.actions import Action
from metagpt.logs import logger
from ProcessAgent.constant import Constants
from ProcessAgent.detectors.errors_taxonomy import PipelineError, append_errors_live

_ATOM_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^()]*)\)')
_NOT_PREDICATES = {"forall", "exists"}
_UNICODE_LOGIC_SYMBOLS = "∧∨¬→↔≠∀∃⊕"


def _extract_atoms(fol: str):
    atoms = []
    for m in _ATOM_RE.finditer(fol):
        pred = m.group(1).strip()
        if pred.lower() in _NOT_PREDICATES:
            continue
        args = [a.strip() for a in m.group(2).split(",")] if m.group(2).strip() else []
        atoms.append((pred, args))
    return atoms


def _tokens(name: str) -> set:
    return set(name.lower().replace("-", "_").split("_"))


def _similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    overlap = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    dist = (1 - SequenceMatcher(None, a, b).ratio()) * max(len(a), len(b))
    char_sim = 1.0 - dist / max(len(a), len(b), 1)
    return 0.65 * overlap + 0.35 * char_sim


_MULTIPLICITY_THRESHOLD = 0.55


class DetectCat2(Action):
    """
    Watches FOL2Tptp's output the moment it's built — reads task_info.json's
    real premise:_fol / steps:_fol / conclusion:_fol (ref/fol/tptp triples),
    live, per task, before GrammerChecker/VampireRun ever runs on it.

    Checks: I-B-i (unsupported), I-B-ii (arity mismatch), II-A-i (near-miss
    naming), II-A-ii (leftover Unicode = incomplete TPTP conversion),
    II-B-i (translation drift), II-B-ii (dropped premises/steps).

    Read-only: never mutates task_info.json, never blocks GrammerChecker.
    """

    name: str = "DetectCat2"

    async def run(self, path: str) -> str:
        idx = Constants.TASK_NAME or "unknown"
        task_info_path = os.path.join(Constants.OUTPUT_DIR, Constants.TASK_INFO_FILE_NAME)
        task = Constants.read_json(task_info_path)

        premise_fol = task.get("premise:_fol", [])
        steps_fol = task.get("steps:_fol", [])
        conclusion_fol = task.get("conclusion:_fol")

        steps_and_conclusion = list(steps_fol)
        if conclusion_fol:
            steps_and_conclusion.append(conclusion_fol)
        all_entries = list(premise_fol) + steps_and_conclusion

        errors = []

        if not premise_fol:
            append_errors_live(os.path.dirname(Constants.OUTPUT_DIR), errors)
            return path

        # Premise bank — per-task canonical reference
        bank: dict[str, set] = {}
        for entry in premise_fol:
            for pred, args in _extract_atoms(entry.get("fol", "")):
                bank.setdefault(pred, set()).add(len(args))

        # I-B-i / I-B-ii
        for entry in steps_and_conclusion:
            for pred, args in _extract_atoms(entry.get("fol", "")):
                if pred not in bank:
                    errors.append(PipelineError(
                        layer=2, error_type="I-B-i",
                        detail=(
                            f"Predicate '{pred}({', '.join(args)})' in reasoning/"
                            f"conclusion FOL never established by any premise. "
                            f"ref: {entry.get('ref', '')!r}"
                        ),
                        task_idx=idx, symbol=pred,
                    ))
                elif len(args) not in bank[pred]:
                    errors.append(PipelineError(
                        layer=2, error_type="I-B-ii",
                        detail=(
                            f"'{pred}' used with arity {len(args)}, but premises "
                            f"establish arity {sorted(bank[pred])}. ref: {entry.get('ref', '')!r}"
                        ),
                        task_idx=idx, symbol=pred,
                    ))

        # II-A-i — near-miss predicate naming
        all_preds = sorted({p for e in all_entries for p, _ in _extract_atoms(e.get("fol", ""))})
        seen = set()
        for i, p1 in enumerate(all_preds):
            for p2 in all_preds[i + 1:]:
                score = _similarity(p1, p2)
                if score >= _MULTIPLICITY_THRESHOLD:
                    pair = tuple(sorted([p1, p2]))
                    if pair in seen:
                        continue
                    seen.add(pair)
                    errors.append(PipelineError(
                        layer=2, error_type="II-A-i",
                        detail=f"'{p1}' and '{p2}' are near-miss predicate names (similarity={score:.2f})",
                        task_idx=idx, symbol=p1,
                    ))

        # II-A-ii — incomplete TPTP conversion
        for entry in all_entries:
            tptp = entry.get("tptp", "")
            leftover = set(tptp) & set(_UNICODE_LOGIC_SYMBOLS)
            if leftover:
                errors.append(PipelineError(
                    layer=3, error_type="II-A-ii",
                    detail=(
                        f"TPTP conversion incomplete for '{entry.get('fol', '')}' — "
                        f"leftover {sorted(leftover)} in tptp: {tptp!r}"
                    ),
                    task_idx=idx,
                ))

        # II-B-i — translation drift (keyword overlap)
        stopwords = {"a", "an", "the", "is", "are", "of", "for", "if", "to", "and",
                     "then", "not", "it", "that", "this", "something", "someone"}
        for entry in all_entries:
            ref = entry.get("ref", "").lower()
            fol = entry.get("fol", "")
            atoms = _extract_atoms(fol)
            if not atoms or not ref:
                continue
            fol_tokens = set()
            for pred, args in atoms:
                fol_tokens |= _tokens(pred)
                for a in args:
                    fol_tokens |= _tokens(a)
            ref_words = {w.strip(".,()") for w in ref.split() if w not in stopwords and len(w) > 2}
            if ref_words and not (ref_words & fol_tokens):
                errors.append(PipelineError(
                    layer=3, error_type="II-B-i",
                    detail=f"Translation '{fol}' shares no content words with ref {ref!r}",
                    task_idx=idx, symbol=atoms[0][0] if atoms else "",
                ))

        # II-B-ii — dropped premises/steps
        original_premises = task.get("premises", [])
        if len(premise_fol) < len(original_premises):
            errors.append(PipelineError(
                layer=3, error_type="II-B-ii",
                detail=(
                    f"{len(original_premises)} original premise(s) but only "
                    f"{len(premise_fol)} formalized — "
                    f"{len(original_premises) - len(premise_fol)} dropped"
                ),
                task_idx=idx,
            ))

        filter_steps = [s for s in task.get("filter_reasoning_steps", []) if s]
        final_steps = task.get("final_filter_reasoning_steps", [])
        expected = max(len(filter_steps) - 1, 0)
        if len(final_steps) < expected:
            errors.append(PipelineError(
                layer=3, error_type="II-B-ii",
                detail=(
                    f"{expected} filtered reasoning step(s) but only "
                    f"{len(final_steps)} survived FOL2Tptp — "
                    f"{expected - len(final_steps)} dropped"
                ),
                task_idx=idx,
            ))

        project_dir = os.path.dirname(Constants.OUTPUT_DIR)
        append_errors_live(project_dir, errors)
        if errors:
            logger.warning(f"[DetectCat2] {idx}: {len(errors)} Cat-II error(s) found")

        return path