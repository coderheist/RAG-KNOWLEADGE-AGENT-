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
