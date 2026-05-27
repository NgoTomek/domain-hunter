from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: src/domainhunter/config.py -> parents[2] == domain-hunter/
ROOT = Path(__file__).resolve().parents[2]


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    porkbun_api_key: str = ""
    porkbun_secret_key: str = ""


@dataclass
class Config:
    tlds: list[str]
    budget: float
    check_limit: int
    strategies: list[str]
    seeds: list[str]
    target_pool: int
    min_len: int
    max_len: int
    min_coolness: float
    dns_concurrency: int
    rdap_concurrency: int
    porkbun_concurrency: int
    cache_ttl_days: int
    secrets: Secrets


def load_config(path: Path | None = None) -> Config:
    path = path or (ROOT / "config.toml")
    data: dict = tomllib.loads(path.read_text()) if path.exists() else {}
    gen = data.get("generation", {})
    sco = data.get("scoring", {})
    net = data.get("network", {})
    return Config(
        tlds=data.get("tlds", [".com"]),
        budget=float(data.get("budget", 30.0)),
        check_limit=int(data.get("check_limit", 90)),
        strategies=data.get("strategies", ["brandable", "words", "seeds", "leet"]),
        seeds=data.get("seeds", []),
        target_pool=int(gen.get("target_pool", 5000)),
        min_len=int(gen.get("min_len", 3)),
        max_len=int(gen.get("max_len", 12)),
        min_coolness=float(sco.get("min_coolness", 0.5)),
        dns_concurrency=int(net.get("dns_concurrency", 40)),
        rdap_concurrency=int(net.get("rdap_concurrency", 12)),
        porkbun_concurrency=int(net.get("porkbun_concurrency", 3)),
        cache_ttl_days=int(net.get("cache_ttl_days", 7)),
        secrets=Secrets(),
    )
