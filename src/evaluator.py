"""Evaluate the claim review pipeline on labeled sample rows."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from main import PROJECT_ROOT, run_pipeline
from schemas import OUTPUT_COLUMNS
from utils import count_images_in_csv, read_csv


IMPORTANT_FIELDS = [
    "claim_status",
    "issue_type",
    "object_part",
    "evidence_standard_met",
    "valid_image",
    "severity",
]


def find_mismatches(expected_df: pd.DataFrame, predicted_df: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    comparable_fields = [
        "claim_status",
        "issue_type",
        "object_part",
        "evidence_standard_met",
        "valid_image",
        "severity",
    ]
    for index, expected_row in expected_df.iterrows():
        if index >= len(predicted_df):
            continue
        predicted_row = predicted_df.iloc[index]
        mismatched = [
            field
            for field in comparable_fields
            if field in expected_df.columns
            and field in predicted_df.columns
            and str(expected_row[field]).strip().lower()
            != str(predicted_row[field]).strip().lower()
        ]
        if not mismatched:
            continue
        rows.append(
            {
                "row_number": str(index + 1),
                "user_id": str(expected_row.get("user_id", "")),
                "claim_object": str(expected_row.get("claim_object", "")),
                "mismatched_fields": ";".join(mismatched),
                "expected_claim_status": str(expected_row.get("claim_status", "")),
                "predicted_claim_status": str(predicted_row.get("claim_status", "")),
                "expected_issue_type": str(expected_row.get("issue_type", "")),
                "predicted_issue_type": str(predicted_row.get("issue_type", "")),
                "expected_severity": str(expected_row.get("severity", "")),
                "predicted_severity": str(predicted_row.get("severity", "")),
                "prediction_reason": str(
                    predicted_row.get("claim_status_justification", "")
                ),
            }
        )
    return rows


def compute_metrics(expected_df: pd.DataFrame, predicted_df: pd.DataFrame) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for field in IMPORTANT_FIELDS:
        if field not in expected_df.columns or field not in predicted_df.columns:
            continue
        expected = expected_df[field].astype(str).str.strip().str.lower()
        predicted = predicted_df[field].astype(str).str.strip().str.lower()
        metrics[field] = float((expected == predicted).mean()) if len(expected) else 0.0
    return metrics


def write_evaluation_report(
    report_path: str | Path,
    model: str,
    input_path: str | Path,
    output_path: str | Path,
    metrics: dict[str, float],
    mismatches: list[dict[str, str]] | None = None,
) -> None:
    sample_rows = len(read_csv(input_path))
    sample_images = count_images_in_csv(input_path)
    test_path = PROJECT_ROOT / "dataset/claims.csv"
    test_rows = len(read_csv(test_path)) if test_path.exists() else 0
    test_images = count_images_in_csv(test_path) if test_path.exists() else 0

    metric_lines = "\n".join(
        f"- `{field}` accuracy: {score:.3f}" for field, score in metrics.items()
    )
    if not metric_lines:
        metric_lines = "- No labeled expected output columns were present for metric comparison."
    mismatch_count = len(mismatches or [])
    mismatch_examples = "\n".join(
        "- Row {row_number}: fields `{mismatched_fields}`, expected status `{expected_claim_status}`, predicted `{predicted_claim_status}`.".format(
            **row
        )
        for row in (mismatches or [])[:8]
    )
    if not mismatch_examples:
        mismatch_examples = "- No mismatches found for the tracked fields."

    report = f"""# Evaluation Report

## Run Summary

- Model used: `{model}`
- Sample input: `{input_path}`
- Sample predictions: `{output_path}`
- Sample rows/model calls: approximately {sample_rows}
- Test rows/model calls: approximately {test_rows}
- Sample images processed: approximately {sample_images}
- Test images processed: approximately {test_images}

## Sample Metrics

{metric_lines}

## Error Analysis

- Rows with at least one tracked-field mismatch: {mismatch_count}
{mismatch_examples}

The prompt is calibrated to be conservative: supported requires a clear visual match, ordinary visible damage is usually low or medium rather than high, and missing-contents claims require enough visual context to verify absence rather than merely showing an open package.

## Token, Cost, and Latency Assumptions

- The pipeline uses one GPT-4o Vision call per claim row.
- Approximate text input per row: 1,000 to 2,000 tokens including claim text, history, evidence requirements, enum values, and instructions.
- Approximate image input varies by image count and resolution; this solution sends images with high detail because visual evidence is the primary source of truth.
- Approximate output per row: 150 to 300 tokens of strict JSON.
- Cost should be estimated from current OpenAI GPT-4o text and image pricing at run time. For this dataset, multiply per-row text/image cost by about {test_rows} test calls and {test_images} test images.
- Expected latency is commonly several seconds per row. Sequential processing of {test_rows} test rows may take a few minutes depending on model load and image sizes.

## TPM/RPM Considerations

- The default implementation processes sequentially, which is safer for take-home reproducibility and avoids unnecessary rate-limit pressure.
- For larger datasets, add a small bounded worker pool and throttle by both requests per minute and tokens per minute.
- If rate limits occur, the OpenAI client retries temporary failures with short backoff and then returns a safe manual-review fallback.

## Batching, Caching, and Retry Strategy

- Batching: one claim row per call, because each decision depends on a distinct conversation, object, history slice, checklist, and image set.
- Caching: production usage should cache by a stable hash of claim text, image file bytes or paths, model, and prompt version. This starter does not persist cache entries to avoid stale evidence decisions.
- Retry: limited retries are used for rate limits, temporary API failures, connection errors, and JSON parsing failures.
- Validation: all model outputs are normalized to allowed enums before CSV writing.

## Limitations and Failure Cases

- Visual decisions depend on image quality, angle, cropping, and model interpretation.
- Severity is approximate and should not be treated as a repair estimate.
- User history is only risk context and does not override clear image evidence.
- Missing, corrupted, or unreadable images are routed to `not_enough_information` and manual-review risk.
- Multilingual user claims are passed directly to GPT-4o; ambiguous phrasing can still require manual review.
"""
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")


def run_evaluation(input_path: str | Path, output_path: str | Path, model: str) -> dict[str, float]:
    predicted_df = run_pipeline(input_path=input_path, output_path=output_path, model=model)
    expected_df = read_csv(input_path)

    metrics = compute_metrics(expected_df, predicted_df)
    mismatches = find_mismatches(expected_df, predicted_df)
    error_analysis_path = PROJECT_ROOT / "evaluation/sample_error_analysis.csv"
    pd.DataFrame(mismatches).to_csv(error_analysis_path, index=False)
    print("Summary metrics:")
    if metrics:
        for field, score in metrics.items():
            print(f"  {field}: {score:.3f}")
    else:
        print("  No expected output columns found.")
    print(f"Error analysis path: {error_analysis_path}")

    write_evaluation_report(
        report_path=PROJECT_ROOT / "evaluation/evaluation_report.md",
        model=model,
        input_path=input_path,
        output_path=output_path,
        metrics=metrics,
        mismatches=mismatches,
    )
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate sample claim predictions.")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "dataset/sample_claims.csv"))
    parser.add_argument(
        "--output", default=str(PROJECT_ROOT / "evaluation/sample_eval_results.csv")
    )
    parser.add_argument("--model", default="gpt-4o")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_evaluation(args.input, args.output, args.model)


if __name__ == "__main__":
    main()
