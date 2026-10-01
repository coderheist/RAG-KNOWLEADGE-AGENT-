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

### Phase 1 · Iteration 2 · 2026-09-24

**Changed:**
- Quotas are per model. `gemini-3.5-flash` (the app's model) had its 20/day spent, but
  `gemini-flash-lite-latest` still had quota, so the eval loop now uses it for generation and judging
  (`GEMINI_MODEL` in the local, gitignored `backend/.env`; judge default via `EVAL_JUDGE_MODEL`).
  `gemini-2.5-flash`, `gemini-2.5-flash-lite` and `gemini-2.0-flash` all return 404 "no longer available
  to new users" on this account, so the spec's `QUERY_REWRITE_MODEL=gemini-2.0-flash` and this repo's
  `.env.example` model are invalid here; the rewrite default is now `gemini-flash-lite-latest`.
- Hardened corpus indexed (~90 chunks); `relevant_chunk_ids` re-derived for all 47 answerable cases.
- First full judged run crashed 20 minutes in: the citation judge returned a bare JSON list and an
  uncaught `AttributeError` aborted the whole run. Fixed both the parser (accepts either shape) and the
  runner (a judge failure now records `judge_error` for that case and the run continues).
- Added the runner flags CI needs (`--max-regression`, `--markdown-out`) and the two workflows
  (`ci.yml`: lint, types, unit tests, frontend build; `eval.yml`: 20-case stratified smoke eval vs a
  committed reference, PR comment). They have not run: nothing is pushed until the owner confirms.

**Eval:** `backend/evals/results/baseline_20260924_052025.json` — dense-only, no rewrite, ~90-chunk corpus,
62 cases, 0 errors, 1 judge error.
recall@5 0.745 | MRR 0.670 | nDCG@5 0.687 | precision@5 0.162 | faithfulness 0.967 |
answer relevance 0.877 | context precision 0.388 | citation accuracy 0.700 | refusal correctness 0.787 |
p50 latency 3.9 s. By category, recall@5: factual 1.000, multi_hop 1.000, exact_term 0.583,
follow_up 0.300. Chitchat: 2 of 7 cases already retrieve nothing (score floor), the rest do.

**Threshold:** MET — harness runs end to end on all golden cases, baseline written, no NaN or
zero-variance warnings. Recall 0.745 is well under the 0.9 "too easy" ceiling.
**Not verifiable locally:** "CI runs on every PR and shows a green check" (definition of done 1.5) —
needs the repo on GitHub, which the spec defers to the end. `ci_reference_*.json` (the 20-case reference
the eval workflow compares against) still has to be generated with `--limit 20 --tag ci_reference`.
Tagged `phase-1-complete`.

**Next:** Phase 2 — measure query rewriting on the follow_up subset with the flag off vs on.

### Phase 2 · Iteration 1 · 2026-09-24

**Changed:** `rewrite_query` graph node before `retrieve` (`app/services/query_rewriter.py`): no history →
passthrough with no LLM call; otherwise one Gemini call (temperature 0, small output cap, last 3 turns) to
produce a standalone query, guarded against empty / multi-line / preamble / overlong output and falling back
to the original query on any failure. The SDK is called directly, not through LangChain: inside the graph a
LangChain chat model emits `on_chat_model_stream` events that would have leaked into the user-facing answer
stream, and the stream loop is now also restricted to the `generate` node. A `query_rewrite` SSE event
reports what was searched. Flags: `ENABLE_QUERY_REWRITE`, `QUERY_REWRITE_MODEL`,
`QUERY_REWRITE_HISTORY_TURNS`, `QUERY_REWRITE_MAX_TOKENS`.
Guard detail: the spec's "longer than ~3x the original" rule would reject the very rewrites this feature exists
for ("his skills?" → "What are Marcus Bell's technical skills?" is 3.5x), so the limit is
`max(3x, 200 chars)`.

**Eval** (retrieval-only, 62 cases, `rc_dense_*.json` vs `rc_dense_rewrite_*.json`, same build):
follow_up recall@5 **0.300 → 1.000** (MRR 0.125 → 1.000); overall recall@5 0.745 → 0.894; factual,
multi_hop and exact_term unchanged; p50 retrieval latency 0.82 s → 0.90 s (only follow-ups pay for the
extra LLM call). The dense control run reproduces the earlier judged baseline exactly (0.745 / 0.670), so
the flag-off path is unchanged.

**Tests:** unit tests for empty history (no LLM call), pronoun resolution, six malformed-output cases, LLM
failure, identical rewrite, guard length rule, history formatting.
**Threshold:** MET on the first iteration (follow_up recall@5 +0.700 ≥ +0.15; no other category regressed
by more than 0.02). `ENABLE_QUERY_REWRITE` now defaults to true. Model note: the spec's default
`gemini-2.0-flash` is unavailable to this account; the default is `gemini-flash-lite-latest`.

### Phase 3 · Iteration 1 · 2026-09-24

**Changed:** BM25 sparse vectors (fastembed, local) beside the dense vector; dense and sparse searched
concurrently (`asyncio.gather`, top_k x 4 each) and merged with client-side Reciprocal Rank Fusion (k=60);
optional local cross-encoder rerank (`Xenova/ms-marco-MiniLM-L-6-v2`) behind a `Reranker` protocol mirroring
`embeddings/`; score-floor / gap logic applied after reranking on the dense cosine score, which is kept on the
chunk beside `rerank_score`. All behind `ENABLE_HYBRID_SEARCH` / `ENABLE_RERANKING`, default off.

**Two real bugs found while rolling out** (both fixed): (1) Qdrant cannot add a new vector name to an existing
collection, so `update_collection(sparse_vectors_config=...)` returned 400 and the API failed to start on any
existing deployment even with every flag off — startup now warns, and `scripts/reindex_hybrid.py` is a real
resumable migration into a new collection (dense vectors copied, BM25 computed locally, no embedding calls;
96 points migrated, 0 API calls). (2) Eval containers must run as root to write results — launch mistake, not code.

**Eval** (retrieval-only, 62 cases; recall@5 / MRR / p50 retrieval latency; exact_term recall):
dense 0.745 / 0.670 / 0.82 s / 0.583 · hybrid 0.787 / 0.748 / 0.78 s / 0.750 ·
dense+rerank 0.787 / 0.749 / 3.22 s / 0.750 · hybrid+rerank 0.830 / 0.802 / 4.43 s / 0.917.
**Latency diagnosis** (stage timings from the API log): search 14–100 ms, fusion ~20 ms, **rerank 1.3–1.7 s
for 20 candidates**, with 3–15 s spikes. Compute-bound cross-encoder inference over ~300-token chunks in a
3.8 GB Docker VM; not a bug. The reranker's cost is the whole story: hybrid retrieval itself is faster than
dense-only.
**Threshold (so far):** NOT MET for hybrid+rerank on latency (+3.6 s vs ≤ 300 ms). Rewriting must be on when
judging Phase 3 (it is the shipped Phase 2 default), so the combined configurations are being measured next.

### Phase 3 · Iteration 2 · 2026-09-25

**Diagnosis:** end-to-end p50 swings run to run because the query-embedding call to Gemini dominates and
varies, so it cannot resolve a 300 ms budget. Added per-stage server timings to the `sources` SSE event
(`timings_ms`: search / fuse / rerank), recorded by the runner (`latency_ms.stage_p50/p95`). This is also the
"latency per stage" the spec asks for and feeds Phase 6.
**Changed:** (1) rollout guard: `hybrid_enabled()` is true only if the flag is on AND the collection has the
sparse vector, so an older collection falls back to dense with a warning and ingestion never tries to attach
sparse vectors to a collection that cannot hold them; (2) stage timings; (3) `ENABLE_HYBRID_SEARCH` now
defaults to true. Reranking stays off by default (flag).
**Verified end to end:** ingested a new document with hybrid on — it received a sparse vector automatically
(97/97 points flagged) and a query for a made-up fault code retrieved it as the only source. The probe
document was then deleted (collection back to 96 points).

**Eval, rewriting ON** (retrieval-only, 62 cases; server-side stage p50):
| config | recall@5 | MRR | exact_term recall | stage p50 |
|---|---|---|---|---|
| dense (`rs_dense`) | 0.894 | 0.856 | 0.583 | search 8 ms |
| hybrid (`rs_hybrid`) | 0.936 | 0.926 | 0.750 | search 12 ms, fuse ~0 ms |
| hybrid + rerank, 10 candidates (`rc_full_rr10`) | 0.936 | 0.936 | 0.750 | end-to-end +1.1 s |
| hybrid + rerank, 20 candidates (`rs_hybrid_rr20`) | 0.979 | 0.979 | 0.917 | rerank 3,761 ms (p95 13.8 s) |
With rewriting OFF (`rc_*`): dense 0.745 / 0.670, hybrid 0.787 / 0.748, dense+rerank 0.787 / 0.749,
hybrid+rerank 0.830 / 0.802; exact_term recall 0.583 / 0.750 / 0.750 / 0.917. Exact-term and numeric cases
improve most, as predicted; follow-up cases are unaffected by retrieval changes (0.300 without rewriting).

**Threshold:** MET by **hybrid search alone**: recall@5 0.936 ≥ 0.85; MRR 0.926 ≥ 0.75; exact_term +0.167 ≥
+0.10; added retrieval latency ≈ +4 ms ≤ 300 ms. **Reranking is not adopted by default:** it adds
+0.043 recall and +0.053 MRR (mostly exact_term 0.75 → 0.917) for +3.7 s p50 (spec: "if reranking costs
more than ~150 ms, say so"), an order of magnitude over budget on this hardware (cross-encoder inference
over ~300-token chunks, 3.8 GB Docker VM). It remains one flag away: `ENABLE_RERANKING=true`. With 10
candidates the cost halves but the accuracy gain disappears. The 300 ms threshold was not changed.
**Not measured:** `INCLUDE_CHUNK_METADATA_IN_PROMPT` (heading/section in the context header) affects only
generation, so it needs judged runs; default stays off until then.

**Next:** Phase 4 — the agentic graph (router, chunk grading with a capped retry loop, grounded-answer check,
verified citations).

### Phase 4 · Iteration 1 · 2026-09-25

**Built (commits 41ccad9, bb93648):** router (`needs_retrieval | chitchat | clarification_needed`) with a
no-retrieval `direct_response` path; chunk grading with a capped retry loop (`MAX_RETRIEVAL_LOOPS=2`, weak =
fewer than `MIN_RELEVANT_CHUNKS=1` chunks graded relevant); groundedness check that appends a visible caveat;
verified structured citations (source ids validated server-side). Every step is behind its own flag and fails
open. Graph diagram is in the README.

**Eval (`ag_full`, judged, 62 cases, 0 errors; all three flags on, vs `jd_hybrid` = hybrid + rewriting):**
| metric | jd_hybrid | ag_full | threshold |
|---|---|---|---|
| faithfulness | 0.968 | 0.968 | ≥ 0.90 ✅ |
| refusal_correctness | 0.952 | 0.919 | ≥ 0.95 ❌ |
| citation_accuracy | 0.841 | 0.881 | ≥ 0.90 ❌ |
| chitchat with zero retrieval | 2/7 | 7/7 | all ✅ |
| recall@5 | 0.936 | 0.915 | — |
| p50 latency | 3.2 s | 12.5 s | report |
Loop termination at the cap is covered by `test_loop_terminates_at_the_cap_even_when_grading_is_always_weak`.
The first attempt of this run was stopped and discarded: at concurrency 2 the agent (≈5 LLM calls per question
plus 2 judge calls) exceeded the Gemini free-tier *per-minute* quota. `run_eval --delay 30 --concurrency 1`
paces it; the kept run logged 11 backend 429s, all absorbed by retries (0 case errors). The p50 includes those
retry waits and 3–4 extra sequential LLM calls, so it overstates steady-state latency on a paid tier.

**Diagnosis:** both lost refusal points are exact-term questions whose correct chunk *was* retrieved on the first
attempt. q_028 (E-4292): the grader rated the attempt weak, the retry rewrite drifted to "E-4292 error code
troubleshooting", and the final context no longer held the answer chunk. q_034 (HW-FN-7701): the right chunk
was retrieved but graded irrelevant, so generation got an empty context and refused. Both are the same design
flaw: the final context was only the last attempt, filtered by grades. A related latent bug: grading filtered
chunks *after* the `sources` event, so `[Source N]` in the answer could point at a different chunk than the UI
showed.

**Changed (commit 45a8471):** keep `(chunk, grade)` from every attempt and choose the final context from that
pool (relevant, then partial, else everything retrieved, capped at top_k); retry rewrites re-append identifiers
the model dropped; a final `sources` event carries exactly the context the model sees. Recall in later runs is
therefore measured on the final context rather than the raw first retrieval.

**Next:** iteration 2 — re-run the same judged eval (`ag_full2`).

### Phase 4 · Iteration 2 · 2026-09-28

**Invalid attempt first (`ag_full2`, 2026-09-25, kept in results/ for the record):** the Gemini free tier allows
500 requests/day per model and that day's budget was already partly spent on iteration 1, so 36/62 cases failed
with 429 mid-run. Numbers from that file are not used anywhere. Lesson: one full judged agent run (≈4.5 app calls
+ 2 judge calls per case) is the most a single day's quota holds, so each iteration gets its own day. A plan to
move the judge to `gemini-3.6-flash` was dropped: its free daily cap ran out after ~15 calls. `--rejudge` (re-score
a stored run with another judge, no app calls) was added while investigating and stays useful.

**Eval (`ag_full3`, judged with the same flash-lite judge as `jd_hybrid`; 62 cases, 6 client timeouts):**
Paired over the 56 cases both runs completed: faithfulness 0.964 → **0.973**, refusal_correctness 0.946 → 0.946
(no per-case change: both iteration-1 regressions, q_028 and q_034, are fixed), citation_accuracy (39 applicable)
0.821 → **0.846**. Unpaired aggregates: faithfulness 0.968 → 0.973, context_precision 0.536 → 0.664 (the grader
drops irrelevant chunks), chitchat without retrieval 2/7 → **7/7**, recall@5 0.936 → 0.929.
**Latency:** p50 3.2 s → 14.1 s. The `/metrics` dump for the run shows why beyond the extra calls: 55 retrieval
queries took 3,053 s in total and the 7 chitchat replies 484 s, yet 5 of those 7 took 3–4 s; two took 207 s and 261 s.
Slow cases cluster in time (q_011–013, q_020–025, q_058–059) and 6 cases exceeded the eval client's 300 s timeout:
provider stalls, amplified by LLM clients with no timeout (Gemini SDK) or 6 retries with backoff (LangChain).
**Cost per query (measured, this run):** 55 retrieval queries + 7 chitchat used 122,720 input and 7,195 output tokens
in the app (router, grader, groundedness, rewrite, generation), i.e. ≈1,980 input + 116 output tokens per query;
$0 on the free tier. Retrievals per query averaged 87/55 = 1.58 (the loop retries about half the time).

**Threshold:** faithfulness 0.973 ≥ 0.90 — met. Definition of done: faithfulness improved (paired +0.009),
chitchat skips retrieval, latency reported; refusal_correctness did **not** improve (equal).

**Diagnosis of the remaining refusals:** all three are exact-code questions that no configuration answers
(q_026 E-5107, q_029 E-4025, q_031 E-5112). Traced below the API: BM25 ranks the answer chunk **#1** for all three,
dense does not have it in its top 20, and RRF then scores it 1/61 against chunks that are mediocre in *both* lists,
so it lands at fused rank 11–13, outside the top 5. Even when kept, the dense-cosine floor and gap filter would cut
it. A Phase 3 weakness that only this per-case analysis exposed.

**Changed (iteration 3):** (1) for queries containing an identifier (error code, SKU, version), the BM25 leader is
pinned into the top-k and exempt from the dense-score floor/gap; (2) every LLM call is bounded:
`LLM_TIMEOUT_S=45` per attempt, `LLM_MAX_RETRIES=2` for the answering model, SDK helpers time out and fail open.

### Phase 4 · Iteration 3 · 2026-09-28

**Retrieval check first (`rs_pin`, retrieval-only, no LLM beyond rewriting):** vs `rs_hybrid` recall@5 0.936 → 1.000,
MRR 0.926 → 0.938, exact_term recall 0.750 → 1.000, all other categories unchanged, no added latency. (While
comparing, `--compare rs_hybrid` turned out to load `rs_hybrid_rr20`: result lookup now requires an exact tag. Only
that one printout was affected; the numbers above and all earlier PROGRESS numbers come from the exact files.)

**Eval (`ag_full4`, judged with flash-lite like `jd_hybrid`; 62 cases, 1 client timeout, 0 quota errors):**
| metric | jd_hybrid (no agent) | ag_full3 (it. 2) | ag_full4 (it. 3) |
|---|---|---|---|
| faithfulness | 0.968 | 0.973 | **0.984** |
| refusal_correctness | 0.952 | 0.946 | **1.000** |
| citation_accuracy | 0.841 | 0.846 | 0.848 |
| recall@5 / MRR | 0.936 / 0.926 | 0.929 / 0.917 | 1.000 / 0.989 |
| chitchat without retrieval | 2/7 | 7/7 | 7/7 |
| latency p50 / p95 | 3.2 s / 5.9 s | 14.1 s / 200.8 s | **8.7 s / 35.1 s** |
The bounded LLM calls removed the stalls: the 7 chitchat replies took 20 s in total (484 s in `ag_full3`). One exact-term
case (q_030) still exceeded the 300 s client timeout: calls are bounded individually, not per request (logged as a
known limitation). Tokens: 126,308 in + 7,702 out over 62 queries ≈ 2,160 per query; 88 retrievals for 55 retrieval
queries (1.6 per query). Part of the refusal gain comes from identifier pinning, which also helps the non-agent
path; a judged non-agent run with pinning would separate the two and needs another day's quota.

**Threshold:** faithfulness 0.984 ≥ 0.90 — met. Definition of done: faithfulness and refusal_correctness improved over
the non-agent run, chitchat completes without retrieval, loop cap tested, latency reported — **met. Phase 4 complete
after 3 iterations.**

**Defaults flipped:** `ENABLE_AGENTIC_LOOP`, `ENABLE_GROUNDEDNESS_CHECK`, `ENABLE_VERIFIED_CITATIONS` now default to
true (accuracy up on every judged metric; the cost is p50 +5.5 s, p95 +29 s and ~2.4× the tokens, stated in the
README). New config keys this phase: `ENABLE_AGENTIC_LOOP`, `MAX_RETRIEVAL_LOOPS`, `MIN_RELEVANT_CHUNKS`,
`ENABLE_GROUNDEDNESS_CHECK`, `ENABLE_VERIFIED_CITATIONS`, `AGENT_MODEL`, `AGENT_MAX_TOKENS`, `LLM_TIMEOUT_S`,
`LLM_MAX_RETRIES`.

### Phase 5 · UI overhaul · 2026-09-25 → 2026-09-28 (direction: "tighten the current look")

**Built:** SSE client for every backend event (typed handlers, single `onDone`, conversation memory via
`conversation_id`); streaming status line with `aria-live`; markdown with syntax highlighting, code-copy and tables;
inline citation chips (only for citations that match a retrieved source; invented ones stay plain text) with a popover
that highlights the supporting sentence; ranked sources panel with relevance bars ("show raw context"); groundedness
and confidence badges; copy / regenerate / thumbs up-down; composer with slash commands, drag-and-drop upload and an
8-row cap; empty state from the indexed documents; dark mode (next-themes), mobile nav, Ctrl/Cmd+K palette, delete
confirmation, optimistic delete, specific toasts; framer-motion removed (~40 kB per page); reduced motion respected.
**Bugs found while testing:** document list and stats were capped at the first 20 of 81 documents (the client never
paged); Progress bars never received their value; an aborted request could reset a newer one; the cited passage was
cut at 300 characters, often before the supporting sentence; the lazily loaded renderer could leave the first answer
blank, and preloading it on mount cost mobile /chat ~28 Lighthouse points, so it now loads when a question is sent.
**Lighthouse (median of 3, production build):** accessibility 100 and best practices 100 on /chat, /dashboard and
/documents, desktop and mobile. Performance: desktop 100 / 94 / 99, mobile 91 / 75 / 64 (LCP 2.8–3.0 s on mobile).
**Threshold:** accessibility ≥ 95 — met. Not met: mobile performance on dashboard and documents (< 85, LCP > 2.5 s on
the throttled profile of this laptop). Screenshots: `docs/screenshots/` (light/dark, desktop/mobile).
**Not built (and why):** per-stage upload progress (ingestion is one synchronous request, no stage events); a
right-rail sources panel on desktop (the panel stays inline under each answer).

### Phase 6 · Observability and the feedback loop · 2026-09-25 → 2026-09-28

**Built:** `POST /feedback` (rating, question, answer, retrieved chunk ids, comment, active flags) wired to the thumbs
in the UI; `scripts/feedback_to_eval.py` turns thumbs-down rows into golden-format candidates with the ground truth
left for a human (verified end to end with a probe row, then deleted). Prometheus `/metrics` replaces the in-process
singleton: queries by route/outcome, latency per request and per retrieval stage, retrievals per query, LLM tokens by
model and step, cost at configured prices, embedding requests/retries/429s, ingestion. `docker-compose.observability.yml`
brings up Prometheus, Grafana (provisioned 11-panel dashboard) and self-hosted Langfuse v2 (Postgres only; v3 needs
ClickHouse/Redis/MinIO, too heavy next to this stack). Langfuse: one trace per query, a span per graph node, flags as
tags, seeded headlessly from `.env`; tracing and metrics fail open.
**Verified:** `/metrics` scrapes (Prometheus target up); the Grafana dashboard renders live data; a real query produced a
38-observation trace with route, outcome, groundedness and flags (screenshots in the README).
**Cost per query:** ≈2,040 input + 124 output tokens with the agent on (`ag_full4`), $0 on the free tier.
**Threshold:** traces + metrics + feedback live — met.

### Phase 4 · Control run (`jd_pin`) · 2026-10-01

**Why:** the Phase 4 comparison (iteration 3) was against `jd_hybrid`, which predates the identifier-pinning fix, so it
could not separate the agent's contribution from pinning's. `jd_pin` is the missing control: the same configuration as
`ag_full4` (hybrid + rewriting + pinning) with all three agent flags off, the same flash-lite judge, 62 cases, 0 errors,
0 quota errors.

| metric | jd_hybrid | jd_pin (no agent) | ag_full4 (agent) |
|---|---|---|---|
| recall@5 / MRR | 0.936 / 0.926 | 1.000 / 0.938 | 1.000 / 0.989 |
| faithfulness | 0.968 | 0.984 | 0.984 |
| refusal_correctness | 0.952 | 0.984 | 1.000 |
| citation_accuracy | 0.841 | 0.872 | 0.848 |
| context_precision | 0.536 | 0.537 | 0.738 |
| answer_relevance | 0.968 | 0.976 | 0.984 |
| latency p50 / p95 | 3.2 s / 5.9 s | 2.7 s / 4.3 s | 8.7 s / 35.1 s |

**Finding (a negative result for the agent):** pinning alone delivers the accuracy improvement. The only refusal
difference between `jd_pin` and `ag_full4` is one chitchat question (q_062). The agent's measurable benefits are cleaner
context (precision 0.537 → 0.738), the chitchat shortcut (7/7 answered without a search vs 2/7) and a slightly higher
MRR measured on its graded context; its costs are 3× the p50, 8× the p95, about 2.4× the tokens and slightly lower
citation accuracy (0.872 → 0.848). This **corrects the iteration-3 statement** that accuracy was "up on every judged
metric" because of the agent: that comparison credited the agent with pinning's gain. The README now states it.
**Default kept on** (`ENABLE_AGENTIC_LOOP`, `ENABLE_GROUNDEDNESS_CHECK`, `ENABLE_VERIFIED_CITATIONS`) because the spec's
Phase 4 goals include chitchat without retrieval and a visible groundedness verdict, and the CI reference was recorded
with it; `=false` is the documented fast path. A reader who values latency or free-tier quota should switch it off.

### Phase 5 · Final measurement after the redesign · 2026-10-01

Production build, Lighthouse 12, median of 3 per page, all five pages. Accessibility 100 and best practices 100
everywhere (desktop and mobile). Performance: desktop 100 on every page; mobile 89 /chat, 88 /dashboard, 88 /documents,
92 /collections, 91 /settings. LCP 0.6 to 0.7 s on desktop, 2.5 to 3.1 s on mobile; mobile CLS 0.099 on /dashboard
(limit 0.1). **Phase 5 thresholds met** (accessibility >= 95, performance >= 85 on every page); remaining gap: mobile LCP
above 2.5 s on /chat and /dashboard. This supersedes the earlier mobile figures (64 to 91) measured on the pre-redesign UI.

