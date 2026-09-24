# PROGRESS

Iteration log for the Production RAG Agent build, per the build spec's §0.5 loop.
Every entry is appended, never edited after the fact.

### Phase 0 · Iteration 1 · 2026-09-23

**Changed:**
- Imported the baseline zip into a local git repo (no remote), initial commit `chore: import baseline`.
- Backend root cleanup (0.1):
  - Moved binary fixtures (`test.pdf`, `new_test.pdf`, `debug_test.pdf`, `upload_test.pdf`,
    `test_large.txt`, `test_duplicate.txt`) into `backend/tests/fixtures/`.
  - Moved audit/ops scripts (`audit_tests.py`, `comprehensive_audit.py`, `generate_evidence.py`,
    `clean_orphans.py`, `upload.py`, `test_all.sh`, `test_duplicate.ps1`, `generate_test_files.py`)
    into `backend/scripts/`.
  - Deleted `backend/debug/` (2 throwaway debug scripts) and `backend/final_audit_report.md`
    (stale one-off report, not the ongoing log this file replaces).
  - Deleted `backend/test_memory_debug.py` — a strict subset of `test_memory.py` (same request,
    no assertions, just debug prints); nothing was lost by dropping it.
  - Converted loose root test scripts into proper pytest modules under `backend/tests/`:
    - `test_all.py` + `test_all_formats.py` → `tests/test_upload_formats.py`
      (parametrized, in-memory fixtures, real assertions, `@pytest.mark.integration`).
    - `test_concurrent_dup.py` → `tests/test_concurrent_dup.py` (asyncio.gather + assert on
      status counts instead of print).
    - Still pending: `test_duplicate.py` (root) merge into existing `tests/test_duplicate.py`
      (name collision — both test duplicate detection, so this is a merge not a move),
      `test_memory.py`, `test_retrieval.py` + `test_retrieval_2.py` (merge — same target,
      different iterations), `test_zip_bomb.py` (convert to a real unit test against
      `DocxParser` directly, no live server needed).

**Gates:** lint — not yet run (no `ruff`/`mypy` invocation this iteration). unit/integration —
not yet run. build — not applicable yet (frontend untouched). smoke — not yet run.

**Blockers hit this iteration:**
1. **Docker is not installed** on this machine (`docker`, `docker compose` both absent from PATH
   and no Docker Desktop service found). Phase 0.2 ("bring up Postgres, Qdrant and the API")
   and the Phase 0.3 exit condition ("the app still boots and answers a query") cannot be
   verified until Docker is available.
2. **No `GOOGLE_API_KEY`** is set in `backend/.env` yet (file doesn't exist — only
   `backend/.env.example` does). Embeddings, generation, and every eval from Phase 1 onward
   need a real key. Per the spec's own ground rules ("Stop and ask if a phase needs a paid
   API key that isn't already in `.env.example`") this is a pause point — the owner needs to
   supply the key.
3. The scratch working directory Claude Code started in had a path too deep for Windows'
   `MAX_PATH`, which broke `git add` on a nested alembic migration filename. Relocated the
   whole project to `C:\Users\DELL\Downloads\Production-RAG-Agent` before continuing — noted
   here in case it recurs.

**Diagnosis:** not a code defect — these are environment/credential prerequisites the spec
itself calls out as owner-supplied (§0 "Environment", §"Pause points").

**Next:** finish converting the remaining loose test scripts, then stop Phase 0 at the
verification step (0.2) until Docker + `GOOGLE_API_KEY` are available, per the spec's own
pause-point rule rather than skipping the gate.

### Phase 0 · Iteration 2 · 2026-09-23

**Changed:**
- Converted the remaining loose root scripts: `test_memory.py` → `tests/test_memory.py`
  (asserts the follow-up answer actually recalls the name from turn 1, not just that the
  stream completes), `test_retrieval.py` + `test_retrieval_2.py` → a single
  `tests/test_retrieval.py` (parametrized over 3 queries, asserts non-empty answer + at
  least one cited source — dropped the "_2" duplicate-target naming), `test_zip_bomb.py` →
  `tests/test_zip_bomb.py` (real unit test, no live services needed — imports `DocxParser`
  directly; scaled the payload down from 500MB to 50MB decompressed to keep it CI-fast).
- Dropped root `test_duplicate.py` outright (see iteration 1 diagnosis — redundant with the
  existing `tests/test_duplicate.py`).
- Added `backend/pytest.ini` (`asyncio_mode = auto`, registers the `integration` marker) and
  `backend/requirements-dev.txt` (pytest, pytest-asyncio, httpx, ruff, mypy).
- `backend/` root now contains only `app/, alembic/, tests/, scripts/, docker-compose*.yml,
  Dockerfile, alembic.ini, requirements*.txt, test_files/` (pre-existing fixtures dir, left
  untouched — not in the spec's explicit move list).

**Gates:** still not run — `ruff`, `mypy`, and `pytest` all need `pip install -r
requirements-dev.txt` first, which pulls `paddlepaddle`/`paddleocr` (large, unverified on
this machine's Python 3.13 + Windows combination). Deferred to the 0.2 verification step
alongside Docker, so the environment is set up once rather than twice.

**Threshold:** NOT MET — Phase 0's exit condition ("Gates 1–6 pass; backend root clean; app
boots and answers") only has "backend root clean" satisfied. Stopping here per the pause-point
rule (blocked on Docker + `GOOGLE_API_KEY`, both owner-supplied) rather than tagging
`phase-0-complete` prematurely.

**Next:** once Docker Desktop is installed and `backend/.env` has a real `GOOGLE_API_KEY`,
resume at 0.2: `docker compose up -d`, `pip install -r backend/requirements-dev.txt`, run the
full gate list, upload every fixture format, run one query end to end, record documents
indexed / chunks created / median query latency, then tag `phase-0-complete` and move to
Phase 1 (eval harness).

### Phase 0 · Iteration 3 · 2026-09-23

**Changed:**
- Docker Desktop installed and started; owner supplied a working `GOOGLE_API_KEY` (verified
  directly against the Gemini API's `/v1beta/models` endpoint before trusting it).
- `docker compose up -d --build` brought up Postgres (healthy), Qdrant, and the FastAPI
  backend (health check passing, `/health` reports gemini/postgres/qdrant all connected).
- **Smoke gate passed**: uploaded all 7 fixture formats (pdf, docx, pptx, xlsx, csv, txt, md) —
  each indexed with 1 page / 1 chunk; re-uploading the same PDF correctly returned
  `already_exists`. Ran 3 queries end-to-end; each streamed a cited answer referencing the
  correct source files. Median query latency ~8.7s (6.0s / 8.7s / 15.2s) — first-query
  cold-start likely explains the high end; worth re-measuring once Phase 1's eval harness
  gives a real sample size instead of 3 manual queries.
- **Lint gate passed**: `ruff check backend/` was 128 errors under ruff's unpinned defaults
  (no `pyproject.toml` existed). Added `backend/pyproject.toml` selecting `[E, F, I]` at
  `line-length=120` — a standard baseline, not a weakened one — which cut it to 48 real
  findings; auto-fixed 37 (import sorting, unused imports), manually fixed the remaining 11
  in `app/` with zero behaviour change (dead-variable removal, explicit re-export syntax,
  line wraps), then found and fixed 16 more of the same kind in `scripts/` and `tests/`.
  `ruff check backend/` now passes clean.
- **Types gate in progress**: `mypy backend/app` found 22 errors in 5 files — real
  pre-existing issues, not lint noise: unguarded `Optional[Document]` attribute access in
  `document_service.py` (11 occurrences), two missing required args to `DocumentResult`,
  a wrong exception attribute in `embedding_service.py` (`GoogleAPIError` has no `.code`),
  a `list + str` type mismatch in `rag_graph.py`, and a missing var annotation in
  `chunker.py`. Not yet fixed — paused here to check in with the owner given session cost.

**Incident:** the app's session-directory-move file sync (from earlier when this session
relocated out of the scratch workspace) silently restored every file Phase 0.1 had already
deleted/moved, since it only fills in files missing at the destination and never overwrites.
Caught via `git status` showing ~25 unexpected untracked files identical to the pre-cleanup
originals; deleted them again. No data was lost — `git status` is now clean of anything
unexpected. Lesson for future iterations: verify `git status` before each commit, not just
after big directory-tool operations.

**Gates:** lint ✓ · types (in progress, 22 known errors) · unit — not yet run · integration —
not yet run (needs the container rebuilt with the pyproject.toml + lint fixes first) · build —
not applicable yet (frontend untouched) · smoke ✓.

**Threshold:** NOT MET — 2 of 6 gates fully green.

**Next:** fix the 22 mypy errors (all real, no behaviour change required — they're narrowing
issues, not design flaws), rebuild the container, run the unit + integration pytest suites,
then tag `phase-0-complete`.

### Phase 0 · Iteration 4 · 2026-09-24

**Changed:**
- mypy: 22 → 0. Enabled the pydantic mypy plugin (fixes false "missing argument" errors on
  `Field(None, ...)` defaults); asserted the `doc is not None` invariant in
  `_process_single_file`; stopped reusing the `doc` name for a differently-typed value in the
  IntegrityError fallback; annotated `current_lines` and the health `overall` Literal; read
  `GoogleAPIError.code` via `getattr`; guarded AIMessage truncation on `str` content.
- Tests: `tests/test_upload.py` was a module-level script that opened `test.pdf` relative to the
  cwd — the Phase 0.1 fixture move broke it and it broke pytest collection; rewritten as a proper
  integration test. `test_memory.py` now stops at the SSE `[DONE]` sentinel. `test_concurrent_dup.py`
  uses unique content per run so it is repeatable.
- Pytest runs in a throwaway container from the same image with `backend/` mounted and the
  backend's network namespace shared (the runtime image only contains `app/` and `alembic/`).

**Finding (not fixed — Phase 0 allows no behaviour changes):** when 5 identical uploads race, all 5
report `completed` for the same document id: the IntegrityError fallback attaches every request to
the winner's row and each re-runs ingestion. No duplicate data (vector ids are deterministic, the
upsert is idempotent) but embedding work is repeated up to N times. Belongs in "Known limitations".

**Baseline (0.2):** 7 fixture formats indexed, 1 page / 1 chunk each; re-uploading the same PDF returned
`already_exists`; 3 manual queries streamed cited answers, latencies 6.0s / 8.7s / 15.2s (median 8.7s).
These 3 samples are replaced by real percentiles once the eval harness has a baseline.

**Gates:** lint ✓ · types ✓ (55 files) · unit ✓ (1) · integration ✓ (13) · frontend build ✓
(`next build`, 9 routes) · smoke ✓.

**Threshold:** MET. Tagged `phase-0-complete`.

### Phase 1 · Iteration 1 · 2026-09-24

**Changed:**
- Built the harness under `backend/evals/`: synthetic corpus with look-alike distractors
  (`corpus_data.py`, `build_corpus.py`), `golden_v1.jsonl` (62 cases: 17 factual_lookup, 8 multi_hop,
  12 exact_term, 10 follow_up, 8 unanswerable, 7 chitchat), retrieval metrics (pure), generation
  judges (Gemini, temperature 0, hash-cached), `setup_corpus.py` (index through the API, derive
  `relevant_chunk_ids` from real chunks), `run_eval.py` (real `/query`, `--compare`, `--fail-under`,
  `--limit`, `--no-judge`).
- Ground truth is by construction: every case carries `evidence` strings and a test proves each exists
  in exactly one document. Chunk ids are derived, so re-running `setup_corpus` re-labels after any
  chunking change.
- Additive backend changes for testability: SSE `sources` now carry the deterministic `chunk_id`, and
  `/query` accepts an optional stateless `history` (used instead of stored history when no
  `conversation_id` is given) so follow-up evals inject the dataset's history deterministically.

**Eval (retrieval-only probe, 22-chunk corpus, `evals/results/probe_20260924_044901.json`):**
recall@5 0.978 | MRR 0.869 | nDCG@5 0.895 | hit-rate@5 0.978 | precision@5 0.209. Chitchat cases
retrieved on 5 of 5 scored (the baseline has no router).

**Threshold:** NOT MET.
**Diagnosis:**
1. *Golden set too easy.* recall@5 0.978 > the spec's 0.9 ceiling: the corpus is 22 chunks, so the
   top 5 is close to "retrieve everything". This is the spec's pause point; remedy applied — added 24
   generated products, 15 resumes and a second price list, all seeded and deterministic, with
   near-identical identifiers (error codes, SKUs, names) that never collide with gold evidence (the
   dataset test enforces it). Baseline must be re-measured on the hardened corpus.
2. *Gemini free-tier quota is far below what the loop needs.* The key allows 5 requests/minute and
   20 requests/day per model. A full judged run needs ~60 generation calls plus ~120 judge calls, so
   it cannot complete on this key even once; 58 of 62 cases hit 429 on generation. Retrieval still
   works (sources arrive before generation), so retrieval metrics are measurable; judged metrics
   (faithfulness, citation accuracy, refusal correctness) are not until the quota changes.

**Next:** re-index the hardened corpus, record the retrieval baseline, then continue with the phases
whose exit gates are retrieval metrics (2, 3) while flagging the quota blocker for the owner.
