from typing import Optional

def to_int(v) -> Optional[int]:
    try:
        if v is None or v == "" or str(v).lower() == "null":
            return None
        return int(float(v))
    except Exception:
        return None

def to_float(v) -> Optional[float]:
    try:
        if v is None or v == "" or str(v).lower() == "null":
            return None
        return float(v)
    except Exception:
        return None

def to_str(v) -> str:
    return "" if v is None else str(v)
