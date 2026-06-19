# Multi-Modal Evidence Review

This repository contains a runnable Python batch pipeline for the HackerRank Orchestrate damage-claim evidence review assignment.

The system reads claim rows from CSV, sends each claim and its submitted images to GPT-4o Vision, validates the model's structured JSON output against the required enums, and writes a submission-ready `output.csv`.

## What The Solution Does

- Reads `dataset/claims.csv` or `dataset/sample_claims.csv`.
- Uses `claim_object`, `user_claim`, submitted images, user history, and evidence requirements.
- Treats images as the primary source of truth.
- Uses `dataset/user_history.csv` only for risk context.
- Uses `dataset/evidence_requirements.csv` as the minimum evidence checklist.
- Produces exactly the required output columns in the required order.
- Evaluates predictions on labeled sample rows when expected columns are present.

## Project Layout

```text
.
├── dataset/
├── src/
│   ├── main.py
│   ├── llm_client.py
│   ├── prompts.py
│   ├── schemas.py
│   ├── utils.py
│   └── evaluator.py
├── code/
│   ├── main.py
│   └── evaluation/main.py
├── evaluation/
│   ├── evaluation_report.md
│   ├── sample_error_analysis.csv
│   └── sample_eval_results.csv
├── requirements.txt
├── README.md
├── chat_transcript.txt
└── output.csv
```

`code/` contains compatibility wrappers for the starter repository entry points. The main implementation lives in `src/`.

## Install Dependencies

Use Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Set The API Key

The OpenAI key is read from the environment only.

```bash
export OPENAI_API_KEY="your_api_key_here"
```

You can also create a local `.env` file:

```text
OPENAI_API_KEY=your_api_key_here
```

Do not commit `.env`.

## Run Sample Evaluation

```bash
python src/evaluator.py --input dataset/sample_claims.csv --output evaluation/sample_eval_results.csv --model gpt-4o
```

This produces:

- `evaluation/sample_eval_results.csv`
- `evaluation/sample_error_analysis.csv`
- `evaluation/evaluation_report.md`
- printed accuracy metrics for available labeled fields

Latest sample metrics from the final run:

```text
claim_status: 0.800
issue_type: 0.800
object_part: 0.950
evidence_standard_met: 0.950
valid_image: 0.950
severity: 0.800
```

Compatibility entry point:

```bash
python code/evaluation/main.py --input dataset/sample_claims.csv --output evaluation/sample_eval_results.csv --model gpt-4o
```

## Generate Final Output

```bash
python src/main.py --input dataset/claims.csv --output output.csv --model gpt-4o
```

This produces `output.csv` with the required columns:

```text
user_id,image_paths,user_claim,claim_object,evidence_standard_met,evidence_standard_met_reason,risk_flags,issue_type,object_part,claim_status,claim_status_justification,supporting_image_ids,valid_image,severity
```

Compatibility entry point:

```bash
python code/main.py --input dataset/claims.csv --output output.csv --model gpt-4o
```

Final `output.csv` validation from the submitted run:

```text
rows: 44
required columns: 14
schema/enum/fallback errors: 0
```

## Design Explanation

The pipeline uses one OpenAI Vision call per claim row. Each request includes:

- claim object
- user claim conversation
- image IDs and image data
- relevant user history for that user
- evidence requirements matching the object plus global requirements
- allowed enum values
- strict JSON schema instructions

Before images are sent to the model, they are normalized through Pillow into standard RGB JPEG data URLs. This avoids API failures from unusual source image encodings and keeps the input format consistent.

The model is asked to decide whether image evidence supports, contradicts, or is insufficient for the claim. The code then normalizes every model response before writing CSV.

Invalid model enum values are replaced with safe fallbacks:

- invalid `claim_status` -> `not_enough_information`
- invalid `issue_type` -> `unknown`
- invalid `object_part` -> `unknown`
- invalid `severity` -> `unknown`
- empty `risk_flags` -> `none`
- empty `supporting_image_ids` -> `none`

## Important Behavior Rules

- User history never decides claim status by itself.
- User history can only add `user_history_risk` and `manual_review_required`.
- If no image is usable, the system returns `valid_image=false`, `evidence_standard_met=false`, `claim_status=not_enough_information`, `supporting_image_ids=none`, and `severity=unknown`.
- If the relevant part is visible and claimed damage is absent, the system should return `contradicted`, `issue_type=none`, and `severity=none`.
- If claimed damage is visible and matches the claim, the system should return `supported`.
- Semicolon-separated CSV output is used for `risk_flags` and `supporting_image_ids`.

## Operational Considerations

- The default runner is sequential to keep rate-limit behavior simple and reproducible.
- Retry logic handles rate limits, temporary API failures, timeouts, connection errors, and JSON parsing failures.
- OpenAI requests use a 75-second timeout so a stalled row does not block the run indefinitely.
- While processing, the runner writes `output.csv.partial` after each completed row. At the end, it writes final `output.csv` and removes the partial file.
- If all retries fail, the row receives a safe manual-review fallback.
- For larger datasets, add persistent caching keyed by prompt version, model, claim text, and image hashes.
- For higher throughput, add bounded concurrency with RPM/TPM throttling.
- Cost depends on current OpenAI GPT-4o text and image pricing, image resolution, and number of images per claim.

## Submission Files

Upload:

- `output.csv`
- `chat_transcript.txt`
- `code.zip`

Recommended `code.zip` contents:

- `src/`
- `code/`
- `evaluation/`
- `README.md`
- `requirements.txt`
- `problem_statement.md`

Exclude local/generated environment artifacts:

- `.venv/`
- `__pycache__/`
- `.DS_Store`
- `.env`

## Assumptions

- CSV image paths beginning with `images/` are resolved under `dataset/images/`.
- Image IDs are filenames without extensions, such as `img_1`.
- The expected object types are `car`, `laptop`, and `package`.
- The OpenAI API is available at runtime for real predictions.
- If the OpenAI package or API key is unavailable, the code returns safe fallback rows so the pipeline remains structurally runnable, but those fallback rows are not useful final predictions.
