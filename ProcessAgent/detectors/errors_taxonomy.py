from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

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
    task_idx: str = ""
    symbol: str = ""

    @property
    def category(self) -> str:
        return ERROR_TYPE_TO_CATEGORY.get(self.error_type, "I")

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "category": self.category,
            "error_type": self.error_type,
            "detail": self.detail,
            "task_idx": self.task_idx,
            "symbol": self.symbol,
        }


def append_errors_live(project_dir: str, errors: list[PipelineError]) -> None:
    """
    Appends each error as one line of JSON to errors_live.jsonl at the
    project level (one level above per-task OUTPUT_DIR), so errors persist
    incrementally across all 344 tasks even if the run crashes partway.
    """
    if not errors:
        return
    log_path = Path(project_dir) / "errors_live.jsonl"
    with open(log_path, "a", encoding="utf8") as f:
        for e in errors:
            f.write(json.dumps(e.to_dict()) + "\n")


def load_errors_live(project_dir: str) -> list[dict]:
    log_path = Path(project_dir) / "errors_live.jsonl"
    if not log_path.exists():
        return []
    with open(log_path, encoding="utf8") as f:
        return [json.loads(line) for line in f if line.strip()]