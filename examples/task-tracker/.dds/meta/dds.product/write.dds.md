---
id: meta-product-write
type: meta
status: active
dependencies: [meta-product-rules]
last_updated: 2026-09-18
description: RAG-optimized protocol for formatting, structuring, and indexing business requirements, user stories, and product epics.
---

# SYSTEM_DIRECTIVE: PRODUCT_WRITE_AND_INDEX_PROTOCOL

## [0] DEFINITION & SCOPE

This document instructs the EXECUTOR (AI Agent or Human) on EXACTLY how to create, format, and index a NEW document within the `.dds/product/` domain.
EXECUTOR MUST process operations sequentially: FOLDERIZE -> FORMAT (RAG-OPTIMIZED) -> RECURSIVE_INDEX -> PRE-FLIGHT_SELF_CORRECTION.

## [1] FLEXIBLE_FOLDERIZATION_PROTOCOL

Unlike the `modules` tier, the `product` tier supports both Global and Epic-specific documents.

1. **GLOBAL_DOCUMENTS:** High-level strategic files (e.g., `vision.dds.md`, `target-audience.dds.md`) MAY be placed directly in the root `.dds/product/` directory.
2. **EPIC_DOCUMENTS:** Specific business features or user journeys MUST be isolated in sub-directories.
   `TARGET_PATH` = `.dds/product/epics/[epic_name]/` (e.g., `product/epics/user-onboarding/`)
3. **CONSTRAINTS_DOCUMENT:** `.dds/product/constraints.dds.md` (id `product-constraints`) lists the non-negotiable constraints (security, legal and compliance, safety, physical) as imperative rules, each with its source (law, standard, contract, or policy). No KPI or tier may override an entry (manifesto [1].0). `gate: strict` requires this document to be `active`.
4. FILE_NAME = `[kebab-case-name].dds.md`

## [2] STRATEGIC_LINGUISTICS (MACHINE PERCEPTION)

To ensure each section keeps its meaning when retrieved alone, without confusing the AI with implementation details, EXECUTOR MUST adhere to these rules:

1. **TECHNOLOGY_AGNOSTICISM:** EXECUTOR MUST NOT mention specific coding languages, database types (e.g., SQL, MongoDB), or libraries (e.g., React, Tailwind). Use business terms: "Data Storage", "User Interface".
2. **CHUNK-LOCAL REFERENTS:** EXECUTOR MUST NOT use a pronoun ("It", "This", "They") whose referent lies outside the current `##`/`###` section, because a section may be retrieved alone. Name the Persona or Feature at least once per section before any pronoun.
3. **CONTEXT-BEARING HEADERS:** Headers MUST encapsulate the business context (e.g., `### [B2B_Dashboard] Success Metrics`).
4. **HEADER DEPTH LIMIT:** MAX H3 (`###`). Use bolding or bullet points for deeper hierarchies.
5. **KPIS_ARE_TARGETS:** Write KPIs as measurable targets (`[Metric]: [Target]`), never as rules. A KPI resolves no conflict and overrides no document.

## [3] MANDATORY_STRUCTURED_TEMPLATE

Every new `.dds.md` file in the `product` domain MUST adhere to the following business-logic template.

**TEMPLATE:**

```markdown
---
id: product-[epic-or-global-name]
type: product
status: active
dependencies: []
last_updated: [YYYY-MM-DD]
description: [One sentence, reused by the index tree.]
---

# [PRODUCT/EPIC_NAME]: [TITLE]

## [0] BUSINESS_VISION_AND_VALUE
[1-2 sentences defining the ultimate business goal and the value it brings to the user or company. WHY are we building this?]

## [1] TARGET_PERSONAS
- **[Persona 1 Name]:** [Brief description of their needs and pain points].
- **[Persona 2 Name]:** [Brief description].

## [2] KEY_PERFORMANCE_INDICATORS (KPIs)
- [Metric 1]: [Target Goal - e.g., Increase user retention by 15%].
- [Metric 2]: [Target Goal].

## [3] USER_STORIES_AND_ACCEPTANCE_CRITERIA
<user_stories>
- **Story:** As a [Persona], I want to [Action], so that [Benefit].
- **Acceptance:** The system MUST allow [Outcome].
</user_stories>
```

`dependencies` is empty for a global document and may name other `product` ids for an epic that refines them (e.g., `[product-vision]`); a `product` document never depends on `architecture` or `module` documents (`schema.dds.md` [1]). `description` is the sentence the index tree shows.

**CONSTRAINTS_TEMPLATE** (for `.dds/product/constraints.dds.md`, id `product-constraints`): keep sections [0] and [2] of the template above, and replace [1] and [3] with one `## [1] CONSTRAINTS` section holding a `<constraints>` list. Each entry reads `- **C<n> <Short name> (<security | legal | compliance | safety | physical>):** The system MUST ... Source: <law, standard, contract, or policy>.` Section [2] states `None. Constraints are rules, not targets.`

## [4] RECURSIVE_INDEXING_ROUTINE

Whenever a NEW file or folder is created, EXECUTOR MUST update the index trees to maintain the global memory.

**INDEX_UPDATE_STEPS:**
IF a required tree file does not exist, CREATE it with `type: tree` frontmatter (`id: tree-<scope>`) per `schema.dds.md` [4]. Entry syntax: `- [path]: description`; subtree pointer: `- [folder/]: description`.
IF a new GLOBAL document is created directly in `product/`:

   1. OPEN the main tree: `.dds/product/product.tree.dds.md`
   2. APPEND file path AND a 1-sentence strategic description.

IF a new EPIC folder/file is created:

   1. CREATE/OPEN local tree: `.dds/product/epics/[epic_name]/[epic_name].tree.dds.md`
   2. APPEND the file path and description.
   3. OPEN parent tree: `.dds/product/product.tree.dds.md`
   4. VERIFY/APPEND the pointer to the new epic tree using the syntax: `- [epics/[epic_name]/]: [1-sentence description]`
   5. VERIFY that `product.tree.dds.md` is linked in the Master Root Tree (`.dds/tree.dds.md`).

## [5] PRE-FLIGHT_SELF_CORRECTION (VALIDATION LOOP)

AFTER generating the document and BEFORE saving, EXECUTOR MUST perform a self-audit.

**VALIDATION_STEPS:**

1. **Scan for Tech-Agnosticism:** Does the text contain coding frameworks, DB schema names, or API endpoint routes? -> IF YES, rewrite into abstract business requirements.
2. **Scan for Referents:** Does any pronoun refer to a subject named outside its section? -> IF YES, name the subject in that section.
3. **Scan for KPIs:** Are the goals measurable? -> IF NO, refine the KPIs.
4. **Scan for empty sections:** Does every required section hold content? -> IF NO, the document stays `draft`; `check` rejects an `active` document with a missing or empty section.

**FINAL_CHECK:** RUN `python .dds/meta/scripts/dds.py check` on the saved files. IF it fails, fix the reported errors.

*Output: EXECUTOR returns `STATUS: VALIDATED` ONLY IF all checks pass.*

# END_OF_DIRECTIVE
