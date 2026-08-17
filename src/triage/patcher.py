# patcher.py - Patch Engineer node.
#
# Given a target file's current contents and an issue description (plus, on
# retry, the prior attempt's diff and failure output), asks the LLM for the
# complete corrected file content via a forced tool call, then computes the
# unified diff itself with difflib (see graph.py's patcher_node).
#
# Deliberately NOT asking the model to hand-write the unified diff (hunk
# headers with `@@ -start,count +start,count @@` line-count arithmetic):
# qwen2.5:7b was observed reproducing the exact same correct code fix but
# with a wrong hunk-header line count every retry ("corrupt patch at line 4"),
# burning the whole format-retry budget on something the model was never
# going to get right by re-asking. Generating the diff in Python instead
# guarantees a syntactically valid patch every time and lets the model's
# unreliability show up only in the code it writes, not in diff bookkeeping.

import json
from typing import Optional

from . import config, llm_client

SUBMIT_FIX_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_fix",
        "description": (
            "Submit the fix as the complete, corrected contents of the target "
            "file (the whole file, not a diff or a snippet)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_contents": {
                    "type": "string",
                    "description": "The complete corrected file, from the first line to the last.",
                },
            },
            "required": ["file_contents"],
        },
    },
}

SYSTEM_PROMPT = (
    "You are the Patch Engineer in an automated code-repair pipeline. "
    "Given a target file's current contents and a bug/issue description, "
    "produce the smallest correct fix. "
    "Always call the `submit_fix` tool with the complete corrected file "
    "contents - the whole file, unchanged except for the fix - never reply "
    "in plain text and never omit unrelated lines."
)


class PatcherError(Exception):
    """Raised when the model fails to produce a usable patch tool call."""


def _build_messages(
    target_file: str,
    file_contents: str,
    issue_description: str,
    last_attempt: Optional[str],
    last_error: Optional[str],
) -> list[dict]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Target file: {target_file}\n\n"
                f"--- current contents ---\n{file_contents}\n--- end contents ---\n\n"
                f"Issue: {issue_description}"
            ),
        },
    ]
    if last_attempt and last_error:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Your previous attempt did not fix the issue. Try again.\n\n"
                    f"Previous file contents you submitted:\n{last_attempt}\n\n"
                    f"Failure output:\n{last_error}"
                ),
            }
        )
    return messages


def propose_patch(
    target_file: str,
    file_contents: str,
    issue_description: str,
    last_attempt: Optional[str] = None,
    last_error: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Returns the model's proposed complete corrected file contents."""
    model = model or config.PATCHER_MODEL
    messages = _build_messages(
        target_file, file_contents, issue_description, last_attempt, last_error
    )
    response = llm_client.complete(
        model=model,
        messages=messages,
        tools=[SUBMIT_FIX_TOOL],
        tool_choice="required",
    )
    tool_calls = response.choices[0].message.tool_calls
    if not tool_calls:
        content = response.choices[0].message.content
        raise PatcherError(
            f"Patcher model {model!r} did not call submit_fix; got: {content!r}"
        )
    args = json.loads(tool_calls[0].function.arguments)
    return args["file_contents"]
