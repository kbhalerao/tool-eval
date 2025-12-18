"""Eval runner - orchestrates test execution."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..client import LMStudioClient
from ..tools.registry import tool_registry
from .metrics import CallMetrics, MetricsWriter
from .scoring import Scorer


@dataclass
class TestCase:
    """A single test case."""

    id: str
    tier: int
    prompt: str
    expected_tool: str
    expected_args: dict[str, Any]
    tools: list[str] | None = None  # Specific tools to present
    acceptable_tools: list[str] | None = None  # Alternative valid tools
    tags: list[str] | None = None
    mock_response: dict[str, Any] | None = None  # For multi-step tests

    @classmethod
    def from_dict(cls, data: dict) -> "TestCase":
        return cls(
            id=data["id"],
            tier=data["tier"],
            prompt=data["prompt"],
            expected_tool=data["expected_tool"],
            expected_args=data.get("expected_args", {}),
            tools=data.get("tools"),
            acceptable_tools=data.get("acceptable_tools"),
            tags=data.get("tags"),
            mock_response=data.get("mock_response"),
        )


def load_test_cases(path: Path) -> list[TestCase]:
    """Load test cases from YAML file or directory."""
    cases = []

    if path.is_file():
        with open(path) as f:
            data = yaml.safe_load(f)
            cases.extend([TestCase.from_dict(d) for d in data])
    elif path.is_dir():
        for file in path.rglob("*.yaml"):
            with open(file) as f:
                data = yaml.safe_load(f)
                if data:
                    cases.extend([TestCase.from_dict(d) for d in data])

    return cases


class EvalRunner:
    """Main eval runner."""

    def __init__(
        self,
        client: LMStudioClient,
        scorer: Scorer | None = None,
        console: Console | None = None,
        reasoning_effort: str | None = None,
    ):
        self.client = client
        self.scorer = scorer or Scorer(use_semantic=True, client=client)
        self.console = console or Console()
        self.reasoning_effort = reasoning_effort  # "low", "medium", "high", or None

    def run_single(self, test: TestCase) -> CallMetrics:
        """Run a single test case."""
        # Determine which tools to present
        if test.tools:
            # Test case specifies which tools to use
            tool_names = test.tools
        elif test.tier <= 4:
            # Tiers 1-4: Focus on tool usage correctness, not selection
            # Only present the expected tool to reduce schema size
            tool_names = [test.expected_tool]
        else:
            # Tier 5+: Multi-tool selection tests
            # Present all tools for that tier
            tier_tools = tool_registry.get_by_tier(test.tier)
            tool_names = [t.name for t in tier_tools]

        # Always ensure expected tool is available
        if test.expected_tool not in tool_names:
            tool_names.append(test.expected_tool)

        tools = tool_registry.to_openai_tools(tool_names)

        try:
            response = self.client.call_with_tools(
                prompt=test.prompt,
                tools=tools,
                reasoning_effort=self.reasoning_effort,
            )

            # Extract tool call from response
            # Handle both chat/completions format (objects) and responses API format (dicts)
            actual_tool = None
            actual_args = None

            if response.result and len(response.result) > 0:
                tool_call = response.result[0]

                # Responses API format: {"type": "function_call", "name": "...", "arguments": "..."}
                if isinstance(tool_call, dict):
                    actual_tool = tool_call.get("name")
                    args_str = tool_call.get("arguments", "{}")
                    try:
                        actual_args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    except json.JSONDecodeError:
                        actual_args = {}
                # Chat completions format: object with .function.name and .function.arguments
                else:
                    actual_tool = tool_call.function.name
                    try:
                        actual_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        actual_args = {}

            # Score the result
            success = actual_tool is not None
            correct_tool, _ = self.scorer.score_tool(
                test.expected_tool,
                actual_tool,
                test.acceptable_tools,
            )
            correct_args = 0.0
            if correct_tool and actual_args:
                correct_args = self.scorer.score_args(test.expected_args, actual_args)

            return CallMetrics(
                test_id=test.id,
                tier=test.tier,
                prompt=test.prompt,
                success=success,
                correct_tool=correct_tool,
                correct_args=correct_args,
                retries=response.retries,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                thinking_tokens=response.thinking_tokens,
                latency_ms=response.latency_ms,
                expected_tool=test.expected_tool,
                expected_args=test.expected_args,
                actual_tool=actual_tool,
                actual_args=actual_args,
                raw_output=json.dumps(response.raw_response) if response.raw_response else None,
                thinking=response.thinking,
                model=self.client.get_current_model(),
                tags=test.tags or [],
            )

        except Exception as e:
            return CallMetrics(
                test_id=test.id,
                tier=test.tier,
                prompt=test.prompt,
                success=False,
                correct_tool=False,
                correct_args=0.0,
                retries=0,
                input_tokens=0,
                output_tokens=0,
                thinking_tokens=0,
                latency_ms=0,
                expected_tool=test.expected_tool,
                expected_args=test.expected_args,
                actual_tool=None,
                actual_args=None,
                error=str(e),
                model=self.client.get_current_model(),
                tags=test.tags or [],
            )

    def run_tests(
        self,
        tests: list[TestCase],
        output_path: Path | None = None,
    ) -> list[CallMetrics]:
        """Run multiple tests with progress display."""
        results = []
        writer = MetricsWriter(output_path) if output_path else None

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task(f"Running {len(tests)} tests...", total=len(tests))

            for test in tests:
                progress.update(task, description=f"[cyan]{test.id}[/cyan]")
                metrics = self.run_single(test)
                results.append(metrics)

                if writer:
                    writer.write(metrics)

                progress.advance(task)

        return results

    def print_summary(self, results: list[CallMetrics]) -> None:
        """Print summary table of results."""
        if not results:
            self.console.print("[yellow]No results to display[/yellow]")
            return

        table = Table(title="Eval Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        total = len(results)
        success = sum(1 for r in results if r.success)
        correct_tool = sum(1 for r in results if r.correct_tool)
        avg_arg_score = sum(r.correct_args for r in results) / total
        avg_latency = sum(r.latency_ms for r in results) / total
        total_output = sum(r.output_tokens for r in results)
        total_thinking = sum(r.thinking_tokens for r in results)
        total_input = sum(r.input_tokens for r in results)

        table.add_row("Total Tests", str(total))
        table.add_row("Success Rate", f"{success}/{total} ({100*success/total:.1f}%)")
        table.add_row("Tool Accuracy", f"{correct_tool}/{total} ({100*correct_tool/total:.1f}%)")
        table.add_row("Avg Arg Score", f"{avg_arg_score:.2f}")
        table.add_row("Avg Latency", f"{avg_latency:.0f}ms")
        table.add_row("Input Tokens", str(total_input))
        table.add_row("Output Tokens", str(total_output))
        if total_thinking > 0:
            table.add_row("Thinking Tokens", f"{total_thinking} ({100*total_thinking/(total_output+total_thinking):.0f}% of output)")

        self.console.print(table)

        # Per-tier breakdown
        tiers = sorted(set(r.tier for r in results))
        if len(tiers) > 1:
            tier_table = Table(title="Per-Tier Breakdown")
            tier_table.add_column("Tier")
            tier_table.add_column("Success")
            tier_table.add_column("Tool Acc")
            tier_table.add_column("Arg Score")

            for tier in tiers:
                tier_results = [r for r in results if r.tier == tier]
                t_total = len(tier_results)
                t_success = sum(1 for r in tier_results if r.success)
                t_tool = sum(1 for r in tier_results if r.correct_tool)
                t_arg = sum(r.correct_args for r in tier_results) / t_total

                tier_table.add_row(
                    str(tier),
                    f"{100*t_success/t_total:.0f}%",
                    f"{100*t_tool/t_total:.0f}%",
                    f"{t_arg:.2f}",
                )

            self.console.print(tier_table)
