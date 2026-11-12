# Bug hunt — 2026-11 (read-only pass)

Five suspected defects from a static read of `kettle-core`. This sprint documents and
reproduces each defect; **no production fixes** in the accompanying change set. Each item
has an `xfail` test in `tests/test_bug_hunt_2026_11.py`.

| # | Location | Summary |
|---|----------|---------|
| 1 | `kettle/server.py` ~799 (`safe_path`) | Relative paths with a project `base` are not required to stay under that base. |
| 2 | `kettle/lineage.py` ~173 (`read_record`) | One bad JSONL line aborts the whole read. |
| 3 | `kettle/server.py` ~1049 (`load_session`) | Corrupt `session.json` is swallowed and read as `{}`. |
| 4 | `kettle/server.py` ~1309 (`save_settings`) | Corrupt `settings.json` merges as `{}` and skips the corrupt backup `load_settings` writes. |
| 5 | `kettle/server.py` ~1167 (`find_entry`) | Queue entry `id` lookup is strict `==`; string `"42"` does not match numeric `42`. |

---

## 1. Cross-project escape via `safe_path` with `base`

**File:** `kettle/server.py`, `safe_path` (lines 799–814)

**Why it is wrong:** When `base` is the active project root, the handler joins `base / relative`
then accepts any resolved path that lies under **any** registered allow-root. It never requires
the result to remain under `base`. Sibling projects in the registry are all allow-roots, so a
relative path can climb out of project A and land in project B while the route still thought it
was scoped to A.

**Failure scenario:** Registry lists project `alpha` at `…/alpha` and project `beta` at `…/beta`.
`POST /api/file` for `alpha` with `path: "../beta/notes.md"` resolves to a file under `beta`.
The server reads or writes another desk’s tree without rejecting the path.

**Reproduction:** `tests/test_bug_hunt_2026_11.py::test_safe_path_relative_must_stay_under_base`

---

## 2. `read_record` does not tolerate a corrupt JSONL line

**File:** `kettle/lineage.py`, `read_record` (lines 173–178)

**Why it is wrong:** Every non-empty line is passed to `json.loads` with no per-line guard.
`SessionLedger` in `runtime.py` already skips bad lines; the durable working record reader does
not. A single truncated or hand-edited line makes the whole call raise `JSONDecodeError`.

**Failure scenario:** `.kettle/working-record.jsonl` has one valid entry and one garbage line
(partial write, merge conflict, manual edit). `lineage.status()` or `GET /api/lineage` raises
instead of returning partial records or a surfaced parse error.

**Reproduction:** `tests/test_bug_hunt_2026_11.py::test_read_record_skips_corrupt_jsonl_line`

---

## 3. Corrupt `session.json` masquerades as empty session

**File:** `kettle/server.py`, `load_session` (lines 1049–1066)

**Why it is wrong:** `json.JSONDecodeError` on `session.json` is caught and ignored. The
function falls through to legacy `interview.json`, then returns `{}` with no error. A later
`save_session` overwrites the corrupt file with a fresh minimal record.

**Failure scenario:** Crash mid-write leaves `session.json` as `{"session_id":` (invalid JSON).
The sitting opens with no `session_id`; curator starts a new CLI session while bindings
(`status`, `last_entry`, provider tag) that were on disk are silently dropped.

**Reproduction:** `tests/test_bug_hunt_2026_11.py::test_load_session_corrupt_json_surfaces_error`

---

## 4. `save_settings` on corrupt disk merges from empty dict

**File:** `kettle/server.py`, `save_settings` (lines 1309–1331)

**Why it is wrong:** On `JSONDecodeError`, `cur` becomes `{}` and the patch is deep-merged into
that empty dict, then written atomically. Unlike `load_settings` (lines 1290–1297), this path
does not snapshot the unreadable bytes to `settings.json.corrupt`. A small UI patch after disk
corruption can replace the entire settings file with defaults plus the patch, discarding keys
that were present before corruption (`kits`, `egress`, `admin`, custom curator keys).

**Failure scenario:** `settings.json` is corrupted. Client sends `POST /api/settings` with only
a curator model tweak. Server persists a nearly fresh settings document; prior configuration is
gone and no corrupt backup exists for recovery.

**Reproduction:** `tests/test_bug_hunt_2026_11.py::test_save_settings_corrupt_disk_preserves_backup`

---

## 5. `find_entry` type mismatch on queue entry id

**File:** `kettle/server.py`, `find_entry` (lines 1167–1171)

**Why it is wrong:** Lookup uses `e["id"] == entry_id` with no normalization. Queue JSON from
hand edits or external tools may store numeric ids; HTTP bodies and CLI arguments are strings.

**Failure scenario:** `queue.json` contains `"id": 42` (number). Client `POST /api/approve` with
`{"id": "42", ...}`. `find_entry` raises `KeyError` → **400** `bad_request` instead of matching
the entry. Same pattern affects open, chat context, diff, and other id-keyed routes.

**Reproduction:** `tests/test_bug_hunt_2026_11.py::test_find_entry_coerces_string_and_int_ids`

---

## Verification (2026-11-12)

```sh
python3 -m pytest
```

```
============ 791 passed, 1 skipped, 5 xfailed in 197.75s (0:03:17) =============
```
