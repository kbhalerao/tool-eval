"""
Simple agentic loop for multi-turn tool use.
"""

import json
import httpx
from typing import Optional
from .tools import tool_registry
from .tools.exploration import list_dir, read_file, grep, ListArgs, ReadArgs, GrepArgs


TOOL_FUNCS = {
    "list_dir": (list_dir, ListArgs),
    "read_file": (read_file, ReadArgs),
    "grep": (grep, GrepArgs),
}

BASE_URL = "http://macstudio.local:1234/v1"


def call_model(model: str, messages: list, tools: list) -> dict:
    """Call model via chat completions API with tools."""
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
    }

    response = httpx.post(
        f"{BASE_URL}/chat/completions",
        json=payload,
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()


def run_agent(
    question: str,
    model: str,
    max_turns: int = 10,
    verbose: bool = True
) -> dict:
    """
    Run agentic loop until model answers or hits max turns.
    """
    # Get tool schemas
    tools = tool_registry.to_openai_tools(["list_dir", "read_file", "grep"])

    system_prompt = """You are a research assistant analyzing test results in a tool-test project.

You have access to these tools:
- list_dir: List files in a directory (path like "results" or ".")
- read_file: Read a file's contents (path like "results/granite-t6.jsonl")
- grep: Search for text patterns in files

The test results are JSONL files in the 'results/' directory.
Each line in a JSONL file is a JSON object with fields like:
  test_id, tier, success, correct_tool, correct_args, latency_ms, actual_tool, etc.

Strategy:
1. First list what files are available
2. Read relevant files to answer the question
3. When you have enough info, give your final answer WITHOUT calling more tools

Keep your final answer concise and data-driven."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    tool_calls_log = []

    for turn in range(max_turns):
        if verbose:
            print(f"\n--- Turn {turn + 1} ---")

        # Call model
        response = call_model(model, messages, tools)

        # Extract assistant message
        choice = response.get("choices", [{}])[0]
        msg = choice.get("message", {})

        # Check for tool calls
        tool_calls = msg.get("tool_calls", [])

        if tool_calls:
            # Add assistant message with tool calls
            messages.append(msg)

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args_str = tc["function"]["arguments"]
                tool_id = tc["id"]

                try:
                    tool_args = json.loads(tool_args_str)
                except:
                    tool_args = {}

                if verbose:
                    print(f"Tool: {tool_name}({json.dumps(tool_args)})")

                # Execute tool
                if tool_name in TOOL_FUNCS:
                    func, args_model = TOOL_FUNCS[tool_name]
                    try:
                        args = args_model(**tool_args)
                        result = func(args)
                    except Exception as e:
                        result = {"error": str(e)}
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}

                result_str = json.dumps(result)
                if verbose:
                    if len(result_str) > 300:
                        print(f"Result: {result_str[:300]}...")
                    else:
                        print(f"Result: {result_str}")

                tool_calls_log.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })

                # Add tool result
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result_str
                })

        else:
            # No tool call - model gave final answer
            answer = msg.get("content", "")
            if verbose:
                print(f"Answer: {answer[:500]}...")

            return {
                "question": question,
                "answer": answer,
                "turns": turn + 1,
                "tool_calls": tool_calls_log,
                "success": True
            }

    # Hit max turns
    return {
        "question": question,
        "answer": None,
        "turns": max_turns,
        "tool_calls": tool_calls_log,
        "success": False
    }


if __name__ == "__main__":
    import sys

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen/qwen3-30b-a3b-2507"
    question = sys.argv[2] if len(sys.argv) > 2 else "What result files exist in the results directory?"
    output_file = sys.argv[3] if len(sys.argv) > 3 else None

    result = run_agent(question, model)
    result["model"] = model  # add model to output

    print("\n" + "="*50)
    print(f"Turns: {result['turns']}")
    print(f"Tool calls: {len(result['tool_calls'])}")
    print(f"Success: {result['success']}")
    if result['answer']:
        print(f"\nFinal Answer:\n{result['answer']}")

    if output_file:
        with open(output_file, "a") as f:
            f.write(json.dumps(result) + "\n")
        print(f"\nAppended to {output_file}")
