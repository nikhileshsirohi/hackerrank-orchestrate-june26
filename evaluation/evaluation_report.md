# Multi-Modal Evidence Review Evaluation Report

## Hackathon Submission Summary

This solution is a Python batch pipeline for the HackerRank Orchestrate Multi-Modal Evidence Review challenge. It reads claim rows, sends one GPT-4o Vision request per claim, validates the structured JSON response, and writes the required CSV output schema.

- Final model: `gpt-4o`
- Sample evaluation input: `dataset/sample_claims.csv`
- Sample evaluation output: `evaluation/sample_eval_results.csv`
- Final prediction input: `dataset/claims.csv`
- Final prediction output: `output.csv`
- Error analysis file: `evaluation/sample_error_analysis.csv`
- Final `output.csv` validation: 44 rows, 14 required columns, 0 schema/enum/fallback errors

## Sample Evaluation Metrics

The labeled `dataset/sample_claims.csv` file was used as a practice/evaluation set. The evaluator compares model predictions against expected sample labels for the most important fields.

- `claim_status` accuracy: 0.800
- `issue_type` accuracy: 0.800
- `object_part` accuracy: 0.950
- `evidence_standard_met` accuracy: 0.950
- `valid_image` accuracy: 0.950
- `severity` accuracy: 0.800

## Error Analysis

The final sample run had 5 rows with at least one tracked-field mismatch.

- Row 5: expected `contradicted`, predicted `supported`; bumper damage was judged more generously by the model than the label.
- Row 6: only `valid_image` differed; both expected and predicted `not_enough_information`.
- Row 8: expected `contradicted`, predicted `not_enough_information`; the model was conservative because the claimed hood scratch was not visible.
- Row 14: expected `contradicted`, predicted `supported`; the model interpreted visible trackpad-area marks as physical damage.
- Row 20: expected `contradicted`, predicted `supported`; the model interpreted the seal as torn/open.

The error patterns show the remaining risk: borderline visual evidence can be interpreted differently from the sample label. The prompt and post-processing were tuned to be conservative, but the solution avoids hardcoding sample row answers.

## Final Output Distribution

Final `output.csv` contains 44 rows.

`claim_status`:

- `supported`: 20
- `contradicted`: 16
- `not_enough_information`: 8

`valid_image`:

- `true`: 38
- `false`: 6

`severity`:

- `medium`: 18
- `none`: 11
- `unknown`: 8
- `low`: 7

No final output row contains API fallback text such as `Automated review failed`, `BadRequestError`, or `OPENAI_API_KEY`.

## Model Calls And Images Processed

- Sample evaluation rows/model calls: 20
- Sample images processed: 29
- Final test rows/model calls: 44
- Final test images processed: 82
- Total calls for one full sample-plus-final run: 64
- Total images for one full sample-plus-final run: 111

The system intentionally uses one model call per claim row. This keeps each decision grounded in exactly one claim conversation, one object type, that user's risk history, matching evidence requirements, and the submitted images for that row.

## Prompt And Validation Strategy

Each model call includes:

- claim object
- user claim/conversation
- image IDs and normalized image data URLs
- matching user history
- matching evidence requirements
- allowed enum values
- strict JSON schema instructions

Images are treated as the primary source of truth. User history is risk context only and cannot override clear visual evidence.

Post-processing enforces:

- exact allowed enum values
- valid object parts for each object type
- `not_enough_information` fallback for invalid claim statuses
- `unknown` fallback for invalid issue types/object parts/severity
- semicolon-separated CSV values for `risk_flags` and `supporting_image_ids`
- `supporting_image_ids` restricted to IDs from the current row only
- no API failure text in final submission output

## Operational Analysis

### Token And Cost Assumptions

The pipeline sends one GPT-4o Vision request per row. Approximate usage per row:

- Text input: about 1,000 to 2,000 tokens for instructions, claim text, user history, evidence requirements, and allowed values.
- Image input: varies by image count and image dimensions. Images are converted into tokens by the OpenAI API.
- Output: about 150 to 300 tokens of JSON.

OpenAI's pricing page explains that images are converted into tokens and charged per token, and its pricing calculator includes `gpt-4o` image estimates. Using that pricing model, this hackathon dataset is small: 44 final calls and 82 final images. The expected cost is in the small-dataset range, but exact cost should be checked against current OpenAI pricing at run time because model and image-token pricing can change.

### Latency And Runtime

Observed per-row latency was usually a few seconds. A full 44-row final run is expected to take several minutes when run sequentially, depending on OpenAI API latency and image sizes.

The implementation uses sequential processing for reliability and reproducibility. This is acceptable for 44 rows. For larger datasets, a bounded worker pool could reduce runtime.

### TPM/RPM Considerations

Sequential processing keeps requests per minute low and avoids most rate-limit pressure. For larger production runs:

- throttle by both requests per minute and tokens per minute
- cap concurrent image requests
- use exponential backoff for 429/5xx/timeouts
- consider the Batch API for non-urgent processing

### Retry And Timeout Strategy

The OpenAI client uses:

- limited application-level retries
- a 75-second request timeout
- retry handling for rate limits, timeouts, temporary server errors, connection errors, and JSON parsing failures
- safe fallback output if all retries fail

During final validation, earlier `BadRequestError` fallback rows were removed by normalizing images through Pillow into standard RGB JPEG data URLs before sending them to GPT-4o.

### Caching Strategy

This submission does not persist a cache because the dataset is small and stale visual evidence decisions are risky. A production version should cache by:

- prompt version
- model name
- claim text hash
- image file hash
- evidence requirement version

Cached outputs should still pass the same schema validation before CSV writing.

## Limitations And Failure Cases

- Borderline visual evidence can be subjective, especially severity and contradiction/support decisions.
- Missing contents claims are hard to verify from images unless the package contents area is clearly shown.
- User history can add risk flags, but it should not decide claim status.
- Image quality problems such as blur, glare, cropping, or wrong angle can force `not_enough_information`.
- Multilingual claims are passed directly to GPT-4o; ambiguous wording can still lead to conservative decisions.
- The system is designed for batch evaluation, not real-time claim adjudication.

## Final Assessment

The final pipeline is runnable from the command line, uses GPT-4o Vision as the primary reviewer, validates all outputs against the challenge schema, and produces a submission-ready `output.csv`.

