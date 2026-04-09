from __future__ import annotations

import json
from io import StringIO
from typing import BinaryIO

import pandas as pd


SAMPLE_DATASET = """review_id,review_title,review_body,sentiment_label,theme_livraison,theme_sav,theme_produit
r1,Fast shipping and perfect item,The delivery was fast and the package arrived in perfect condition.,positive,1,0,1
r2,Support never answered,I contacted customer support twice for a refund and they never answered.,negative,0,1,0
r3,Cheap material and bad fit,The product looks nice in pictures but the material feels cheap and the size is wrong.,negative,0,0,1
r4,Delayed parcel,Shipping took too long and the parcel arrived damaged.,negative,1,0,1
r5,Helpful support team,The support team was helpful and solved my issue quickly.,positive,0,1,0
r6,Average experience,The product is okay overall but nothing special.,neutral,0,0,1
r7,Great all around,Fast delivery and excellent quality.,positive,1,0,1
r8,Refund process was frustrating,The return was accepted but the refund process was slow and confusing.,negative,0,1,0
"""


def load_default_dataset() -> pd.DataFrame:
    return pd.read_csv(StringIO(SAMPLE_DATASET))


def safe_read_csv_filelike(file_obj: BinaryIO) -> pd.DataFrame:
    raw = file_obj.read()
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    for sep in (",", ";", "\t"):
        try:
            df = pd.read_csv(StringIO(text), sep=sep)
            if len(df.columns) > 1:
                return df
        except Exception:
            continue
    return pd.read_csv(StringIO(text))


def prepare_dataset(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    if "review_id" not in cleaned.columns:
        cleaned["review_id"] = [f"review_{idx + 1}" for idx in range(len(cleaned))]
    if "review_title" not in cleaned.columns:
        cleaned["review_title"] = ""
    if "review_body" not in cleaned.columns:
        cleaned["review_body"] = cleaned.get("text", "")
    if "sentiment_label" not in cleaned.columns:
        cleaned["sentiment_label"] = "unknown"
    for col in ("theme_livraison", "theme_sav", "theme_produit"):
        if col not in cleaned.columns:
            cleaned[col] = 0
    return cleaned.fillna("")


def flatten_results(df: pd.DataFrame) -> pd.DataFrame:
    export = df.copy()
    for col in export.columns:
        if export[col].apply(lambda v: isinstance(v, list)).any():
            export[col] = export[col].apply(
                lambda values: json.dumps(values, ensure_ascii=False)
                if isinstance(values, list) and values and isinstance(values[0], dict)
                else ", ".join(values)
                if isinstance(values, list)
                else values
            )
    return export
