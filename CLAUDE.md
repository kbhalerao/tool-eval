# Tool Eval Harness

Eval harness for testing LLM tool calling capabilities with local models via LMStudio.

## Project Setup

```bash
uv sync
```

## Running

```bash
# List available models
uv run tool-eval models

# Run tier 1 tests
uv run tool-eval run --tier 1

# Run all tests, save results
uv run tool-eval run --all --output results/model-name.jsonl

# Smoke test (one per tier)
uv run tool-eval smoke
```

## Architecture

- `src/tool_eval/tools/` - Tool definitions (Pydantic models + implementations)
- `src/tool_eval/harness/` - Test runner, metrics collection, scoring
- `src/tool_eval/client.py` - LMStudio client wrapper (uses `instructor`)
- `tests/` - Test case definitions (YAML)

## Adding Tools

Tools are registered via decorator in tier files:

```python
from pydantic import BaseModel, Field
from .registry import tool_registry

class MyArgs(BaseModel):
    param: str = Field(description="Description for the model")

@tool_registry.register(tier=2, description="What this tool does")
def my_tool(args: MyArgs) -> str:
    return f"Result: {args.param}"
```

## Test Case Format

```yaml
- id: "t1_example"
  tier: 1
  prompt: "User prompt that should trigger the tool"
  expected_tool: "tool_name"
  expected_args:
    param: "expected_value"
  tags: ["category"]
```

## Key Dependencies

- `instructor` - Structured output with validation/retries
- `pydantic` - Tool schemas
- `openai` - API client (instructor wraps this)

## LMStudio Config

Default endpoint: `http://macstudio.local:1234/v1`

Override via `LMSTUDIO_BASE_URL` env var or `--base-url` CLI flag.
