# Evaluation Report

## Run Summary

- Model used: `gpt-4o`
- Sample input: `dataset/sample_claims.csv`
- Sample predictions: `evaluation/sample_eval_results.csv`
- Sample rows/model calls: approximately 20
- Test rows/model calls: approximately 44
- Sample images processed: approximately 29
- Test images processed: approximately 82

## Sample Metrics

- `claim_status` accuracy: 0.800
- `issue_type` accuracy: 0.800
- `object_part` accuracy: 0.950
- `evidence_standard_met` accuracy: 0.950
- `valid_image` accuracy: 0.950
- `severity` accuracy: 0.800

## Error Analysis

- Rows with at least one tracked-field mismatch: 5
- Row 5: fields `claim_status;issue_type;severity`, expected status `contradicted`, predicted `supported`.
- Row 6: fields `valid_image`, expected status `not_enough_information`, predicted `not_enough_information`.
- Row 8: fields `claim_status;issue_type;object_part;evidence_standard_met;severity`, expected status `contradicted`, predicted `not_enough_information`.
- Row 14: fields `claim_status;issue_type;severity`, expected status `contradicted`, predicted `supported`.
- Row 20: fields `claim_status;issue_type;severity`, expected status `contradicted`, predicted `supported`.

The prompt is calibrated to be conservative: supported requires a clear visual match, ordinary visible damage is usually low or medium rather than high, and missing-contents claims require enough visual context to verify absence rather than merely showing an open package.

## Token, Cost, and Latency Assumptions

- The pipeline uses one GPT-4o Vision call per claim row.
- Approximate text input per row: 1,000 to 2,000 tokens including claim text, history, evidence requirements, enum values, and instructions.
- Approximate image input varies by image count and resolution; this solution sends images with high detail because visual evidence is the primary source of truth.
- Approximate output per row: 150 to 300 tokens of strict JSON.
- Cost should be estimated from current OpenAI GPT-4o text and image pricing at run time. For this dataset, multiply per-row text/image cost by about 44 test calls and 82 test images.
- Expected latency is commonly several seconds per row. Sequential processing of 44 test rows may take a few minutes depending on model load and image sizes.

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
