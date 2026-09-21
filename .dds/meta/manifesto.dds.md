---
id: meta-manifesto
type: meta
status: active
dependencies: []
last_updated: 2026-09-18
dds_version: 2.1.0
description: Root constitution and routing protocol for the Documentation-Driven System (.dds/).
---

# SYSTEM_DIRECTIVE: DDS_MASTER_DISPATCHER

## [0] DEFINITION & SCOPE

This document is the Root Dispatcher and Constitution of the Documentation-Driven System (`.dds/`).
Section [1] holds the global laws. Sections [2] and [3] route the EXECUTOR (AI Agent or Human) to the correct Domain Rule Set. This document does NOT contain formatting, writing, or updating rules; those live in the domain rule sets under `.dds/meta/dds.*/`.
EXECUTOR MUST read sections [1] and [2] completely before evaluating the routing matrix in [3].

## [1] CORE_CONSTITUTION (GLOBAL LAWS)

These laws apply to every tier and every operation, regardless of the target domain.

0. **NON_NEGOTIABLE_CONSTRAINTS:** Security, legal and compliance, safety, and physical constraints are documented in `.dds/product/constraints.dds.md` (id `product-constraints`; further documents MAY use `product-constraint-<name>`). No tier, KPI, or business goal may override a constraint. A conflict between a constraint and any other document is NOT resolved by the Truth Hierarchy: EXECUTOR MUST HALT and escalate to a human. `gate: strict` requires an `active` `product-constraints` document.
1. **SINGLE SOURCE OF TRUTH (SSoT):** The `.dds/` directory is the reference description of system behavior. A change MAY originate anywhere: a business decision, a schema migration, or a code edit. Before the change is committed, the relevant `.dds/` documents MUST describe the new behavior. At commit time, if code and an `active` document disagree, the document is the reference and the code is a defect. IF EXECUTOR believes the document itself is wrong, EXECUTOR updates the document through its protocol FIRST, then the code; shipping code that contradicts an `active` document is never the fix. A `draft` document is not yet authoritative; see `.dds/meta/schema.dds.md` [3].
2. **TRUTH_HIERARCHY (CONFLICT RESOLUTION):** The hierarchy resolves conflicts between RULES. IF rule documents contradict each other, `product` rules OVERRIDE `architecture` rules, and `architecture` rules OVERRIDE `modules` rules; the lower document MUST be corrected, never the higher one. KPIs are TARGETS, not rules: a KPI never overrides a rule or a constraint. To change a rule, change the rule document through its protocol. The dependency graph carries the hierarchy: a document depends only on its own tier or a higher one, and the graph is acyclic (`schema.dds.md` [1]); `check` rejects the reverse.
3. **THRESHOLD_BASED_SYNC:** A Git commit or Deployment MUST NOT proceed while `python .dds/meta/scripts/dds.py check --gate --staged` reports errors. Code staged under an `active` document's `sources:` without that document staged is such an error: the governing document changes in the same commit as the code. There is no bypass at the gate; a `DDS-No-Doc: <reason>` commit trailer is an audit mark for CI-era range checks, not a switch. The commit gate (git pre-commit hook, agent hook, or CI) runs this check: always strict for AI agents; `strict` or `warn` for humans according to `gate:` in `.dds/tree.dds.md`.
4. **SCHEMA_CONFORMANCE:** Every `.dds.md` file MUST conform to `.dds/meta/schema.dds.md`: one frontmatter schema, one id grammar, one tree-line grammar. Locks (`locked_by`, `locked_at`) are transient and MUST NEVER be committed.
5. **TOMBSTONE_LAW:** Nothing in `.dds/` is physically deleted. A retired document moves to `.dds/archive/` and leaves a Tombstone line in the index tree that referenced it.

## [2] ROUTING_PRECEDENCE

1. **TOP-DOWN ORDER:** A task that touches several tiers is DECIDED top-down: complete the `product` operation first, then `architecture`, then `modules`. Each Domain Rule Set governs only the documents of its own tier. Deprecations are the one exception in execution: they are decided top-down but EXECUTED leaves-first (see the deprecate protocols), so that no `active` document ever depends on a `deprecated` id.
2. **NO MATCH:** IF the task matches no tier (e.g., a refactor with no behavioral, structural, or business change), no `.dds/` document changes. EXECUTOR still runs `dds.py check` before commit.
3. **TIE-BREAK:** IF EXECUTOR cannot decide between two tiers, EXECUTOR MUST choose the HIGHER tier (`product` > `architecture` > `modules`) and let that tier's impact assessment route the remaining work downward.
4. **UNDOCUMENTED CODE:** IF the repository contains code that `.dds/` does not yet describe, EXECUTOR MUST follow `.dds/meta/adopt.dds.md` for that area before applying any other protocol to it.

## [3] DOMAIN_ROUTING_MATRIX

When EXECUTOR receives a task to read, create, update, or retire documentation, EXECUTOR MUST evaluate the `context` and follow the matching routing path. Several paths MAY match; apply [2].1 and [2].3.

**IF context CONTAINS (Business Logic OR Market Goals OR User Personas OR Epics OR KPIs):**
- `TARGET_DOMAIN` = `product`
- `NEXT_ACTION`: EXECUTOR MUST read `.dds/meta/dds.product/rules.dds.md` and continue there.

**IF context CONTAINS (Global Tech Stack OR Database Schemas OR System Infrastructure OR Global API Contracts OR Security Boundaries):**
- `TARGET_DOMAIN` = `architecture`
- `NEXT_ACTION`: EXECUTOR MUST read `.dds/meta/dds.architecture/rules.dds.md` and continue there.

**IF context CONTAINS (Specific Application Features OR Code Logic OR UI Components OR Isolated Modules):**
- `TARGET_DOMAIN` = `modules`
- `NEXT_ACTION`: EXECUTOR MUST read `.dds/meta/dds.modules/rules.dds.md` and continue there.

EXECUTOR MUST NOT modify this manifesto or `schema.dds.md` as part of a domain operation. Protocol changes are DDS version changes.

## [4] TOOLING

`.dds/meta/scripts/dds.py` (Python 3, standard library only) implements the mechanical parts of the protocols so that EXECUTOR does not have to simulate them:

- `check` — frontmatter schema, id uniqueness, dependency resolution, dependency direction and cycle detection, non-empty required sections and resolving `sources:` on `active` documents (warnings on `draft`), tree ↔ filesystem parity and reachability, tombstone targets, version match, reserved `product-constraint` prefix, and the `gate: strict` precondition (an `active` `product-constraints` document). Exit code 1 on any error. Locks are reported as INFO. `--gate` (used by commit hooks) additionally treats any present lock as an error. `--staged` reads the git index: code staged under an `active` document's `sources:` without that document staged is an error in gate mode and a warning otherwise; staged code that no module document governs is the same error once the repository has module documents. Known non-detections: a file renamed out of a glob is not seen (the index lists the new name only), and an empty index reports INFO. `--coverage` and `--sync` add adoption reports (see `adopt.dds.md`).
- `impact <id>` — DIRECT dependents: non-deprecated (`active` or `draft`) documents whose `dependencies` list this id. `impact <id> --down` — TRANSITIVE dependents (the cascade set). `impact <id> --up` — the document's own direct `dependencies`, with their `status`.
- `lock <file> --by <executor_id>` / `unlock <file>` — CONCURRENCY_CONTROL with the 40-minute takeover rule computed from `locked_at`.
- `tree` — lists index entries that are missing, dangling, or duplicated.

Every protocol states a manual fallback for environments where the script cannot run.

**WHAT THE TOOLING DOES NOT DO:** DDS does not orchestrate agents. Deprecation cascades are enforced mechanically (`check` rejects an `active` document that depends on a `deprecated` id). Update cascades rely on EXECUTOR discipline plus `check --sync` warnings. `--sync` detects drift (source files changed while the governing document did not); it cannot prove a document is correct, and touching the file silences it. Human review does that. `--sync` and `--coverage` resolve paths relative to the directory that holds `.dds/`, so a project inside a monorepo works as long as `--root` (or the working directory) points at that project.

# END_OF_DIRECTIVE
