"""Server-side AI layer.

Public surface used by agents:

    from ..ai import complete_json, complete_text, available, mode, AILimitReached

Design rules enforced here (see docs/PRODUCTION_PLAN.md, Phase 1):
  * the API key never leaves the server;
  * prompts are versioned files loaded by name (backend/ai/prompts/*.vN.txt);
  * structured output is validated with a Pydantic schema and repaired once;
  * every call is capped by tokens, timeout, retries-with-backoff and a hard
    monthly budget stored in the usage log;
  * untrusted text (user input, web snippets) is delimited and never treated
    as instructions.
"""

from __future__ import annotations

from .client import (  # noqa: F401
    AIBudgetExceeded,
    AIConfigError,
    AIError,
    AIRequestError,
    AIValidationError,
    available,
    complete_json,
    complete_text,
    mode,
    usage_summary,
)
from .guard import sanitize_text, wrap_untrusted  # noqa: F401
