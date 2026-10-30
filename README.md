# PS 80 — SQL Error Explainer & Fixer

Local Gemma inference via LM Studio, a Streamlit SQL repair demo, SQLite safety
controls, and a reproducible benchmark with CSV metrics.

## 1. Prerequisites

- Python 3.10+
- LM Studio installed
- A Gemma 3 4B model loaded in LM Studio
- LM Studio local server enabled (default base URL: `http://localhost:1234/v1`)

By default, this project uses the local OpenAI-compatible interface exposed by
LM Studio and sends prompts to `localhost`. If you change `LM_STUDIO_BASE_URL`,
requests go to that configured server. Confirm with your faculty that model
access is allowed under the project rules.

## 2. Install

Open a terminal in this folder:

```bash
python -m venv .venv
```

Windows:
```powershell
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
```

## 3. Configure LM Studio

1. Load Gemma 3 4B.
2. Open LM Studio's Developer / Local Server panel and start the server.
3. Confirm the server base URL (usually `http://localhost:1234/v1`).
4. If the server requires a model identifier, set `LM_STUDIO_MODEL` to the identifier shown by LM Studio.

Windows PowerShell example:
```powershell
$env:LM_STUDIO_MODEL="gemma-3-4b"
$env:LM_STUDIO_BASE_URL="http://localhost:1234/v1"
```

If the model name is different in your LM Studio, use that exact model identifier.
Set `LM_STUDIO_API_KEY` if your local server requires a specific key. The default
is `lm-studio`.

## 4. Run tests

From this directory, with the virtual environment activated:

```bash
python -m unittest discover -v
```

## 5. Run the benchmark

```bash
python evaluator.py
```

The benchmark runs each case against a generated database under `results/`.
It reads the checked-in `test_cases.json` without overwriting it, queries the
local model once per test case, and saves:

- `results/detailed_results.csv` — per-case model output and evaluation
- `results/summary_metrics.csv` — overall metrics
- `results/category_metrics.csv` — category-wise metrics
- `results/benchmark.db` — disposable synthetic database used for evaluation

Do not report placeholder or anticipated values. Use the actual output from your run.

## 6. Launch interactive demo

```bash
streamlit run app.py
```

The demo keeps a repair in session state so you can inspect the suggestion and
execute it in a separate step. Execution is limited to the synthetic sample
database; the demo does not recreate or overwrite the checked-in benchmark DB.

## 7. Metrics

- Result-match accuracy: output rows match expected rows, ignoring row order but preserving value and column order.
- Execution success: query runs successfully in the isolated sample DB.
- Exact-match accuracy: normalized generated SQL equals the reference SQL. This is strict; valid alternative SQL may fail exact match.
- Explanation rubric score: an initial keyword-based proxy. It is not a validated semantic metric. For a defensible jury result, manually score explanations with a rubric and report the method.
- Safety violations: proposed SQL failed the conservative read-only checks. SQLite authorizer restrictions, read-only connections, result limits, and query timeouts are defense in depth, not a production security boundary.
- Latency: time for one model request, including local inference and HTTP overhead.

## 8. Important limitations and evaluation validity

- Starter benchmark contains only seven cases, which is enough to test the pipeline, not to claim general model performance. Expand to at least 50 diverse, manually verified cases before presenting robust performance claims.
- The benchmark's reference SQL and expected results are hand-authored. Verify every case yourself.
- SQLite is the only executed dialect. Queries for PostgreSQL, MySQL, etc. need their own compatible test database.
- The benchmark checks a repair's exact SQL match as well as result match. Exact match is strict; equivalent SQL can produce a correct result but not match the reference text.
- The executor opens SQLite in read-only mode, allows only query/read actions through SQLite's authorizer, caps results at 1,000 rows, and interrupts long-running queries after two seconds. These are demo safeguards, not a production security boundary. Use a disposable database and manual review; never point this demo at real or production data.
- Result matching ignores row order. If ordering is semantically important, encode ordering in the query and expected result.
- Re-run each model/test combination consistently; record model version, quantization, hardware, and parameters in your report.
