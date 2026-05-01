"""Ask Claude to approve or veto each candidate trade.

Claude sees the screener output, indicators, and a short market context,
then returns structured JSON: {approve: bool, confidence: 0-100, reason: str}.
"""
import json
from dataclasses import dataclass
from typing import Optional

from anthropic import Anthropic

import config
from screener import Candidate


@dataclass
class ClaudeVerdict:
    approve: bool
    confidence: int  # 0-100
    reason: str


_SYSTEM_PROMPT = """You are a careful trade-review agent for a small retail
trading account. You receive a candidate trade with technical indicators and
must decide whether to APPROVE or VETO it.

Rules:
- Capital preservation is more important than catching every winner.
- Veto if the setup is mediocre, the indicators conflict, or the rationale is weak.
- Approve only when the technical picture is clean and risk/reward is reasonable.
- Be skeptical. A veto is always safer than a marginal approval.

Respond with ONLY a JSON object on a single line, no prose, no code fences:
{"approve": true|false, "confidence": 0-100, "reason": "<one short sentence>"}
"""


def _client() -> Anthropic:
    config.assert_anthropic_configured()
    return Anthropic(api_key=config.ANTHROPIC_API_KEY)


def review(candidate: Candidate, market_context: Optional[str] = None) -> ClaudeVerdict:
    """Ask Claude to evaluate a single candidate."""
    client = _client()
    user_msg = {
        "symbol": candidate.symbol,
        "direction": candidate.direction,
        "screener_score": candidate.score,
        "last_price": candidate.last_price,
        "rationale": candidate.rationale,
        "indicators": candidate.indicators,
        "market_context": market_context or "none provided",
    }

    resp = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=200,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(user_msg)}],
    )

    text = "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    ).strip()

    try:
        parsed = json.loads(text)
        return ClaudeVerdict(
            approve=bool(parsed.get("approve", False)),
            confidence=int(parsed.get("confidence", 0)),
            reason=str(parsed.get("reason", "")).strip(),
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        return ClaudeVerdict(
            approve=False,
            confidence=0,
            reason=f"could not parse Claude response: {text[:120]}",
        )
