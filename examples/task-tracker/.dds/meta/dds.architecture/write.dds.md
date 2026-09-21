---
id: meta-architecture-write
type: meta
status: active
dependencies: [meta-architecture-rules]
last_updated: 2026-09-18
description: RAG-optimized protocol for formatting, structuring, and indexing database schemas, infrastructure, and API contracts.
---

# SYSTEM_DIRECTIVE: ARCHITECTURE_WRITE_AND_INDEX_PROTOCOL

## [0] DEFINITION & SCOPE

This document instructs the EXECUTOR (AI Agent or Human) on EXACTLY how to create, format, and index a NEW document within the `.dds/architecture/` domain.
EXECUTOR MUST process operations sequentially: FOLDERIZE -> FORMAT (RAG-OPTIMIZED) -> RECURSIVE_INDEX -> PRE-FLIGHT_SELF_CORRECTION.

## [1] HYBRID_FOLDERIZATION_PROTOCOL

The `architecture` tier supports both system-wide and service-specific documents.

1. **GLOBAL_ARCHITECTURE:** High-level architectural documents (e.g., `tech-stack.dds.md`, `global-security.dds.md`, `core-database.dds.md`) MAY be placed directly in the root `.dds/architecture/` directory.
2. **SERVICE_SPECIFIC_ARCHITECTURE:** Isolated microservices, third-party integrations, or specific infrastructure domains MUST be placed in sub-directories.
   `TARGET_PATH` = `.dds/architecture/[service_or_domain_name]/` (e.g., `architecture/redis-cache/`)
3. FILE_NAME = `[kebab-case-name].dds.md`

## [2] ARCHITECTURAL_LINGUISTICS (MACHINE PERCEPTION)

To ensure semantic chunks retain exact technical meaning when vectorized, EXECUTOR MUST adhere to these STRICT rules:

1. **CHUNK-LOCAL REFERENTS:** EXECUTOR MUST NOT use a pronoun ("It", "This", "They") whose referent lies outside the current `##`/`###` section; name the table, column, or service at least once per section.
   *Violation:* "It stores the user password."
   *Correct:* "The `User_Auth` table stores the hashed user password."
2. **EXACT_DATA_TYPING:** When defining schemas, EXECUTOR MUST use explicit, platform-agnostic or specific data types (e.g., `VARCHAR(255)`, `UUIDv4`, `Float64`) rather than vague terms (e.g., "text", "number").
3. **CONTEXT-BEARING HEADERS:** Headers MUST encapsulate the architectural context (e.g., `### [Payment_DB] Transactions Table Schema`).
4. **HEADER DEPTH LIMIT:** MAX H3 (`###`). Use bullet points, bold text, or code blocks for deeper schema details.

## [3] MANDATORY_STRUCTURED_TEMPLATE

Every new `.dds.md` file in the `architecture` domain MUST adhere to the following template.

**TEMPLATE:**

```markdown
---
id: architecture-[domain-or-service-name]
type: architecture
status: active
dependencies: [product-EPIC-OR-GLOBAL-NAME]
last_updated: [YYYY-MM-DD]
description: [One sentence, reused by the index tree.]
---

# [ARCHITECTURE_DOMAIN]: [TITLE]

## [0] CONTEXT_AND_ALIGNMENT
[1-2 sentences defining what this infrastructure/data model is and WHICH business requirement (Product tier) it serves.]

## [1] TECH_STACK_AND_INFRASTRUCTURE
- **[Technology]:** [Version/Spec] - [Purpose within this domain].
- *Example:* **PostgreSQL:** 16.0 - Primary relational database for user data.

## [2] DATA_MODELS_AND_SCHEMAS
<schema>
### [Table/Collection_Name]
- `[column_name]` ([Data_Type]) - [Constraints: e.g., UNIQUE, NOT NULL] - [Description].
- `[column_name]` ([Data_Type]) - [Constraints] - [Description].
</schema>

## [3] GLOBAL_BOUNDARIES_AND_API_CONTRACTS
- [Boundary 1: e.g., All requests to this service MUST contain a valid Bearer JWT].
- [Boundary 2: e.g., Rate limiting is capped at 100 req/min per IP].
```

`dependencies` holds the **ids** (never paths) of the `product` documents this architecture serves; `dds.py impact` resolves ids to files. `description` is the sentence the index tree shows.

## [4] RECURSIVE_INDEXING_ROUTINE

Whenever a NEW file or folder is created, EXECUTOR MUST update the index trees to maintain the global memory map.

**INDEX_UPDATE_STEPS:**
IF a required tree file does not exist, CREATE it with `type: tree` frontmatter (`id: tree-<scope>`) per `schema.dds.md` [4]. Entry syntax: `- [path]: description`; subtree pointer: `- [folder/]: description`.
IF a new GLOBAL document is created directly in `architecture/`:

   1. OPEN the main tree: `.dds/architecture/architecture.tree.dds.md`
   2. APPEND file path AND a 1-sentence architectural description.

IF a new SERVICE/DOMAIN folder is created:

   1. CREATE/OPEN local tree: `.dds/architecture/[domain_name]/[domain_name].tree.dds.md`
   2. APPEND the file path and description.
   3. OPEN parent tree: `.dds/architecture/architecture.tree.dds.md`
   4. VERIFY/APPEND the pointer to the new local tree using the syntax: `- [[domain_name]/]: [1-sentence description]`
   5. VERIFY that `architecture.tree.dds.md` is linked in the Master Root Tree (`.dds/tree.dds.md`).

## [5] PRE-FLIGHT_SELF_CORRECTION (VALIDATION LOOP)

AFTER generating the document and BEFORE saving, EXECUTOR MUST perform a self-audit.

**VALIDATION_STEPS:**

1. **Scan for Feature Logic:** Does the text explain *how* a specific UI button or algorithmic function works? -> IF YES, remove it. Feature logic belongs in the `modules` tier.
2. **Scan for Exact Typing:** Are database columns defined with explicit data types? -> IF NO, refine them.
3. **Scan for Header Depth:** Are there `####` headers? -> IF YES, flatten to `###` and use lists.
4. **Scan for empty sections:** Does every required section hold content? -> IF NO, the document stays `draft`; `check` rejects an `active` document with a missing or empty section.

**FINAL_CHECK:** RUN `python .dds/meta/scripts/dds.py check` on the saved files. IF it fails, fix the reported errors.

*Output: EXECUTOR returns `STATUS: VALIDATED` ONLY IF all checks pass.*

# END_OF_DIRECTIVE
