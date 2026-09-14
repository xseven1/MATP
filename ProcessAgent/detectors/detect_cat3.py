import os
from metagpt.actions import Action
from metagpt.logs import logger
from ProcessAgent.constant import Constants
from ProcessAgent.detectors.errors_taxonomy import PipelineError, append_errors_live


class DetectCat3(Action):
    """
    Watches VampireRun's output the moment check_res.json is written.
    Classifies cate == 'Error' as I-A (real syntax/parse failure at the
    solver boundary) and cate == 'Semantic_Error' or a broken-but-correct
    step chain as III-A-ii — using Vampire's own real verdicts, not a guess.

    Read-only: never mutates check_res.json, never blocks anything downstream.
    """

    name: str = "DetectCat3"

    async def run(self, path: str) -> str:
        idx = Constants.TASK_NAME or "unknown"
        check_res = Constants.read_json(path)
        if not check_res:
            return path

        errors = []
        cate = check_res.get("cate", "")

        if cate == "Error":
            errors.append(PipelineError(
                layer=1, error_type="I-A",
                detail="Vampire returned ERROR — could not parse/run the generated TPTP",
                task_idx=idx,
            ))
        elif cate == "Semantic_Error":
            errors.append(PipelineError(
                layer=5, error_type="III-A-ii",
                detail=(
                    "Vampire's premises-entail-conclusion result disagrees with the "
                    "dataset ground-truth label"
                ),
                task_idx=idx,
            ))
        else:
            step_labels = check_res.get("step_correctness_label", [])
            if any(str(s) in ("False", "Unknown") for s in step_labels) and check_res.get("AnswerCorrect"):
                errors.append(PipelineError(
                    layer=5, error_type="III-A-ii",
                    detail=(
                        f"Step(s) marked False/Unknown by Vampire ({step_labels}) but "
                        f"final answer still counted correct — broken step, right answer"
                    ),
                    task_idx=idx,
                ))

        project_dir = os.path.dirname(Constants.OUTPUT_DIR)
        append_errors_live(project_dir, errors)
        if errors:
            logger.warning(f"[DetectCat3] {idx}: {len(errors)} Cat-III/I error(s) found")

        return path