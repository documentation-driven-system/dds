![DDS — Documentation-Driven System](docs/dds-banner.jpg)

# DDS — Documentation-Driven System

[![ci](https://github.com/documentation-driven-system/dds/actions/workflows/ci.yml/badge.svg)](https://github.com/documentation-driven-system/dds/actions/workflows/ci.yml)

A `.dds/` directory that describes what a system does, protocols that tell people and AI agents how to change that description, and a script that refuses a commit when the description is inconsistent.

DDS is for repositories where humans and AI coding agents work side by side over a long time. Agents start every session with no memory; a repository that keeps its behaviour written down in one governed place gives every session the same starting point, and the commit gate keeps that place from drifting.

Not to be confused with the OMG Data Distribution Service, which shares the acronym.

## What is in the box

| Part | Where | What it does |
|---|---|---|
| Three tiers of documents | `.dds/product/`, `.dds/architecture/`, `.dds/modules/` | Why the system exists, where it runs, how each feature behaves. Each tier obeys the one above it. |
| Non-negotiable constraints | `.dds/product/constraints.dds.md` | Security, legal, safety, physical rules that no tier, KPI, or business goal overrides. |
| Protocols | `.dds/meta/` | The constitution and routing (`manifesto.dds.md`), one schema (`schema.dds.md`), a brownfield adoption protocol (`adopt.dds.md`), and write / update / deprecate rules per tier. |
| Validator | `.dds/meta/scripts/dds.py` | `check` (schema, ids, dependency direction and cycles, non-empty active documents, index trees, tombstones, locks; `--staged` for code committed without its document), `impact` (dependency graph), `lock` / `unlock`, `tree`. Standard library only. |
| Adapters | `templates/adapters/` | `AGENTS.md`, `CLAUDE.md`, an Agent Skill, a Claude Code hook, a git pre-commit hook, a CI job. These are what make an agent read `.dds/` at all. |
| Examples | `examples/task-tracker/`, `examples/broken/` | A filled repository that passes the strict gate, and a deliberately invalid tree that the validator must reject. |

## When to use DDS, and when not to

Use it when the repository will live for years, more than one person or more than one AI agent changes it, the cost of "nobody remembers why this works this way" is real, and business rules and technical decisions need an explicit order of precedence.

Skip it for a prototype, a weekend project, or a single-maintainer tool. Three tiers of documentation cost more than they return there; an `AGENTS.md` with a paragraph of conventions is the right size.

## Why this and not a shorter thing

| Alternative | Good at | Does not do |
|---|---|---|
| `AGENTS.md` / `CLAUDE.md` alone | Always-on conventions in one file | No tiers, no lifecycle for retired features, no check |
| `CONTEXT.md` + ADRs (e.g. grill-with-docs) | Shared vocabulary and decision records, very light | No order of precedence between decisions, no dependency graph |
| Spec-driven tools (Spec Kit, Kiro, OpenSpec) | Spec → plan → tasks for one feature at a time | The spec ends with the feature; no persistent system description, no deprecation trail |
| DDS | A persistent, tiered description with a deprecation lifecycle and an impact graph, checked at commit | Semantic verification: `check` validates structure, not whether the code does what the document says |

DDS composes with the first two: the adapters *are* an `AGENTS.md` and a skill, and ADR-style entries fit a document's changelog.

## Quick start

**New repository**

1. Copy `.dds/` from this repository into yours (it ships empty: protocols, the script, three empty tier indexes).
2. Copy the adapters your tools read; `templates/adapters/README.md` maps each agent to its files. `AGENTS.md` (+ `CLAUDE.md`) and the skill under `.claude/skills/dds/` and `.agents/skills/dds/` cover Claude Code, Codex, Cursor, Copilot, and Gemini CLI.
3. Write `.dds/product/constraints.dds.md` and `.dds/product/vision.dds.md` following `.dds/meta/dds.product/write.dds.md`, and list both in `.dds/product/product.tree.dds.md`; an unlisted document fails the gate.
4. Run the gate: `python .dds/meta/scripts/dds.py check --gate`.

**Existing codebase**

Follow `.dds/meta/adopt.dds.md`: documents start as `status: draft` (the code is the reference while a document is a draft), `check --coverage` shows which code no document governs yet, humans commit under `gate: warn` until coverage is good enough, and agents are held to the strict gate from the first day.

## A day with DDS

1. Before changing code, a schema, an API, or documentation, the agent (or you) reads `.dds/meta/manifesto.dds.md` and follows the tier protocol it routes to.
2. The change lands in code and in the governing document before the commit.
3. `python .dds/meta/scripts/dds.py check --gate --staged` runs from the git hook and the agent hook (CI runs `check --gate`). Code staged under an `active` document without that document fails the gate; a failing gate is fixed, not bypassed.
4. Retiring a feature runs `impact <id> --down` for the cascade set, archives the documents leaves-first, and leaves Tombstones in the index trees so nobody searches for a file that no longer exists.

`python .dds/meta/scripts/dds.py --help` lists the commands. `examples/task-tracker/` shows the result of all of this on a small fictional app, including a completed retirement.

## Repository layout

```text
.dds/                     the template a consuming repository copies (empty tiers, protocols, script)
templates/adapters/       entry points and commit gates per agent, with install notes
examples/task-tracker/    filled reference repository; passes `check --gate` with 0 warnings
examples/broken/          invalid tree; every expected error is listed and tested
tests/                    unit tests for the script, the adapters, and the examples
tools/sync_copies.py      refreshes the copies the example keeps of the template and adapters
docs/                     human-facing guides: overview and one guide per tier
```

## Status

- Renamed from `documentary-driven-system` on 2026-09-18 (spelling fix; same project, same single maintainer). The old URL redirects.
- `v1.0.0` is the original release of the idea as prose. `v2.0.0` (tagged 2026-09-18) introduced the schema, the validator, adapters, and examples and breaks the 1.0 frontmatter. `2.1.0` (current line) makes the gate look at the code: `check --staged`, dependency direction and cycle detection, and non-empty `active` documents.
- Verified here: the template and the example pass the strict gate; `examples/broken/` reports every expected error; the test suite under `tests/` passes under Git Bash and PowerShell, and in CI on ubuntu and windows with Python 3.8 and 3.x; the Claude Code hook command exits 2 on a failing tree and when no interpreter is found; the git pre-commit blocks under `gate: strict` and warns under `gate: warn` in a real repository; the skill passes `skills-ref validate`.
- Verified only on paper: the Claude Code hook's `if` pattern match (see `templates/adapters/README.md` for the one-command live check); the Vale rules. `check --staged` is verified against a real git index in the tests, not yet in a live Claude Code commit.
- Cost of one operation: the agent reads the manifesto, one tier's rules, and one protocol, about 16 KB (roughly 4k tokens). The full protocol corpus is 75 KB and is never read at once.
- Not provided: semantic verification of code against documents. `check` proves structure and consistency; whether the code does what the document says is still a review.

## Security and privacy

- **No telemetry, no analytics, no network access.** `dds.py` imports only the Python standard library; its one `subprocess` call runs `git` locally for `check --sync`. Nothing phones home, and the hooks and CI job call nothing but that script.
- **No credentials.** The script reads no API keys, tokens, or environment secrets; `DDS_PYTHON` (an interpreter path) is the only variable it honours.
- **No external instructions.** `AGENTS.md`, `CLAUDE.md`, and `SKILL.md` contain no URLs and point only at files inside the repository; the skill declares no `allowed-tools`.
- **What executes, and when.** The Claude Code hook in `.claude/settings.json` runs `dds.py check --gate` before a `git commit` without prompting; the git pre-commit hook runs the same check on commit; CI runs it on push. Nothing runs at install time, and nothing auto-updates.
- **What it writes.** `check`, `impact`, and `tree` write nothing. `lock` / `unlock` (only with `locking: on`) write `locked_by` / `locked_at` into one document's frontmatter and a sidecar under `.dds/.locks/`. `tools/sync_copies.py` writes only into `examples/task-tracker/`.
- **Turning a gate off.** Remove the `PreToolUse` block from `.claude/settings.json`; run `git config --unset core.hooksPath`; delete the workflow file. The documents and the script keep working without any gate.

## Development

`python -m unittest discover -s tests` runs everything: the validator against the template and `examples/broken/`, the adapters (including the hook command and a real git pre-commit), the reference example, and the prose hygiene checks. `python tools/sync_copies.py` refreshes the example's copies after a template change.

## Documentation

- Overview: [docs/dds-main.md](docs/dds-main.md)
- Product tier: [docs/dds-product.md](docs/dds-product.md) · Architecture tier: [docs/dds-architecture.md](docs/dds-architecture.md) · Modules tier: [docs/dds-modules.md](docs/dds-modules.md)
- Constitution and routing: [.dds/meta/manifesto.dds.md](.dds/meta/manifesto.dds.md) · Schema: [.dds/meta/schema.dds.md](.dds/meta/schema.dds.md) · Adoption: [.dds/meta/adopt.dds.md](.dds/meta/adopt.dds.md)
- Tier protocols: `.dds/meta/dds.product/`, `.dds/meta/dds.architecture/`, `.dds/meta/dds.modules/` — each with `rules`, `write`, `update`, `deprecate`
- Installing the adapters: [templates/adapters/README.md](templates/adapters/README.md)

## License

MIT — see [LICENSE](LICENSE).
