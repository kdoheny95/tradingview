"""tastytrade REST client: auth, accounts, quotes, orders."""
import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests

import config


class TastytradeError(RuntimeError):
    pass


class TastytradeClient:
    """Thin wrapper around the tastytrade REST API.

    Handles session token caching to .session.json so we don't log in
    on every CLI invocation. Sessions last ~24h.
    """

    def __init__(self) -> None:
        self.base_url = config.TASTYTRADE_BASE_URL
        self.session_token: Optional[str] = None
        self.session_expires_at: Optional[datetime] = None
        self.account_number: Optional[str] = None

    # ---- session ----
    def _session_path(self) -> str:
        return config.SESSION_FILE

    def _load_session(self) -> bool:
        path = self._session_path()
        if not os.path.exists(path):
            return False
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        if data.get("env") != config.TASTYTRADE_ENV:
            return False
        token = data.get("token")
        expires = data.get("expires_at")
        if not token or not expires:
            return False
        expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if expiry <= datetime.now(timezone.utc):
            return False
        self.session_token = token
        self.session_expires_at = expiry
        return True

    def _save_session(self, token: str, expires_at: str) -> None:
        with open(self._session_path(), "w") as f:
            json.dump(
                {
                    "env": config.TASTYTRADE_ENV,
                    "token": token,
                    "expires_at": expires_at,
                },
                f,
            )

    def login(self) -> None:
        """Use cached session if valid, else re-auth."""
        if self._load_session():
            return
        config.assert_configured()
        url = f"{self.base_url}/sessions"
        resp = requests.post(
            url,
            json={
                "login": config.TASTYTRADE_USERNAME,
                "password": config.TASTYTRADE_PASSWORD,
            },
            timeout=15,
        )
        if resp.status_code != 201 and resp.status_code != 200:
            raise TastytradeError(
                f"Login failed ({resp.status_code}): {resp.text}"
            )
        body = resp.json().get("data", {})
        token = body.get("session-token")
        expires = body.get("session-expiration")
        if not token:
            raise TastytradeError(f"No session token in response: {resp.text}")
        self.session_token = token
        self.session_expires_at = (
            datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if expires
            else None
        )
        self._save_session(token, expires or "")

    # ---- HTTP helpers ----
    def _headers(self) -> dict:
        if not self.session_token:
            raise TastytradeError("Not authenticated; call login() first.")
        return {
            "Authorization": self.session_token,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        resp = requests.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            params=params,
            timeout=15,
        )
        if resp.status_code >= 400:
            raise TastytradeError(f"GET {path} -> {resp.status_code}: {resp.text}")
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        resp = requests.post(
            f"{self.base_url}{path}",
            headers=self._headers(),
            json=body,
            timeout=15,
        )
        if resp.status_code >= 400:
            raise TastytradeError(f"POST {path} -> {resp.status_code}: {resp.text}")
        return resp.json()

    # ---- accounts ----
    def get_account_number(self) -> str:
        if self.account_number:
            return self.account_number
        data = self._get("/customers/me/accounts")
        items = data.get("data", {}).get("items", [])
        if not items:
            raise TastytradeError("No accounts on this login.")
        self.account_number = items[0]["account"]["account-number"]
        return self.account_number

    def get_balance(self) -> dict:
        acct = self.get_account_number()
        data = self._get(f"/accounts/{acct}/balances")
        return data.get("data", {})

    def get_positions(self) -> list:
        acct = self.get_account_number()
        data = self._get(f"/accounts/{acct}/positions")
        return data.get("data", {}).get("items", [])

    # ---- orders ----
    def place_equity_order(
        self,
        symbol: str,
        quantity: int,
        action: str,
        price: Optional[float] = None,
        time_in_force: str = "Day",
    ) -> dict:
        """Place a stock order.

        action: "Buy to Open" | "Sell to Close" | "Sell to Open" | "Buy to Close"
        price: None => Market order, else Limit order at this price.
        """
        acct = self.get_account_number()
        order = {
            "time-in-force": time_in_force,
            "order-type": "Market" if price is None else "Limit",
            "legs": [
                {
                    "instrument-type": "Equity",
                    "symbol": symbol,
                    "quantity": quantity,
                    "action": action,
                }
            ],
        }
        if price is not None:
            order["price"] = f"{price:.2f}"
            order["price-effect"] = "Debit" if action.startswith("Buy") else "Credit"

        return self._post(f"/accounts/{acct}/orders", order)

    def dry_run_equity_order(self, symbol: str, quantity: int, action: str) -> dict:
        """Validate an order without placing it (tastytrade supports this)."""
        acct = self.get_account_number()
        order = {
            "time-in-force": "Day",
            "order-type": "Market",
            "legs": [
                {
                    "instrument-type": "Equity",
                    "symbol": symbol,
                    "quantity": quantity,
                    "action": action,
                }
            ],
        }
        return self._post(f"/accounts/{acct}/orders/dry-run", order)
