import os
import re
from metagpt.actions import Action
from metagpt.logs import logger
from ProcessAgent.constant import Constants
from ProcessAgent.detectors.errors_taxonomy import PipelineError, append_errors_live

_ATOM_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^()]*)\)')
_NOT_PREDICATES = {"forall", "exists"}


def _extract_atoms(text: str):
    atoms = []
    for m in _ATOM_RE.finditer(text):
        pred = m.group(1).strip()
        if pred.lower() in _NOT_PREDICATES:
            continue
        args = [a.strip() for a in m.group(2).split(",")] if m.group(2).strip() else []
        atoms.append((pred, args))
    return atoms


class DetectCat1(Action):
    """
    Watches NL2FOL's raw output the moment it's written, before FOL2Tptp
    or Vampire ever see it. Catches I-A malformed-symbol issues at the
    earliest possible point — invalid predicate names and inconsistent
    arity for the same predicate name within one task's raw generation.

    Read-only: never mutates the file, never blocks downstream roles.
    """

    name: str = "DetectCat1"

    async def run(self, path: str) -> str:
        idx = Constants.TASK_NAME or "unknown"
        raw_text = Constants.read(path)

        errors = []
        arity_by_pred: dict[str, set] = {}

        for pred, args in _extract_atoms(raw_text):
            if not re.match(r'^[a-z][a-z0-9_]*$', pred):
                errors.append(PipelineError(
                    layer=1, error_type="I-A",
                    detail=f"Predicate '{pred}' is not valid snake_case",
                    task_idx=idx, symbol=pred,
                ))
            arity_by_pred.setdefault(pred, set()).add(len(args))

        for pred, arities in arity_by_pred.items():
            if len(arities) > 1:
                errors.append(PipelineError(
                    layer=1, error_type="I-A",
                    detail=f"Predicate '{pred}' used with inconsistent arities: {sorted(arities)}",
                    task_idx=idx, symbol=pred,
                ))

        project_dir = os.path.dirname(Constants.OUTPUT_DIR)
        append_errors_live(project_dir, errors)
        if errors:
            logger.warning(f"[DetectCat1] {idx}: {len(errors)} Cat-I error(s) found")

        # Echo the same path back unchanged — this action never alters the
        # pipeline's actual data, just observes it.
        return path