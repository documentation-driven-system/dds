---
id: meta-modules-update
type: meta
status: active
dependencies: [meta-modules-rules, meta-modules-write]
last_updated: 2026-09-18
description: Machine-readable protocol for atomic updates, concurrency locking with 40-minute timeout, reverse-documentation, and a capped changelog.
---

# SYSTEM_DIRECTIVE: MODULES_UPDATE_AND_SYNC_PROTOCOL

## [0] DEFINITION & SCOPE

This document defines the strict lifecycle for modifying existing `.dds.md` files within the `.dds/modules/` directory.
EXECUTOR (AI Agent or Human) MUST adhere to the `CONCURRENCY_CONTROL` and `ATOMIC_UPDATE` sequences to prevent race conditions, deadlocks, and context loss.

## [1] CONCURRENCY_CONTROL (LOCKING_PROTOCOL)

Before reading or writing content, EXECUTOR MUST secure the target file to prevent multiple agents from modifying it simultaneously.

**LOCK_ACQUISITION_ROUTINE:**

1. RUN `python .dds/meta/scripts/dds.py lock <target_file> --by <executor_id>`.
   - The script writes `locked_by: <executor_id>` and `locked_at: <UTC ISO-8601 timestamp>` into the frontmatter.
   - IF the file is already locked by another executor AND the lock is younger than 40 minutes, the script exits with `STATUS: LOCKED_BY <other_id> (<age> min)`. EXECUTOR MUST ABORT and retry after a delay (Exponential Backoff).
   - IF the lock is older than 40 minutes (crashed executor or disconnected agent), the script takes the lock over and reports `STATUS: LOCK_TAKEN_OVER`.
2. MANUAL FALLBACK (script unavailable): READ `locked_by` and `locked_at` from the frontmatter; apply the same 40-minute rule by comparing `locked_at` with the current UTC time; write both fields yourself.
3. **NEVER COMMIT A LOCK:** `locked_by` and `locked_at` are transient. `dds.py check --gate` (the commit gate) fails while any lock is present; plain `check` lists locks as INFO.
4. This section applies ONLY when `.dds/tree.dds.md` sets `locking: on` (default `off`). The script acquires the real mutex through an exclusive-create sidecar in gitignored `.dds/.locks/` and mirrors it into the frontmatter; the manual fallback has no atomicity guarantee, so two executors racing within the same second may both believe they hold the lock.
5. **SCOPE OF A LOCK:** a lock coordinates executors that share ONE working copy (several agents or people on the same checkout). Uncommitted frontmatter never reaches another clone; across clones, isolate work with branches.

## [2] ATOMIC_READ_BEFORE_WRITE_PROTOCOL

EXECUTOR is FORBIDDEN from performing full-file overwrites (blind replacement).

**MUTATION_CONSTRAINTS:**

- EXECUTOR MUST locate the specific Markdown header (`##` or `###`) related to the specific code/logic change.
- EXECUTOR MUST perform a localized `diff` update (Atomic Update) ONLY on the relevant semantic chunk.
- EXECUTOR MUST NOT delete historical constraints unless they actively contradict the new codebase logic.

## [3] REVERSE_DOCUMENTATION_ROUTINE (CODE TO ABSTRACTION)

When codebase changes dictate documentation updates, EXECUTOR MUST translate implementation details into abstract business/technical rules.

**TRANSLATION_RULES:**

- BAD: "Added `if (user.age < 18) return false` to `auth.ts`."
- GOOD: "System MUST block authentication for users under 18 years old."

**LINGUISTIC_DEPENDENCY:**
EXECUTOR MUST strictly apply the `RAG_OPTIMIZED_LINGUISTICS` (chunk-local referents, Context-Bearing Headers) defined in `.dds/meta/dds.modules/write.dds.md`.

## [4] METADATA_AND_CHANGELOG_MUTATION (CHANGELOG CAP)

Every modification MUST leave an audit trail, but MUST NOT overflow the LLM Context Window.

**ACTION 1: Frontmatter Restoration:**

- UPDATE `last_updated: [YYYY-MM-DD]` to the current execution date.
- RUN `python .dds/meta/scripts/dds.py unlock <target_file>` (removes `locked_by` and `locked_at`). Manual fallback: delete both fields.

**ACTION 2: Log Append (Capped):**

1. LOCATE `## Changelog` at the bottom of the file (Create it if missing).
2. APPEND new entry: `- [YYYY-MM-DD]: [Brief description of the logic change].`
3. IF the Changelog now holds MORE THAN 10 entries, REMOVE the oldest entries until 10 remain. Removed entries stay available through `git log -- <file>`; `dds.py check` warns above 10.

## [5] CROSS_DOMAIN_INTEGRITY_GATE

Before concluding the update, EXECUTOR MUST verify if the module logic change impacts higher-level architecture.

**INTEGRITY_CHECK:**
IF the module update alters a Database Schema requirement or a Global API Contract:

- EXECUTOR MUST apply the `CONCURRENCY_CONTROL` protocol to the relevant file in `.dds/architecture/` and update it accordingly to maintain the Truth Hierarchy.

**FINAL_CHECK:** RUN `python .dds/meta/scripts/dds.py check` after the lock is released ([4] ACTION 1). IF it fails, fix the reported errors before reporting `SYNC_COMPLETE`.

**STAGING RULE:** The commit hooks run `check --gate --staged`. Code staged under this document's `sources:` while this document is not staged fails the gate. EXECUTOR stages the document change with the code, or asks the human when the code change needs no document change and the human decides to commit under `gate: warn`. A `DDS-No-Doc: <reason>` trailer in the commit message records that decision for CI-era range checks; it does not open the gate.

*Output: EXECUTOR returns `STATUS: SYNC_COMPLETE` ONLY IF all locks are released and cross-domain dependencies are resolved.*

# END_OF_DIRECTIVE
