"""Schema constants and normalization helpers for claim review outputs."""

from __future__ import annotations

from typing import Any


CLAIM_STATUSES = ["supported", "contradicted", "not_enough_information"]

ISSUE_TYPES = [
    "dent",
    "scratch",
    "crack",
    "glass_shatter",
    "broken_part",
    "missing_part",
    "torn_packaging",
    "crushed_packaging",
    "water_damage",
    "stain",
    "none",
    "unknown",
]

CAR_OBJECT_PARTS = [
    "front_bumper",
    "rear_bumper",
    "door",
    "hood",
    "windshield",
    "side_mirror",
    "headlight",
    "taillight",
    "fender",
    "quarter_panel",
    "body",
    "unknown",
]

LAPTOP_OBJECT_PARTS = [
    "screen",
    "keyboard",
    "trackpad",
    "hinge",
    "lid",
    "corner",
    "port",
    "base",
    "body",
    "unknown",
]

PACKAGE_OBJECT_PARTS = [
    "box",
    "package_corner",
    "package_side",
    "seal",
    "label",
    "contents",
    "item",
    "unknown",
]

OBJECT_PARTS_BY_OBJECT = {
    "car": CAR_OBJECT_PARTS,
    "laptop": LAPTOP_OBJECT_PARTS,
    "package": PACKAGE_OBJECT_PARTS,
}

ALL_OBJECT_PARTS = sorted(
    set(CAR_OBJECT_PARTS + LAPTOP_OBJECT_PARTS + PACKAGE_OBJECT_PARTS)
)

RISK_FLAGS = [
    "none",
    "blurry_image",
    "cropped_or_obstructed",
    "low_light_or_glare",
    "wrong_angle",
    "wrong_object",
    "wrong_object_part",
    "damage_not_visible",
    "claim_mismatch",
    "possible_manipulation",
    "non_original_image",
    "text_instruction_present",
    "user_history_risk",
    "manual_review_required",
]

SEVERITIES = ["none", "low", "medium", "high", "unknown"]

OUTPUT_COLUMNS = [
    "user_id",
    "image_paths",
    "user_claim",
    "claim_object",
    "evidence_standard_met",
    "evidence_standard_met_reason",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "claim_status_justification",
    "supporting_image_ids",
    "valid_image",
    "severity",
]

MODEL_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "evidence_standard_met",
        "evidence_standard_met_reason",
        "risk_flags",
        "issue_type",
        "object_part",
        "claim_status",
        "claim_status_justification",
        "supporting_image_ids",
        "valid_image",
        "severity",
    ],
    "properties": {
        "evidence_standard_met": {"type": "boolean"},
        "evidence_standard_met_reason": {"type": "string"},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "issue_type": {"type": "string"},
        "object_part": {"type": "string"},
        "claim_status": {"type": "string"},
        "claim_status_justification": {"type": "string"},
        "supporting_image_ids": {"type": "array", "items": {"type": "string"}},
        "valid_image": {"type": "boolean"},
        "severity": {"type": "string"},
    },
}


def safe_text(value: Any) -> str:
    """Convert model/CSV values to clean strings without leaking NaN."""
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        pass
    return str(value).strip()


def coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = safe_text(value).lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return default


def _normalize_token(value: Any) -> str:
    return safe_text(value).lower().replace(" ", "_").replace("-", "_")


def _safe_enum(value: Any, allowed: list[str], fallback: str) -> str:
    token = _normalize_token(value)
    if token in allowed:
        return token
    return fallback


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = []
        for item in value:
            raw_items.extend(safe_text(item).replace(",", ";").split(";"))
    elif isinstance(value, str):
        raw_items = value.replace(",", ";").split(";")
    else:
        raw_items = [value]
    return [safe_text(item) for item in raw_items if safe_text(item)]


def normalize_risk_flags(value: Any) -> list[str]:
    flags = [_safe_enum(item, RISK_FLAGS, "") for item in normalize_string_list(value)]
    flags = [flag for flag in flags if flag]
    if not flags or flags == ["none"]:
        return ["none"]
    return [flag for flag in dict.fromkeys(flags) if flag != "none"] or ["none"]


def normalize_supporting_image_ids(value: Any, allowed_image_ids: list[str]) -> list[str]:
    ids = normalize_string_list(value)
    if not ids or ids == ["none"]:
        return ["none"]
    valid_ids = [image_id for image_id in ids if image_id in allowed_image_ids]
    return list(dict.fromkeys(valid_ids)) or ["none"]


def normalize_model_output(
    model_output: dict[str, Any] | None,
    claim_object: str,
    image_ids: list[str],
    user_history: list[dict[str, Any]] | None = None,
    claim_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize a model response into the required controlled vocabulary."""
    data = model_output if isinstance(model_output, dict) else {}
    allowed_parts = OBJECT_PARTS_BY_OBJECT.get(_normalize_token(claim_object), ALL_OBJECT_PARTS)

    normalized = {
        "evidence_standard_met": coerce_bool(data.get("evidence_standard_met"), False),
        "evidence_standard_met_reason": safe_text(
            data.get("evidence_standard_met_reason")
        )
        or "The submitted evidence could not be verified automatically.",
        "risk_flags": normalize_risk_flags(data.get("risk_flags")),
        "issue_type": _safe_enum(data.get("issue_type"), ISSUE_TYPES, "unknown"),
        "object_part": _safe_enum(data.get("object_part"), allowed_parts, "unknown"),
        "claim_status": _safe_enum(
            data.get("claim_status"), CLAIM_STATUSES, "not_enough_information"
        ),
        "claim_status_justification": safe_text(
            data.get("claim_status_justification")
        )
        or "The image evidence was not sufficient for a confident automated decision.",
        "supporting_image_ids": normalize_supporting_image_ids(
            data.get("supporting_image_ids"), image_ids
        ),
        "valid_image": coerce_bool(data.get("valid_image"), False),
        "severity": _safe_enum(data.get("severity"), SEVERITIES, "unknown"),
    }

    claim_text = safe_text((claim_row or {}).get("user_claim", "")).lower()
    claim_object_text = _normalize_token(claim_object)

    if not normalized["valid_image"]:
        normalized["evidence_standard_met"] = False
        normalized["claim_status"] = "not_enough_information"
        normalized["supporting_image_ids"] = ["none"]
        if normalized["severity"] == "none":
            normalized["severity"] = "unknown"

    if normalized["claim_status"] == "contradicted" and normalized["issue_type"] == "unknown":
        # Keep unknown when the visible object is wrong; otherwise the model may set none.
        normalized["issue_type"] = data.get("issue_type", "unknown")
        normalized["issue_type"] = _safe_enum(normalized["issue_type"], ISSUE_TYPES, "unknown")

    if (
        claim_object_text == "laptop"
        and normalized["object_part"] == "keyboard"
        and normalized["claim_status"] == "supported"
        and any(word in claim_text for word in ["water", "liquid", "spill", "spilled", "stain", "sticky", "coffee"])
    ):
        normalized["issue_type"] = "stain"
        normalized["severity"] = "medium"

    if (
        claim_object_text == "laptop"
        and normalized["object_part"] == "screen"
        and normalized["issue_type"] == "glass_shatter"
    ):
        normalized["issue_type"] = "crack"
        if normalized["severity"] == "high":
            normalized["severity"] = "medium"

    if (
        claim_object_text == "package"
        and normalized["object_part"] == "contents"
        and normalized["claim_status"] == "not_enough_information"
    ):
        merged_flags = [
            flag for flag in normalized["risk_flags"] if flag and flag != "none"
        ]
        for flag in ["cropped_or_obstructed", "damage_not_visible", "manual_review_required"]:
            if flag not in merged_flags:
                merged_flags.append(flag)
        normalized["risk_flags"] = merged_flags
        normalized["valid_image"] = False
        normalized["evidence_standard_met"] = False

    if "wrong_object" in normalized["risk_flags"] and normalized["claim_status"] == "contradicted":
        normalized["issue_type"] = "unknown"
        if normalized["severity"] in {"medium", "high", "unknown"}:
            normalized["severity"] = "low"
        if "claim_mismatch" not in normalized["risk_flags"]:
            normalized["risk_flags"].append("claim_mismatch")

    history_flags: list[str] = []
    for history_row in user_history or []:
        history_flags.extend(normalize_string_list(history_row.get("history_flags")))
    history_flags = [
        flag
        for flag in normalize_risk_flags(history_flags)
        if flag in {"user_history_risk", "manual_review_required"}
    ]
    if history_flags:
        merged_flags = [
            flag
            for flag in normalized["risk_flags"]
            if flag and flag != "none"
        ]
        merged_flags.extend(history_flags)
        normalized["risk_flags"] = list(dict.fromkeys(merged_flags)) or ["none"]

    if normalized["claim_status"] == "not_enough_information":
        normalized["severity"] = "unknown"
        normalized["supporting_image_ids"] = ["none"]
        if normalized["supporting_image_ids"] == ["none"] and any(
            flag in normalized["risk_flags"]
            for flag in [
                "cropped_or_obstructed",
                "damage_not_visible",
                "wrong_angle",
                "wrong_object_part",
            ]
        ):
            normalized["valid_image"] = False
            normalized["evidence_standard_met"] = False

    if normalized["claim_status"] == "contradicted" and normalized["issue_type"] == "none":
        normalized["severity"] = "none"

    if not normalized["risk_flags"]:
        normalized["risk_flags"] = ["none"]

    return normalized


def output_json_schema_for_api() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "claim_evidence_review",
            "strict": True,
            "schema": MODEL_JSON_SCHEMA,
        },
    }
