"""CLI for tool-eval."""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .client import LMStudioClient
from .harness.runner import EvalRunner, load_test_cases
from .harness.scoring import Scorer
from .harness.metrics import MetricsReader
from .tools import tool_registry

# Import tiers to register tools
from .tools import tier1, tier2, tier3  # noqa: F401

console = Console()


@click.group()
@click.option(
    "--base-url",
    envvar="LMSTUDIO_BASE_URL",
    default="http://macstudio.local:1234/v1",
    help="LMStudio API base URL",
)
@click.option(
    "--model",
    default=None,
    help="Model to use (defaults to first available)",
)
@click.pass_context
def main(ctx, base_url: str, model: str | None):
    """Tool calling eval harness for local LLMs."""
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url
    ctx.obj["model"] = model


@main.command()
@click.pass_context
def models(ctx):
    """List available models from LMStudio."""
    client = LMStudioClient(base_url=ctx.obj["base_url"])
    try:
        available = client.list_models()
        if available:
            table = Table(title="Available Models")
            table.add_column("Model ID", style="cyan")
            for m in available:
                table.add_row(m)
            console.print(table)
        else:
            console.print("[yellow]No models available[/yellow]")
    except Exception as e:
        console.print(f"[red]Error connecting to LMStudio: {e}[/red]")


@main.command()
def tools():
    """List registered tools."""
    all_tools = tool_registry.all()
    if not all_tools:
        console.print("[yellow]No tools registered[/yellow]")
        return

    table = Table(title="Registered Tools")
    table.add_column("Name", style="cyan")
    table.add_column("Tier", style="green")
    table.add_column("Description")
    table.add_column("Tags", style="dim")

    for t in sorted(all_tools, key=lambda x: (x.tier, x.name)):
        table.add_row(
            t.name,
            str(t.tier),
            t.description[:50] + "..." if len(t.description) > 50 else t.description,
            ", ".join(t.tags),
        )

    console.print(table)


@main.command()
@click.option("--tier", type=int, help="Run only tests for this tier")
@click.option("--test", "test_id", help="Run specific test by ID")
@click.option("--all", "run_all", is_flag=True, help="Run all tests")
@click.option("--output", "-o", type=click.Path(), help="Output file for results (JSONL)")
@click.option(
    "--tests-dir",
    type=click.Path(exists=True),
    default="tests",
    help="Directory containing test cases",
)
@click.option("--exact-match", is_flag=True, help="Use exact match instead of semantic scoring")
@click.option(
    "--reasoning",
    type=click.Choice(["low", "medium", "high"]),
    default=None,
    help="Enable reasoning mode for thinking models (low/medium/high effort)",
)
@click.pass_context
def run(ctx, tier: int | None, test_id: str | None, run_all: bool, output: str | None, tests_dir: str, exact_match: bool, reasoning: str | None):
    """Run eval tests."""
    tests_path = Path(tests_dir)

    if not tests_path.exists():
        console.print(f"[red]Tests directory not found: {tests_path}[/red]")
        return

    # Load test cases
    test_cases = load_test_cases(tests_path)

    if not test_cases:
        console.print("[yellow]No test cases found[/yellow]")
        return

    # Filter tests
    if test_id:
        test_cases = [t for t in test_cases if t.id == test_id]
        if not test_cases:
            console.print(f"[red]Test not found: {test_id}[/red]")
            return
    elif tier is not None:
        test_cases = [t for t in test_cases if t.tier == tier]
        if not test_cases:
            console.print(f"[yellow]No tests for tier {tier}[/yellow]")
            return
    elif not run_all:
        console.print("[yellow]Specify --tier, --test, or --all[/yellow]")
        return

    console.print(f"[cyan]Running {len(test_cases)} test(s)...[/cyan]")

    # Setup client and runner
    client = LMStudioClient(
        base_url=ctx.obj["base_url"],
        model=ctx.obj["model"],
    )
    scorer = Scorer(use_semantic=not exact_match, client=client if not exact_match else None)
    runner = EvalRunner(client, scorer, console, reasoning_effort=reasoning)

    # Run tests
    output_path = Path(output) if output else None
    results = runner.run_tests(test_cases, output_path)

    # Print summary
    runner.print_summary(results)

    if output:
        console.print(f"\n[green]Results saved to {output}[/green]")


@main.command()
@click.option(
    "--tests-dir",
    type=click.Path(exists=True),
    default="tests",
    help="Directory containing test cases",
)
@click.pass_context
def smoke(ctx, tests_dir: str):
    """Run smoke test (one test per tier)."""
    tests_path = Path(tests_dir)
    all_tests = load_test_cases(tests_path)

    if not all_tests:
        console.print("[yellow]No test cases found[/yellow]")
        return

    # Get one test per tier
    tiers = {}
    for t in all_tests:
        if t.tier not in tiers:
            tiers[t.tier] = t

    smoke_tests = list(tiers.values())
    console.print(f"[cyan]Smoke test: {len(smoke_tests)} tier(s)[/cyan]")

    client = LMStudioClient(
        base_url=ctx.obj["base_url"],
        model=ctx.obj["model"],
    )
    runner = EvalRunner(client, console=console)
    results = runner.run_tests(smoke_tests)
    runner.print_summary(results)


@main.command()
@click.argument("file1", type=click.Path(exists=True))
@click.argument("file2", type=click.Path(exists=True))
def compare(file1: str, file2: str):
    """Compare two result files."""
    reader1 = MetricsReader(Path(file1))
    reader2 = MetricsReader(Path(file2))

    result1 = reader1.aggregate()
    result2 = reader2.aggregate()

    table = Table(title="Comparison")
    table.add_column("Metric")
    table.add_column(Path(file1).stem, style="cyan")
    table.add_column(Path(file2).stem, style="green")
    table.add_column("Diff")

    def diff_str(a: float, b: float) -> str:
        d = b - a
        if d > 0:
            return f"[green]+{d:.2f}[/green]"
        elif d < 0:
            return f"[red]{d:.2f}[/red]"
        return "0"

    table.add_row(
        "Success Rate",
        f"{result1.success_rate*100:.1f}%",
        f"{result2.success_rate*100:.1f}%",
        diff_str(result1.success_rate*100, result2.success_rate*100),
    )
    table.add_row(
        "Tool Accuracy",
        f"{result1.tool_accuracy*100:.1f}%",
        f"{result2.tool_accuracy*100:.1f}%",
        diff_str(result1.tool_accuracy*100, result2.tool_accuracy*100),
    )
    table.add_row(
        "Avg Arg Score",
        f"{result1.avg_arg_score:.2f}",
        f"{result2.avg_arg_score:.2f}",
        diff_str(result1.avg_arg_score, result2.avg_arg_score),
    )
    table.add_row(
        "Avg Latency",
        f"{result1.avg_latency_ms:.0f}ms",
        f"{result2.avg_latency_ms:.0f}ms",
        diff_str(result1.avg_latency_ms, result2.avg_latency_ms),
    )

    console.print(table)


if __name__ == "__main__":
    main()
