# DDS adapters

`.dds/` holds the protocols; nothing reads them unless an entry point says so. These templates are the entry points and the commit gate. Copy what your tools need into the consuming repository (step [1].2 of `.dds/meta/adopt.dds.md`).

| File here | Copy to | Purpose |
|---|---|---|
| `AGENTS.md` | repository root | Always-on instructions for agents that read `AGENTS.md` (Codex, Cursor, Copilot, Jules, and others). |
| `CLAUDE.md` | repository root | Claude Code reads `CLAUDE.md`, not `AGENTS.md`; this file imports it and adds Claude-specific lines. |
| `skills/dds/` | `.claude/skills/dds/` and/or `.agents/skills/dds/` | The same instructions as an Agent Skill, loaded on demand. Keep the copies identical. |
| `claude-code/settings.json` | `.claude/settings.json` (merge if one exists) | PreToolUse hook: `dds.py check --gate --staged` runs before `git commit …`, `git -C <path> commit …`, and `git -c key=value commit …`; exit 2 blocks the commit. |
| `git/pre-commit` | `.githooks/pre-commit` + `git config core.hooksPath .githooks` | Human gate; honours `gate: strict` / `gate: warn` from `.dds/tree.dds.md`. |
| `ci/dds-check.yml` | `.github/workflows/dds-check.yml` | Strict gate on pull requests and pushes to `main`. |
| `vale/` | repository root (optional) | Suggestion-level prose lint for chunk-local referents and header depth. Written against the Vale rule reference, not run here (no Vale binary); validate with `vale sync && vale .dds` before relying on it. |

## Where each agent looks for the skill

Verified against each product's documentation on 2026-09-18; re-check before relying on it.

| Agent | Skill directory (project) | Always-on file |
|---|---|---|
| Claude Code | `.claude/skills/` | `CLAUDE.md` (import `AGENTS.md` with `@AGENTS.md`) |
| OpenAI Codex | `.agents/skills/` | `AGENTS.md` |
| Cursor | `.agents/skills/`, `.cursor/skills/` (also reads `.claude/skills/`) | `AGENTS.md` |
| GitHub Copilot | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | `AGENTS.md` / `copilot-instructions.md` |
| Gemini CLI | `.gemini/skills/`, `.agents/skills/` | `GEMINI.md` (copy the `AGENTS.md` content or import it) |

Two placements, `.claude/skills/dds/` and `.agents/skills/dds/`, cover every agent in the table. The skill uses only the fields of the open Agent Skills specification (`name`, `description`, `license`, `metadata`), so one file serves all of them.

## Gate policy in one line

Agents and CI are always strict. Humans start with `gate: warn` in `.dds/tree.dds.md` while adopting DDS (`adopt.dds.md` [4]) and switch to `gate: strict` when coverage is good enough.

Only Claude Code has a pre-tool hook here. Codex, Cursor, Copilot and Gemini CLI get the gate from the git pre-commit hook and CI; their `AGENTS.md` step 4 asks them to run it themselves as well.

## Verifying the Claude Code hook

The hook's `if` patterns (`Bash(git commit*)`, `Bash(git -C * commit*)`, `Bash(git -c * commit*)`) follow the permission-rule glob syntax in the Claude Code hooks reference; they were checked against that reference, not observed live. Verify once per repository: start a Claude Code session in the repository, ask it to run `git commit --dry-run --allow-empty -m test`, and confirm the transcript shows the gate output. Forms outside those two patterns (for example a commit issued through a script) bypass the agent hook and are caught by the git hook and CI.

## Windows

Claude Code runs hook commands through Git Bash on Windows; the `settings.json` command is a Bash one-liner. Git for Windows runs `.githooks/pre-commit` through its bundled `sh`. Both need `python` on `PATH` (or `DDS_PYTHON` for the git hook).
