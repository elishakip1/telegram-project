import logging
import re

import requests

from app.config import get_config

logger = logging.getLogger(__name__)


class DVNetClient:
    def __init__(self) -> None:
        cfg = get_config()
        server_cfg = cfg["server"]
        self.api_key = server_cfg["dv_api_key"]
        base_url = server_cfg.get("dv_base_url", "http://localhost")
        self.wallet_url = f"{base_url.rstrip('/')}/api/v1/external/wallet"

    def get_or_create_deposit_address(self, external_id: str) -> str:
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

        body = response.text
        match = re.search(r"T[A-Za-z0-9]{33}", body)
        if not match:
            logger.error("DV.net wallet response did not include a TRC20 address: %s", body)
            raise ValueError("Could not parse TRC20 address from DV.net response")
        return match.group(0)
