# Future Work for Project Extension

This document summarizes concrete, incremental ways to extend the clinical trials MCP server project, based on recent discussion:

## 1. New MCP Methods
- **filter_trials**: Accept `mutation`, `phase`, `status`, `country`, `max_rank` → return filtered list (reuse `query_clinical_trials` + simple post-filter).
- **get_trial_details**: Accept `nct_id` → fetch a single record, run a focused summary.
- **list_common_mutations**: Expose the curated resources folder so Claude can discover what’s available.
  - _Where_: add cases in `clinicaltrials_mcp_server.process_request` (and/or `simple_mcp_server`).
  - _Tests_: add to `tests/test_filter.py`, `tests/test_details.py`.

## 2. Query-side Enhancements (`clinicaltrials/query.py`)
- Support pagination: return iterator/generator, so callers can stream large result sets.
- Parallel requests: use `httpx` + `asyncio.gather` to fetch multiple pages concurrently.
- Basic in-memory cache (LRU via `functools.lru_cache`) to avoid repeat API hits.

## 3. Summarization Improvements (`llm/summarize.py`)
- Chunk long study lists into batches; call LLM per batch; then run a “reduce” pass—classic map-reduce pattern.
- Add highlighting: pass in a style flag (markdown/plain).
- Surface uncertainty: if trial count > N, include an “out-of-scope omitted” notice.

## 4. Multi-source Data Node
- Create `pubmed/query.py` + `llm/summarize_pubmed.py` to pull publications for the same mutation.
- Combine results in a new flow (`flow.py`): Query trials ➜ Query PubMed ➜ Summarize each ➜ Merge ➜ Return.

## 5. Reliability & Ops
- Add structured logging (`structlog`) and rotate to `~/.cache/clinicaltrials-mcp/logs`.
- Graceful shutdown already handled; also expose `/healthz` if you later dockerize.

## 6. CLI / Notebook Usage
- Tiny wrapper: `python -m clinicaltrials.cli "EGFR L858R" --phase=3` so the code is useful outside Claude.

## 7. Packaging & Distribution
- `pyproject.toml` + `__version__` in `clinicaltrials/__init__.py`, then `pip install -e .` for contributors.
- Publish as a “tool” on the MCP registry when ready.

## 8. Better Tests / CI
- Mock requests with `responses` to make tests deterministic.
- GitHub Action: lint (ruff or flake8), run tests, build package.

---

Each of these steps is independent and can be merged progressively. Choose any subset to begin, and further details or code sketches can be provided as needed.
