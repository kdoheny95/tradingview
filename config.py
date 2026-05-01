"""Central configuration. Reads from environment via .env."""
import os
from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw not in (None, "") else default


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw not in (None, "") else default


# ---- tastytrade ----
TASTYTRADE_ENV = os.environ.get("TASTYTRADE_ENV", "sandbox").strip().lower()
TASTYTRADE_USERNAME = os.environ.get("TASTYTRADE_USERNAME", "")
TASTYTRADE_PASSWORD = os.environ.get("TASTYTRADE_PASSWORD", "")

TASTYTRADE_BASE_URL = (
    "https://api.tastyworks.com"
    if TASTYTRADE_ENV == "live"
    else "https://api.cert.tastyworks.com"
)

# ---- Claude ----
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

# ---- Risk & sizing ----
NOTIONAL_ACCOUNT_SIZE = _get_float("NOTIONAL_ACCOUNT_SIZE", 10_000.0)
RISK_PER_TRADE_PCT = _get_float("RISK_PER_TRADE_PCT", 1.0)
MAX_TRADES_PER_DAY = _get_int("MAX_TRADES_PER_DAY", 3)
MAX_OPEN_POSITIONS = _get_int("MAX_OPEN_POSITIONS", 5)
DAILY_LOSS_HALT_PCT = _get_float("DAILY_LOSS_HALT_PCT", 5.0)
MIN_SCORE = _get_int("MIN_SCORE", 60)

# ---- Behaviour ----
DRY_RUN = _get_bool("DRY_RUN", True)

# ---- Universe (edit freely) ----
UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA",
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META",
]

# ---- Files ----
SESSION_FILE = ".session.json"
POSITIONS_FILE = "positions.json"
LOG_FILE = "trader.log"


def assert_tastytrade_configured() -> None:
    """Fail loud if tastytrade secrets are missing."""
    missing = []
    if not TASTYTRADE_USERNAME:
        missing.append("TASTYTRADE_USERNAME")
    if not TASTYTRADE_PASSWORD:
        missing.append("TASTYTRADE_PASSWORD")
    if missing:
        raise RuntimeError(
            f"Missing env vars: {', '.join(missing)}. "
            "Copy .env.example to .env and fill it in."
        )


def assert_anthropic_configured() -> None:
    """Fail loud if the Anthropic key is missing."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "Missing env var: ANTHROPIC_API_KEY. "
            "Copy .env.example to .env and fill it in."
        )
