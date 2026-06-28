"""Configuration loader for Phase 1.

This module is the single source of truth for runtime settings. It loads
config.yaml, loads secrets from a gitignored .env, and resolves paths against
the repo root. FIPS codes are always returned as strings with leading zeros
preserved.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# The repo root is two levels up from this file: src/config.py -> src -> root.
REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config.yaml"
ENV_PATH = REPO_ROOT / ".env"


def fips(value: Any) -> str:
    """Return a FIPS code as a string with leading zeros preserved.

    Census FIPS codes are identifiers, not integers. A state code such as 06 is
    not the number 6. This helper normalises any input to a zero-padded string.
    State codes pad to 2, county codes to 3, county FIPS such as 06073 to 5.
    """
    if value is None:
        raise ValueError("FIPS value cannot be None")
    text = str(value).strip()
    if not text:
        raise ValueError("FIPS value cannot be empty")
    if not text.isdigit():
        # Already a non numeric string identifier, return as is.
        return text
    # Pad to the nearest known FIPS width. 1 to 2 is a state, 3 a county,
    # 4 to 5 a county FIPS, longer values are left untouched.
    width_map = {1: 2, 2: 2, 3: 3, 4: 5, 5: 5}
    target = width_map.get(len(text), len(text))
    return text.zfill(target)


@dataclass(frozen=True)
class Config:
    """Immutable view over the parsed configuration."""

    data: dict
    root: Path

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    # CRS helpers.
    @property
    def crs_storage(self) -> str:
        return str(self.data["crs"]["storage"])

    @property
    def crs_working(self) -> str:
        return str(self.data["crs"]["working"])

    # County and territory helpers, FIPS as strings.
    @property
    def counties(self) -> dict[str, str]:
        return {name: fips(code) for name, code in self.data["counties"].items()}

    @property
    def all_county_fips(self) -> list[str]:
        return [fips(c) for c in self.data["counties"].values()]

    def territory_counties(self, territory: str) -> list[str]:
        return [fips(c) for c in self.data["territories"][territory]["counties"]]

    def path(self, key: str) -> Path:
        """Resolve a configured directory under paths against the repo root."""
        return self.root / self.data["paths"][key]

    def secret(self, env_var: str) -> str | None:
        """Read a secret from the environment. Returns None if absent."""
        value = os.environ.get(env_var)
        return value if value else None

    def require_secret(self, env_var: str) -> str:
        value = self.secret(env_var)
        if not value:
            raise RuntimeError(
                f"Required secret {env_var} is not set. "
                f"Add it to {ENV_PATH.name} or export it in the environment."
            )
        return value


@lru_cache(maxsize=1)
def load_config(config_path: str | os.PathLike[str] | None = None) -> Config:
    """Load and cache the configuration.

    The .env file is loaded first so secrets are available on the environment.
    Pass an explicit path in tests to load a fixture config.
    """
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    path = Path(config_path) if config_path else CONFIG_PATH
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return Config(data=data, root=REPO_ROOT)


if __name__ == "__main__":
    cfg = load_config()
    print("counties:", cfg.counties)
    print("crs storage:", cfg.crs_storage, "working:", cfg.crs_working)
    print("processed path:", cfg.path("processed"))
