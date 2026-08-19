"""In-progress run state for the history panel.

A ``LiveEntry`` is a run that has been started but not yet completed. The
history panel renders these at the top of the list with live stage updates;
once the run completes (or fails), the entry is replaced by the real
``ReportEntry`` scanned from ``results/``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


# status constants
STATUS_RUNNING = "running"
STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"


@dataclass
class LiveEntry:
    """One in-progress analysis run."""

    ticker: str
    date: str
    started_at: float = field(default_factory=time.time)
    current_stage: str = ""
    completed_stages: list[str] = field(default_factory=list)
    status: str = STATUS_RUNNING
    final_decision: str = ""
    error: str = ""

    @property
    def key(self) -> str:
        return f"{self.ticker}|{self.date}"

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at

    def mark_stage(self, field: str, display: str) -> None:
        if field not in self.completed_stages:
            self.completed_stages.append(field)
        self.current_stage = display

    def mark_complete(self, decision: str) -> None:
        self.status = STATUS_COMPLETE
        self.final_decision = decision
        self.current_stage = ""

    def mark_failed(self, error: str) -> None:
        self.status = STATUS_FAILED
        self.error = error
        self.current_stage = ""
