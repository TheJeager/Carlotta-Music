import os
import ast
import traceback
from typing import Optional


async def meval(code: str, globs: dict, **kwargs):
    """
    Safely evaluate data-only input.

    Dynamic code execution is intentionally not supported; callers may only pass
    Python literals such as strings, numbers, lists, dicts, tuples, booleans, or
    None.
    """
    del globs, kwargs

    return ast.literal_eval(code)


def format_exception(
    exc: BaseException, tb: Optional[list[traceback.FrameSummary]] = None
) -> str:
    """Format exception traceback into a readable string."""
    if tb is None:
        tb = traceback.extract_tb(exc.__traceback__)

    cwd = os.getcwd()
    for frame in tb:
        if cwd in frame.filename:
            frame.filename = os.path.relpath(frame.filename)

    return (
        "Traceback (most recent call last):\n"
        f"{''.join(traceback.format_list(tb))}"
        f"{type(exc).__name__}{': ' + str(exc) if str(exc) else ''}"
    )
