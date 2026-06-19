"""Command-line batch runner for Multi-Modal Evidence Review."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from llm_client import review_claim_with_images
from schemas import OUTPUT_COLUMNS, normalize_model_output
from utils import (
    build_output_row,
    extract_image_id,
    filter_evidence_requirements,
    filter_user_history,
    parse_image_paths,
    read_csv,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_pipeline(
    input_path: str | Path,
    output_path: str | Path,
    model: str = "gpt-4o",
    user_history_path: str | Path = PROJECT_ROOT / "dataset/user_history.csv",
    evidence_requirements_path: str | Path = PROJECT_ROOT / "dataset/evidence_requirements.csv",
) -> pd.DataFrame:
    claims_df = read_csv(input_path)
    user_history_df = read_csv(user_history_path)
    evidence_requirements_df = read_csv(evidence_requirements_path)

    total_rows = len(claims_df)
    print(f"Total rows: {total_rows}")
    output_rows = []
    output_path = Path(output_path)
    partial_output_path = output_path.with_suffix(output_path.suffix + ".partial")

    for index, claim_row in tqdm(
        list(claims_df.iterrows()), total=total_rows, desc="Reviewing claims"
    ):
        row_dict = claim_row.to_dict()
        image_paths = parse_image_paths(row_dict.get("image_paths", ""))
        image_ids = [extract_image_id(path) for path in image_paths]
        print(f"Current row: {index + 1}/{total_rows} | images: {len(image_paths)}")

        user_history = filter_user_history(user_history_df, row_dict.get("user_id", ""))
        evidence_requirements = filter_evidence_requirements(
            evidence_requirements_df, row_dict.get("claim_object", "")
        )

        raw_output = review_claim_with_images(
            claim_row=row_dict,
            image_paths=image_paths,
            image_ids=image_ids,
            user_history=user_history,
            evidence_requirements=evidence_requirements,
            model=model,
        )
        normalized = normalize_model_output(
            raw_output,
            claim_object=row_dict.get("claim_object", ""),
            image_ids=image_ids,
            user_history=user_history,
            claim_row=row_dict,
        )
        output_rows.append(build_output_row(row_dict, normalized))
        pd.DataFrame(output_rows, columns=OUTPUT_COLUMNS).to_csv(
            partial_output_path, index=False
        )

    output_df = pd.DataFrame(output_rows, columns=OUTPUT_COLUMNS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_path, index=False)
    if partial_output_path.exists():
        partial_output_path.unlink()
    print(f"Output path: {output_path}")
    return output_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multimodal evidence review.")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "dataset/claims.csv"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "output.csv"))
    parser.add_argument("--model", default="gpt-4o")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_pipeline(args.input, args.output, args.model)


if __name__ == "__main__":
    main()
