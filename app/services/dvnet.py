import logging
import re
from typing import Any, Optional

import requests

from app.config import get_config

logger = logging.getLogger(__name__)


class DVNetError(Exception):
    """Raised when DV.net operations fail."""


def _extract_address(payload: Any) -> Optional[str]:
    if isinstance(payload, str):
        match = re.search(r"T[A-Za-z0-9]{33}", payload)
        return match.group(0) if match else None

    if isinstance(payload, dict):
        for key in ("address", "wallet", "wallet_address", "deposit_address"):
            value = payload.get(key)
            if isinstance(value, str) and re.fullmatch(r"T[A-Za-z0-9]{33}", value):
                return value

        for value in payload.values():
            found = _extract_address(value)
            if found:
                return found

    if isinstance(payload, list):
        for value in payload:
            found = _extract_address(value)
            if found:
                return found

    return None


class DVNetClient:
    def __init__(self) -> None:
        cfg = get_config()
        server_cfg = cfg["server"]
        self.api_key = server_cfg["dv_api_key"]
        base_url = server_cfg.get("dv_base_url", "http://localhost")
        self.wallet_url = f"{base_url.rstrip('/')}/api/v1/external/wallet"

    def get_or_create_deposit_address(self, external_id: str) -> str:
        try:
            response = requests.post(
                self.wallet_url,
                headers={"x-api-key": self.api_key},
                json={
                    "amount": 0,
                    "store_external_id": external_id,
                    "currency": "USDT_TRC20",
                },
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DVNetError(f"DV.net wallet request failed: {exc}") from exc

        parsed: Any
        try:
            parsed = response.json()
        except ValueError:
            parsed = response.text

        address = _extract_address(parsed)
        if not address:
            logger.error("DV.net wallet response did not include a TRC20 address: %s", response.text)
            raise DVNetError("Could not parse TRC20 address from DV.net response")

        return address
