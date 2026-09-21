# DDS: The Modules Tier (`.dds/modules/`)

The human guide to the Modules tier. The protocols in `.dds/meta/dds.modules/` are the source of truth; this page explains them.

---

## 1. What lives here

The Modules tier is the "How": one document per logical feature (Login, Create Task, Checkout), with the constraints the code must respect and the logic flow it follows. Software engineers and coding agents own it. The tier obeys both tiers above it, and it is the tier the code is checked against.

## 2. The rules of the tier (`rules.dds.md`)

- **Modular integrity.** One document per feature, never one per source file: `login.tsx`, `login.css`, and `login.test.ts` are one `login.dds.md`.
- **Strict folderization.** The tier root holds only `modules.tree.dds.md`; every document lives in `modules/<domain>/` (or a nested sub-domain), each folder with its own index tree. `check` enforces this.
- **Hierarchical obedience.** A module document never contradicts an architecture data model or a product rule.

## 3. The lifecycle of a module document

### A. Creating (`write.dds.md`)

- Follow the template: context and purpose (which component, which responsibility, serving which product story), technical constraints, logic flow. XML-like tags such as `<constraints>` may bound a block for the agent.
- Frontmatter follows `schema.dds.md`: `id: modules-<domain>-<feature>`, `dependencies:` holding the **ids** of the architecture and product documents the module obeys, `sources:` globs naming the code the document governs (`src/auth/**`), a one-sentence `description`.
- `sources:` is what makes the document checkable against the repository: `check --coverage` reports code no document governs, `check --sync` warns when governed code changed and the document did not.
- Index the document in its folder's tree; a new domain gets `modules/<domain>/<domain>.tree.dds.md` and a pointer from `modules.tree.dds.md`. Finish with `python .dds/meta/scripts/dds.py check`.

### B. Updating (`update.dds.md`)

- Change only the section the code change touched; keep historical constraints unless the new code contradicts them.
- **Reverse documentation.** A code change is translated into a rule, not pasted: "Added `if (user.age < 18) return false`" becomes "The system MUST block authentication for users under 18." The rule survives a rewrite of the code; the snippet does not.
- **Cross-domain integrity.** If the change alters a data model or a global API contract, the architecture document is updated too; the module tier cannot carry that change alone.
- Append a changelog line (ten entries, older ones in `git log`); if `locking: on`, lock and unlock through `dds.py`.
- **Stage the document with the code.** The commit hooks run `check --gate --staged`: code staged under an `active` document's `sources:` without that document staged fails the gate. There is no bypass; a human under `gate: warn` decides, and a `DDS-No-Doc:` trailer only records that decision.

### C. Retiring (`deprecate.dds.md`)

- `impact <id>` lists the documents that depend on the module. If any exist and this is a standalone retirement, the retirement is blocked until they are updated.
- If the retirement is part of a cascade from a product or architecture document (`CASCADE_MODE`), members of the same cascade set do not block each other; a dependent outside the set still does.
- The document gets `status: deprecated`, a date, its original path, a banner, and moves to `.dds/archive/modules/<domain>/...`. The tree line becomes a Tombstone with the reason. A domain whose tree is now all Tombstones moves to the archive too, and `modules.tree.dds.md` carries a Tombstone to it. The gate expects documents and code to move together, so the code under `sources:` is removed in the same change.

## 4. Writing for retrieval

Module documents are the ones agents read most, often one section at a time. Three conventions keep a section useful on its own:

- Headers carry their context: `### [Auth_Login] Error Handling`, not `### Error Handling`.
- Headers stop at H3; deeper structure uses bold text or lists (`check` warns above H3).
- A pronoun's subject is named inside the same section, because the section may be retrieved alone.

Active voice and imperative verbs are preferred; passive voice is for the cases where the actor is unknown or irrelevant.

## 5. Before saving

1. One document per feature, not per file?
2. `sources:` names the code this document governs?
3. Every header carries the feature name; none deeper than H3?
4. `check` passes.

## 6. Getting started

AI agents start at `.dds/meta/manifesto.dds.md`. Developers start at `.dds/tree.dds.md` and follow the pointers to the module they are changing; the code must match what the document says, or the document is updated first. `examples/task-tracker/.dds/modules/` shows a filled tier with `sources:` at full coverage and a retired domain.
