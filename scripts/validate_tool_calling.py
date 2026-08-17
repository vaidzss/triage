# validate_tool_calling.py - Phase 0 checkpoint.
#
# Sends a tool-call-forcing request to each candidate model via llm_client
# and asserts the response actually contains tool_calls (not a plain-text
# reply, and not an HTTP 400 "does not support tools").

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from triage import config, llm_client

PING_TOOL = {
    "type": "function",
    "function": {
        "name": "ping",
        "description": "Respond to a connectivity check by echoing back a status string.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Always pass 'ok'."},
            },
            "required": ["status"],
        },
    },
}

MESSAGES = [
    {
        "role": "user",
        "content": "Call the `ping` tool now with status='ok'. Do not reply in plain text.",
    }
]


def check(model: str) -> bool:
    print(f"--- {model} ---")
    try:
        response = llm_client.complete(
            model=model,
            messages=MESSAGES,
            tools=[PING_TOOL],
            tool_choice="required",
        )
    except Exception as exc:
        print(f"  FAIL: request errored: {exc}")
        return False

    choice = response.choices[0]
    tool_calls = choice.message.tool_calls
    if tool_calls:
        print(f"  OK: got {len(tool_calls)} tool_call(s): {tool_calls[0].function.name}")
        return True

    print(f"  FAIL: no tool_calls in response; content={choice.message.content!r}")
    return False


if __name__ == "__main__":
    models = [m for m in (config.LOCAL_MODEL, config.CLOUD_MODEL) if m]
    results = {m: check(m) for m in models}
    print("\nSummary:")
    for m, ok in results.items():
        print(f"  {m}: {'PASS' if ok else 'FAIL'}")
    if not all(results.values()):
        sys.exit(1)
