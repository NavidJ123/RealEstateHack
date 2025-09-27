"""Provenance helpers to track input dataset hashes."""

from __future__ import annotations

from typing import Optional

from ..utils.io import file_sha256


def dataset_provenance() -> Optional[str]:
    sha = file_sha256("market_stats.csv")
    if sha:
        return f"data/market_stats.csv#sha256:{sha}"
    return None

