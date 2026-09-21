---
id: meta-schema
type: meta
status: active
dependencies: [meta-manifesto]
last_updated: 2026-09-18
description: The single frontmatter schema, id grammar, and tree-line grammar every .dds.md file MUST follow; enforced by scripts/dds.py check.
---

# SYSTEM_DIRECTIVE: DDS_SCHEMA

## [0] DEFINITION & SCOPE

This document is the single source of truth for the machine-readable parts of every `.dds.md` file: the YAML frontmatter, the `id` grammar, the `status` semantics, and the line grammar of `.tree.dds.md` index files.
The templates in the domain `write.dds.md` files MUST conform to this schema. Rules marked ENFORCED are checked by `python .dds/meta/scripts/dds.py check`; the others are conventions EXECUTOR (AI Agent or Human) MUST follow.

## [1] FRONTMATTER_FIELDS

Every `.dds.md` file MUST begin with a YAML block delimited by `---` lines. The block is FLAT: scalar values and single-line lists (`[a, b]`) only. Nested maps are FORBIDDEN so that the block stays parseable without a YAML library.

| Field | Required | Values / Format | Notes |
|---|---|---|---|
| `id` | yes | see [2] | Unique across the whole `.dds/` tree, including `archive/`. ENFORCED |
| `type` | yes | `product` \| `architecture` \| `module` \| `tree` \| `meta` | ENFORCED |
| `status` | yes | `draft` \| `active` \| `deprecated` | See [3]. ENFORCED |
| `dependencies` | yes | `[]` or `[id, id, ...]` | Ids only, never paths. Every id MUST resolve to a document anywhere under `.dds/`, INCLUDING `archive/` (a tombstoned epic still resolves). Dependencies point UPWARD only: `product` → `product`; `architecture` → `product`, `architecture`; `module` → any tier; `meta` → `meta`; trees declare none. The graph MUST be acyclic. The only status error: an `active` document depending on a `deprecated` id. ENFORCED |
| `last_updated` | yes | `YYYY-MM-DD` | ENFORCED |
| `description` | recommended | one sentence | Shown by index trees and tooling. |
| `sources` | optional, `module` only | `[glob, glob]` relative to repo root | Code paths this document governs. Enables `check --coverage` and `check --sync`. |
| `locked_by` | transient | executor id | MUST appear together with `locked_at`. MUST NOT be committed: `check` reports it as INFO, `check --gate` fails. ENFORCED (gate) |
| `locked_at` | transient | ISO-8601 UTC, e.g. `2026-09-18T09:30:00Z` | The 40-minute takeover rule is computed from this value. ENFORCED (format) |
| `deprecated_date` | iff `status: deprecated` | `YYYY-MM-DD` | ENFORCED |
| `original_path` | iff `status: deprecated` | path relative to repo root | Where the file lived before archiving. ENFORCED |
| `dds_version` | root tree and manifesto only | `MAJOR.MINOR.PATCH` | The two values MUST match; `check` warns when the script's own version differs. ENFORCED |
| `locking` | root tree only | `on` \| `off` | Default `off`. `on` enables CONCURRENCY_CONTROL for executors that share ONE working copy. Known flaw of frontmatter-only locking: check-then-write is not atomic. `dds.py lock` MUST acquire the real mutex with an exclusive-create (`O_EXCL`) sidecar under gitignored `.dds/.locks/` and mirror the result into the frontmatter; the manual fallback has no such guarantee. |
| `gate` | root tree only | `strict` \| `warn` | Policy for the HUMAN pre-commit hook. Agent hooks are always strict. `strict` requires an `active` `product-constraints` document. ENFORCED |

Fields not listed here are FORBIDDEN (ENFORCED). The legacy fields `version`, `priority`, and the legacy value `status: locked_by_*` are invalid.
List values that start with `*` MUST be quoted (`sources: ["**/*.ts", src/auth/**]`); a bare leading `*` is a YAML alias and breaks real YAML parsers. Files under `.dds/` that do not end in `.dds.md` (e.g., `archive/README.md`, `meta/scripts/`) are ignored by `check`.

## [2] ID_GRAMMAR

1. Pattern: `^[a-z0-9]+(-[a-z0-9]+)*$` — lowercase ASCII kebab-case. ENFORCED
2. The prefix MUST match the file's `type` (ENFORCED):
   - `product-` for `type: product`
   - `architecture-` for `type: architecture`
   - `modules-` for `type: module`
   - `tree-` for `type: tree`
   - `meta-` for `type: meta`
   - `product-constraint` is RESERVED: a document whose id starts with it holds non-negotiable constraints (manifesto [1].0) and MUST be `type: product`. ENFORCED
3. Ids are PERMANENT. A deprecated document keeps its id forever; an id is never reused for a new document. ENFORCED (uniqueness across `archive/`)
4. Examples: `product-user-onboarding`, `product-constraints`, `architecture-core-database`, `modules-auth-login`, `tree-modules-auth`, `meta-product-write`.

## [3] STATUS_SEMANTICS

- `draft`: the document exists but is NOT authoritative. While a document is `draft`, the code is the reference and the document adapts to it. Used during adoption (`adopt.dds.md`) and for reverse-documented modules awaiting human review.
- `active`: authoritative. If code contradicts an `active` document, the code is a defect (manifesto [1].1). An `active` document has every required section of its tier template present and non-empty (`## [0]`–`## [3]` for product and architecture, `## [0]`–`## [2]` for modules and for `product-constraints`; a section with only a bare `<tag>` line counts as empty) and, for modules, every `sources:` glob matching at least one file in the repository. ENFORCED (`draft` documents receive warnings instead)
- `deprecated`: archived under `.dds/archive/`, kept for history and Tombstone resolution. An `active` document MUST NOT list a `deprecated` id in `dependencies`. ENFORCED

## [4] TREE_LINE_GRAMMAR

Index files are named `<scope>.tree.dds.md` (root index: `.dds/tree.dds.md`) and carry `type: tree`. After the frontmatter, the body consists of exactly one H1, optional HTML comments (`<!-- ... -->`), blank lines, list lines, and, only in a deprecated tree under `archive/`, the DEPRECATED banner line (`> ...`). Three list-line shapes are valid (ENFORCED):

1. **Document entry:** `- [relative/path/file.dds.md]: One-sentence description.`
2. **Subtree pointer:** `- [path/to/folder/]: One-sentence description.` → resolves to `path/to/folder/<folder>.tree.dds.md`, where `<folder>` is the LAST path segment (`epics/user-onboarding/` → `epics/user-onboarding/user-onboarding.tree.dds.md`).
3. **Tombstone:** `- [DEPRECATED -> .dds/archive/<path>]: Reason the document was retired.`

Paths in shapes 1 and 2 are relative to the tree file. Tombstone paths are relative to the repository root.
Every `.dds.md` document (all types except `tree`, `meta`, and files under `archive/`) MUST be indexed by exactly one entry in the tree of its own folder. Every entry MUST resolve to an existing file. Every tree except the root MUST be reachable from `.dds/tree.dds.md` through exactly one chain of subtree pointers; an unreachable tree is orphaned knowledge. ENFORCED
When every entry of a local tree has become a Tombstone, the tree itself moves under `archive/` as a deprecated document and the parent pointer becomes a Tombstone to it (deprecate protocols, step [3].4); archived trees are exempt from the reachability rule.
`.dds/meta/` and `.dds/archive/` are NOT indexed by trees; the manifesto and the Tombstones are their entry points.
The `.dds/modules/` root holds only `modules.tree.dds.md`; every module document lives in a sub-folder (STRICT_FOLDERIZATION, `dds.modules/rules.dds.md` [1].2). ENFORCED

## [5] EXAMPLES

**A module document:**

```markdown
---
id: modules-auth-login
type: module
status: active
dependencies: [architecture-core-database, product-user-onboarding]
sources: [src/auth/**]
last_updated: 2026-09-18
description: Login flow, session issuance, and lockout rules for the Auth domain.
---
```

**The same document after deprecation (now under `.dds/archive/modules/auth/login.dds.md`):**

```markdown
---
id: modules-auth-login
type: module
status: deprecated
dependencies: [architecture-core-database, product-user-onboarding]
sources: [src/auth/**]
last_updated: 2026-11-02
deprecated_date: 2026-11-02
original_path: .dds/modules/auth/login.dds.md
description: Login flow, session issuance, and lockout rules for the Auth domain.
---

> ⚠️ DEPRECATED: This module was removed from the system on 2026-11-02.
```

**A local tree (`.dds/modules/auth/auth.tree.dds.md`):**

```markdown
---
id: tree-modules-auth
type: tree
status: active
dependencies: []
last_updated: 2026-11-02
description: Index of the Auth domain modules.
---

# MODULES_AUTH_TREE

- [DEPRECATED -> .dds/archive/modules/auth/login.dds.md]: Password login replaced by passkeys.
- [passkey.dds.md]: Passkey registration and assertion flow for the Auth domain.
- [session/]: Session storage and refresh sub-domain.
```

# END_OF_DIRECTIVE
