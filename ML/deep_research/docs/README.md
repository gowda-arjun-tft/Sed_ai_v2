# Deep Research documentation

Five documents. `markdown/` holds the detailed source of record; `html/` holds the same content rendered for reading and sharing. Edit the Markdown and regenerate the HTML — never the other way round.

| Document | Status | What it answers |
| --- | --- | --- |
| [Deep Research Target Architecture](markdown/260908_Deep_Research_Target_Architecture_ENG.md) | Proposed, not implemented | How the whole engine should work: three inputs, three layers, the 15 phase handoffs, the harness, the memory boundary and the saved artifact layout. Start here. |
| [Layer 2 Domain Design and Fact Memory](markdown/260908_Layer2_Domain_Design_And_Fact_Memory_ENG.md) | Proposed, not implemented | How Layer 2 decides domains dynamically, routes facts, reviews them page by page, and keeps exact facts outside the context window. The 200K/250K input boundary in detail. |
| [Document Ingestion Design](markdown/260908_Document_Ingestion_Design_ENG.md) | Recommended, not implemented | Why PDFs are currently unreadable, and the tiered extractor, `read_source` contract, artifact schema, limits and failure handling that fix it. |
| [Layer 3 and Layer 4 World Model Redesign](markdown/260908_Layer3_Layer4_World_Model_Redesign_ENG.md) | Audit plus recommendations | What the live pipeline actually produced, why the place-and-world model is thin, and the smallest prompt and architecture changes that widen it. Includes a prompt-by-prompt change map. |
| [Layer 3 Cost and Context Baseline](markdown/260908_Layer3_Cost_And_Context_Baseline_ENG.md) | Describes the implemented pipeline | What runs today, what it costs, which parts of the plain-research redesign shipped, and how eviction and summarization are configured. |

## Reading order

- **New to the project:** target architecture → cost and context baseline (what exists now) → world model redesign (what is wrong with it).
- **Implementing ingestion:** document ingestion design, then section 3 of the world model redesign for the measured urgency.
- **Implementing Layer 2:** target architecture sections 3 and 9, then the Layer 2 design in full.
- **Changing prompts:** section 11 of the world model redesign.

## Conventions

- File names follow `YYMMDD_Speaking_Title_ENG`. The date is the day the document was issued in its current form; each document states its own evidence dates and what it supersedes.
- Every document declares its status in the first line: proposed, recommended, implemented, or an audit.
- Historical measurements are labelled as historical. Superseded design documents are removed rather than kept as archives; their content lives in git history.
- Prompts, plugins and module READMEs are code and stay beside the code. This folder holds design and audit documents only.

## Jira handover packs

- [SEDAI-1140 Jira update](jira/SEDAI-1140_Jira_Update.md) — copy-ready description,
  subtasks, acceptance criteria, test coverage and completion comment.
- [SEDAI-1140 Layer 2 architecture](jira/SEDAI-1140_Layer_2_Architecture.md) — compact
  implemented architecture attachment for review or Jira upload.
