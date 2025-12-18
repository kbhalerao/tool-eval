"""Metrics collection and result storage."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CallMetrics:
    """Metrics captured for a single tool call."""

    test_id: str
    tier: int
    prompt: str

    # Outcome
    success: bool  # Valid tool call produced
    correct_tool: bool  # Right tool selected
    correct_args: float  # 0-1 score on argument correctness

    # Performance
    retries: int
    input_tokens: int
    output_tokens: int
    thinking_tokens: int  # Tokens spent on reasoning (for thinking models)
    latency_ms: int

    # Raw data
    expected_tool: str
    expected_args: dict[str, Any]
    actual_tool: str | None
    actual_args: dict[str, Any] | None
    raw_output: str | None = None
    thinking: str | None = None
    error: str | None = None

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    model: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CallMetrics":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class EvalResult:
    """Aggregated results from an eval run."""

    model: str
    total_tests: int
    successful: int
    correct_tool: int
    avg_arg_score: float
    avg_latency_ms: float
    avg_retries: float
    total_input_tokens: int
    total_output_tokens: int

    # Per-tier breakdown
    tier_results: dict[int, dict[str, float]] = field(default_factory=dict)

    # Individual call metrics
    calls: list[CallMetrics] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.successful / self.total_tests if self.total_tests > 0 else 0

    @property
    def tool_accuracy(self) -> float:
        return self.correct_tool / self.total_tests if self.total_tests > 0 else 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "model": self.model,
            "total_tests": self.total_tests,
            "successful": self.successful,
            "correct_tool": self.correct_tool,
            "avg_arg_score": self.avg_arg_score,
            "avg_latency_ms": self.avg_latency_ms,
            "avg_retries": self.avg_retries,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "success_rate": self.success_rate,
            "tool_accuracy": self.tool_accuracy,
            "tier_results": self.tier_results,
            "calls": [c.to_dict() for c in self.calls],
        }


class MetricsWriter:
    """Writes metrics to JSONL file."""

    def __init__(self, output_path: Path | str):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, metrics: CallMetrics) -> None:
        """Append a single call's metrics to the output file."""
        with open(self.output_path, "a") as f:
            f.write(json.dumps(metrics.to_dict()) + "\n")

    def write_all(self, metrics_list: list[CallMetrics]) -> None:
        """Write multiple metrics at once."""
        for m in metrics_list:
            self.write(m)


class MetricsReader:
    """Reads metrics from JSONL file."""

    def __init__(self, input_path: Path | str):
        self.input_path = Path(input_path)

    def read_all(self) -> list[CallMetrics]:
        """Read all metrics from file."""
        metrics = []
        with open(self.input_path, "r") as f:
            for line in f:
                if line.strip():
                    metrics.append(CallMetrics.from_dict(json.loads(line)))
        return metrics

    def aggregate(self) -> EvalResult:
        """Aggregate metrics into summary result."""
        calls = self.read_all()
        if not calls:
            return EvalResult(
                model="unknown",
                total_tests=0,
                successful=0,
                correct_tool=0,
                avg_arg_score=0,
                avg_latency_ms=0,
                avg_retries=0,
                total_input_tokens=0,
                total_output_tokens=0,
            )

        model = calls[0].model or "unknown"
        total = len(calls)
        successful = sum(1 for c in calls if c.success)
        correct_tool = sum(1 for c in calls if c.correct_tool)
        avg_arg_score = sum(c.correct_args for c in calls) / total
        avg_latency = sum(c.latency_ms for c in calls) / total
        avg_retries = sum(c.retries for c in calls) / total
        total_input = sum(c.input_tokens for c in calls)
        total_output = sum(c.output_tokens for c in calls)

        # Per-tier breakdown
        tier_results = {}
        tiers = set(c.tier for c in calls)
        for tier in tiers:
            tier_calls = [c for c in calls if c.tier == tier]
            tier_total = len(tier_calls)
            tier_results[tier] = {
                "total": tier_total,
                "success_rate": sum(1 for c in tier_calls if c.success) / tier_total,
                "tool_accuracy": sum(1 for c in tier_calls if c.correct_tool) / tier_total,
                "avg_arg_score": sum(c.correct_args for c in tier_calls) / tier_total,
            }

        return EvalResult(
            model=model,
            total_tests=total,
            successful=successful,
            correct_tool=correct_tool,
            avg_arg_score=avg_arg_score,
            avg_latency_ms=avg_latency,
            avg_retries=avg_retries,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            tier_results=tier_results,
            calls=calls,
        )
