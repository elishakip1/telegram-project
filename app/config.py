from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def get_config() -> dict:
    config_path = Path("config.yaml")
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)
