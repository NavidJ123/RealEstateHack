"""IO helpers for loading CSV data into pandas DataFrames."""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from typing import Optional

import pandas as pd

from .logging import get_logger

LOGGER = get_logger("utils.io")

DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))


@lru_cache(maxsize=16)
def load_csv(name: str) -> pd.DataFrame:
    """Load a CSV by filename from the data directory."""

    path = name if os.path.isabs(name) else os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV not found: {path}")
    LOGGER.debug("loading_csv path=%s", path)
    df = pd.read_csv(path)
    return df


def file_sha256(name: str) -> Optional[str]:
    """Compute a sha256 hash for provenance tracking."""

    path = name if os.path.isabs(name) else os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as infile:
        for chunk in iter(lambda: infile.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


__all__ = ["load_csv", "file_sha256", "DATA_DIR"]

