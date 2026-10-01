"""Legge traders.toml: l'elenco dei bot e il capitale iniziale."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

CONFIG_FILE = Path(os.getenv("TRADERS_CONFIG", Path(__file__).resolve().parent.parent / "traders.toml"))
DEFAULT_MODEL = os.getenv("TRADER_MODEL", "").strip() or "gpt-5.4-mini"


@dataclass(frozen=True)
class TraderConfig:
    name: str
    profile: str
    model: str
    strategy: str


def load_config(path: Path = CONFIG_FILE) -> tuple[float, list[TraderConfig]]:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    traders = []
    for entry in data.get("trader", []):
        name = str(entry.get("name", "")).strip()
        if not name:
            raise ValueError(f"{path}: ogni [[trader]] deve avere un name")
        traders.append(
            TraderConfig(
                name=name,
                profile=str(entry.get("profile", "")).strip(),
                model=str(entry.get("model", "")).strip() or DEFAULT_MODEL,
                strategy=str(entry.get("strategy", "")).strip(),
            )
        )

    names = [t.name.lower() for t in traders]
    if not traders:
        raise ValueError(f"{path}: nessun [[trader]] definito")
    if len(set(names)) != len(names):
        raise ValueError(f"{path}: nomi dei trader duplicati")

    return float(data.get("initial_balance", 10_000)), traders


INITIAL_BALANCE, TRADERS = load_config()
