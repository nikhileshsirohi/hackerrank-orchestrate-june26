"""Utility functions for CSV, images, and output row assembly."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from schemas import OUTPUT_COLUMNS, safe_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = PROJECT_ROOT / "dataset"


def read_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path).fillna("")


def parse_image_paths(image_paths: Any) -> list[str]:
    text = safe_text(image_paths)
    return [part.strip() for part in text.split(";") if part.strip()]


def extract_image_id(image_path: str | Path) -> str:
    return Path(str(image_path)).stem


def resolve_image_path(image_path: str | Path, dataset_dir: Path = DATASET_DIR) -> Path:
    raw = Path(str(image_path))
    if raw.is_absolute():
        return raw
    if raw.parts and raw.parts[0] == "images":
        return dataset_dir / raw
    return PROJECT_ROOT / raw


def image_to_data_url(image_path: str | Path) -> str:
    path = Path(image_path)
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            elif image.mode == "L":
                image = image.convert("RGB")
            image.thumbnail((1600, 1600))
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=90, optimize=True)
            data = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{data}"
    except Exception:
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{data}"


def load_image_data_urls(image_paths: list[str], dataset_dir: Path = DATASET_DIR) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    for original_path in image_paths:
        resolved = resolve_image_path(original_path, dataset_dir)
        image_id = extract_image_id(original_path)
        if not resolved.exists():
            images.append(
                {
                    "image_id": image_id,
                    "path": str(original_path),
                    "resolved_path": str(resolved),
                    "data_url": "",
                    "load_error": "missing_file",
                }
            )
            continue
        images.append(
            {
                "image_id": image_id,
                "path": str(original_path),
                "resolved_path": str(resolved),
                "data_url": image_to_data_url(resolved),
                "load_error": "",
            }
        )
    return images


def filter_user_history(user_history_df: pd.DataFrame, user_id: Any) -> list[dict[str, Any]]:
    if user_history_df.empty or "user_id" not in user_history_df.columns:
        return []
    mask = user_history_df["user_id"].astype(str) == safe_text(user_id)
    return user_history_df.loc[mask].to_dict(orient="records")


def filter_evidence_requirements(
    evidence_requirements_df: pd.DataFrame, claim_object: Any
) -> list[dict[str, Any]]:
    if evidence_requirements_df.empty or "claim_object" not in evidence_requirements_df.columns:
        return []
    object_text = safe_text(claim_object).lower()
    object_series = evidence_requirements_df["claim_object"].astype(str).str.lower()
    mask = (object_series == object_text) | (object_series == "all")
    return evidence_requirements_df.loc[mask].to_dict(orient="records")


def join_semicolon(values: Any) -> str:
    if isinstance(values, list):
        clean = [safe_text(value) for value in values if safe_text(value)]
        if not clean:
            return "none"
        return ";".join(clean)
    text = safe_text(values)
    return text or "none"


def build_output_row(claim_row: Any, normalized_output: dict[str, Any]) -> dict[str, Any]:
    def claim_value(column: str) -> str:
        if hasattr(claim_row, "get"):
            return safe_text(claim_row.get(column, ""))
        return safe_text(getattr(claim_row, column, ""))

    row = {
        "user_id": claim_value("user_id"),
        "image_paths": claim_value("image_paths"),
        "user_claim": claim_value("user_claim"),
        "claim_object": claim_value("claim_object"),
        "evidence_standard_met": str(bool(normalized_output["evidence_standard_met"])).lower(),
        "evidence_standard_met_reason": safe_text(
            normalized_output["evidence_standard_met_reason"]
        ),
        "risk_flags": join_semicolon(normalized_output["risk_flags"]),
        "issue_type": safe_text(normalized_output["issue_type"]),
        "object_part": safe_text(normalized_output["object_part"]),
        "claim_status": safe_text(normalized_output["claim_status"]),
        "claim_status_justification": safe_text(
            normalized_output["claim_status_justification"]
        ),
        "supporting_image_ids": join_semicolon(normalized_output["supporting_image_ids"]),
        "valid_image": str(bool(normalized_output["valid_image"])).lower(),
        "severity": safe_text(normalized_output["severity"]),
    }
    return {column: row[column] for column in OUTPUT_COLUMNS}


def count_images_in_csv(csv_path: str | Path) -> int:
    df = read_csv(csv_path)
    return sum(len(parse_image_paths(value)) for value in df.get("image_paths", []))
