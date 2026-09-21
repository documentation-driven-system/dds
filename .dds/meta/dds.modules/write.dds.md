---
id: meta-modules-write
type: meta
status: active
dependencies: [meta-modules-rules]
last_updated: 2026-09-18
description: RAG-optimized, machine-readable protocol for folderization, semantic formatting, recursive indexing, and pre-flight self-correction of modules.
---

# SYSTEM_DIRECTIVE: MODULES_WRITE_AND_INDEX_PROTOCOL

## [0] DEFINITION & SCOPE

This document instructs the EXECUTOR (AI Agent or Human) on EXACTLY how to create, format, and index a NEW document within the `.dds/modules/` domain.
EXECUTOR MUST process operations sequentially: FOLDERIZE -> FORMAT (RAG-OPTIMIZED) -> RECURSIVE_INDEX -> PRE-FLIGHT_SELF_CORRECTION.

## [1] FOLDERIZATION_PROTOCOL (WITH NESTING)

EXECUTOR MUST NOT place feature documents directly into `.dds/modules/` (only `modules.tree.dds.md` lives there). Every distinct feature MUST have its own sub-directory.
IF a domain is highly complex, EXECUTOR MAY create nested sub-domains to maintain modularity.

1. `TARGET_PATH` = `.dds/modules/[domain_name]/` OR `.dds/modules/[domain_name]/[sub_domain]/` (e.g., `modules/payment/stripe/`)
2. FILE_NAME = `[kebab-case-feature-name].dds.md`

## [2] RAG_OPTIMIZED_LINGUISTICS (MACHINE PERCEPTION)

To ensure each section keeps its meaning when retrieved alone, EXECUTOR MUST adhere to these linguistic rules:

1. **CHUNK-LOCAL REFERENTS:** EXECUTOR MUST NOT use a pronoun ("It", "This", "They", "These") whose referent lies outside the current `##`/`###` section; name the component at least once per section before any pronoun.
   *Violation:* "This component processes the data."
   *Correct:* "The `AuthLogin` component processes the user payload."
2. **CONTEXT-BEARING HEADERS:**
   Headers MUST encapsulate the domain context.
   *Violation:* `### Error Handling`
   *Correct:* `### [Auth_Login] Module: Error Handling Constraints`
3. **TONE & VOICE:** Prefer imperative verbs and active voice. Use passive voice only when the actor is unknown or irrelevant.
4. **HEADER DEPTH LIMIT (MAX H3):** EXECUTOR MUST NOT use headers deeper than `###` (Heading 3). This is a convention that keeps every section large enough to stand alone when retrieval tools split on headings. Use bold text or lists for further hierarchy.

## [3] MANDATORY_STRUCTURED_TEMPLATE

Every new `.dds.md` file MUST adhere strictly to the following layout. XML-like tags (e.g., `<logic_flow>`) MAY be used internally to strictly bound context for LLMs.

**TEMPLATE:**

```markdown
---
id: modules-[domain-name]-[feature-name]
type: module
status: active
dependencies: [architecture-DOMAIN-NAME, product-EPIC-NAME]
sources: [src/DOMAIN-NAME/**]
last_updated: [YYYY-MM-DD]
description: [One sentence, reused by the index tree.]
---

# [MODULE_NAME]: [FEATURE_TITLE]

## [0] CONTEXT_AND_PURPOSE
The [Specific_Component_Name] is responsible for [Specific_Action] within the [Domain] boundary.

## [1] TECHNICAL_CONSTRAINTS
<constraints>
- [Constraint 1: Explicitly state the subject and limitation]
- [Constraint 2]
</constraints>

## [2] LOGIC_FLOW
1. [Subject] executes [Action] resulting in [Output].
2. [Subject] validates [Condition].
```

`dependencies` holds the **ids** (never paths) of the `architecture` and `product` documents this module obeys. `sources` (optional) lists the code globs this document governs; `dds.py check --coverage` and `--sync` use it. `description` is the sentence the index tree shows.

## [4] RECURSIVE_INDEXING_ROUTINE (NESTED TREE PROPAGATION)

Whenever a NEW file or folder is created, EXECUTOR MUST update the index trees RECURSIVELY from the deepest level up to the root.

**INDEX_UPDATE_STEPS:**
IF a required tree file does not exist, CREATE it with `type: tree` frontmatter (`id: tree-<scope>`) per `schema.dds.md` [4]. Entry syntax: `- [path]: description`; subtree pointer: `- [folder/]: description`.
IF a new `.dds.md` file is added to an EXISTING folder:

   1. OPEN local tree: `[TARGET_PATH]/[folder_name].tree.dds.md`
   2. APPEND file path AND a 1-sentence description containing **Semantic Keywords**.

IF a NEW NESTED sub-folder is created (Sub-Domain Initialization):

   1. CREATE deep local tree: `[TARGET_PATH]/[sub_domain].tree.dds.md`
   2. OPEN parent tree: `.dds/modules/[domain_name]/[domain_name].tree.dds.md`
   3. APPEND pointer to the new local tree.
   *SYNTAX_CONSTRAINT: Pointers MUST be appended using this exact format: `- [[folder_name]/]: [1-sentence description of the sub-domain]`*
   4. CONTINUE RECURSIVELY up to the Master Root Tree.

IF a NEW MAIN sub-folder is created (Domain Initialization):

   1. CREATE local tree: `.dds/modules/[domain_name]/[domain_name].tree.dds.md`
   2. OPEN parent tree: `.dds/modules/modules.tree.dds.md`
   3. APPEND pointer to the new local tree.
   4. OPEN Master Root Tree: `.dds/tree.dds.md`
   5. VERIFY/APPEND that `modules.tree.dds.md` is properly linked.
   *CONSTRAINT: EXECUTOR MUST NEVER modify `manifesto.dds.md` during this routine.*

## [5] PRE-FLIGHT_SELF_CORRECTION (VALIDATION LOOP)

AFTER generating the document content and BEFORE saving or committing, EXECUTOR MUST perform a self-audit to prevent context degradation.

**VALIDATION_STEPS:**

1. **Scan for Referents:** Does any pronoun refer to a subject named outside its section? -> IF YES, name the subject in that section.
2. **Scan for Header Depth:** Are there any `####` or deeper headers? -> IF YES, flatten to `###` and use lists or bold text instead.
3. **Scan for Contextless Headers:** Do all `##` and `###` headers explicitly contain the module/feature name? -> IF NO, append the context.
4. **Scan for content and sources:** Does every required section hold content, and does every `sources:` glob match at least one file? -> IF NO, the document stays `draft`; `check` rejects an `active` document that fails either.

**FINAL_CHECK:** RUN `python .dds/meta/scripts/dds.py check` on the saved files. IF it fails, fix the reported errors.

*Output: EXECUTOR returns `STATUS: VALIDATED` ONLY IF all checks pass.*

# END_OF_DIRECTIVE
