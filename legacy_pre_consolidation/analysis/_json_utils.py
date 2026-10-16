"""
Shared JSON-serialization helper for analysis/*.py scripts' optional
--json-out output. Mirrors export_gui_data.py's fallback_json (numpy/pandas/
NaN handling) but is duplicated here rather than imported, so analysis/
stays dependency-free of the root pipeline scripts.
"""
import json

import numpy as np
import pandas as pd


def fallback_json(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return str(obj)


def write_json(data, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=fallback_json)
    print(f"\n[json-out] wrote {path}")
