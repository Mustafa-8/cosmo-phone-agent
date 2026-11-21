"""Speech tool: the only way the agent talks to the patient or the receptionist."""

from google.adk.tools import ToolContext

ALLOWED_LISTENERS = ("patient", "receptionist")


def say(to: str, text: str, tool_context: ToolContext) -> dict:
    """Speak one message to one person on the call.

    Use this tool for EVERY message you want someone to hear. Do not answer
    with plain text instead. Call it as the LAST step of your turn: after
    `say` runs, your turn ends and you wait for the next message.

    Args:
        to: Who should hear the message. Must be exactly "patient" (the
            international student, speaks English) or "receptionist" (the
            clinic receptionist, speaks Hungarian).
        text: The exact words to say. English when to="patient",
            Hungarian when to="receptionist". Keep it short, like a real
            phone call: one to three sentences.

    Returns:
        A dict with "status": "ok" plus the delivered "to" and "text",
        or "status": "error" with an "error_message" explaining what to fix.
    """
    if to not in ALLOWED_LISTENERS:
        return {
            "status": "error",
            "error_message": f"'to' must be one of {ALLOWED_LISTENERS}, got '{to}'.",
        }
    if not text.strip():
        return {"status": "error", "error_message": "'text' must not be empty."}
    # The spoken message is the final output of this turn: do not call the
    # model again just to "summarize" it (that returned empty content and
    # wasted a free-tier request).
    tool_context.actions.skip_summarization = True
    return {"status": "ok", "to": to, "text": text.strip()}
