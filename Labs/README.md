# Advanced RAG teaching labs

For the full course order, including Hugging Face, Microsoft Foundry, these RAG labs, and agent exercises, open the [exercise index](../exercise%20instruction/index.html).

Most RAG lessons have two independent Python files:

- `build_index.py`: read documents, chunk them, create embeddings, and upload to Azure AI Search.
- `rag_app.py`: retrieve evidence for a question and generate a cited answer.

Both load the local `.env`. Neither imports the other. Their connection is the Azure AI Search index named in that file. Lab 03C also shares a local graph database built by its index builder. Lab 05 creates two Search indexes and a Foundry IQ knowledge base, then connects a Foundry agent to its retrieval tool; use its separate environment and instructions.

Start with the [Lab 00 exercise](00_setup_environment/lab_00_exercise.html) if participants need to create Storage, Azure AI Search, a Foundry project, and the model deployments from Azure CLI.

## Run a lesson

From this course folder, create the environment once:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Configure the lesson's `.env`, then run its builder followed by its app:

```powershell
.\.venv\Scripts\python .\01_basic_rag_diagnose\build_index.py
.\.venv\Scripts\python .\01_basic_rag_diagnose\rag_app.py
```

For a complete student walkthrough, open [Lab 01 exercise](01_basic_rag_diagnose/lab_01_exercise.html). Lab 01 also has a visual tester with suggested "works well" and "likely to fail" prompts:

```powershell
.\.venv\Scripts\python .\01_basic_rag_diagnose\gradio_rag_app.py
```

Repeat the same two commands with the next lesson's folder name when it has a builder and app. Run the builder again when source documents, chunking, or index settings change. Run the app whenever you want to ask the demonstration question. Labs 03B and 03C also accept a question after the app filename. The exercise pages below give each lab's exact commands.

For the local semantic-only lab, run:

```powershell
.\.venv\Scripts\python ".\01.1_semantic only rag\build_index.py"
.\.venv\Scripts\python ".\01.1_semantic only rag\rag_app.py"
.\.venv\Scripts\python ".\01.1_semantic only rag\gradio_rag_app.py"
```

For the hybrid lab visual tester, run:

```powershell
.\.venv\Scripts\python ".\02_hybrid_semantic_metadata\gradio_rag_app.py"
```

For the hybrid lab with semantic reranker ON, run:

```powershell
.\.venv\Scripts\python ".\02.1_Hybrid_reranker\gradio_rag_app.py"
```

Most Azure lessons have their own `AZURE_SEARCH_INDEX`. Lab 02.1 reuses Lab 02's index, and Lab 03B uses its `AZURE_SEARCH_HIERARCHY_INDEX` only. The capstone uses both of its indexes. Existing indexes from the previous course layout are left in Azure.

## Lesson order

| Exercise | Data prepared | What students run and inspect |
|---|---|---|
| [00 · Azure setup](00_setup_environment/lab_00_exercise.html) | Student resource group, Storage, Search, Foundry, models | Create or reuse resources |
| [01 · User-aware keyword RAG](01_basic_rag_diagnose/lab_01_exercise.html) | Text chunks, vectors, per-document access metadata | Compare Alice and Bob in Gradio |
| [01.1 · Semantic-only RAG](01.1_semantic%20only%20rag/lab_01_1_exercise.html) | Local JSON vector index | Rank by cosine similarity without Search |
| [02 · Hybrid and metadata](02_hybrid_semantic_metadata/lab_02_exercise.html) | Searchable text, vectors, metadata | Compare keyword, vector, hybrid scores with reranker off |
| [02.1 · Semantic reranker](02.1_Hybrid_reranker/lab_02_1_exercise.html) | Reuses Lab 02's index | Compare evidence order with reranker on |
| [03B · Hierarchical RAG](03b_hierarchical_rag/lab_03b_exercise.html) | Leaf chunks and document summaries | Select summaries, then search selected documents' details |
| [03C · Graph-guided RAG](03c_graph_rag/lab_03c_exercise.html) | Search chunks and a local graph database | Traverse relationships to choose source documents |
| [04 · Adaptive and corrective RAG](04_adaptive_corrective_conversational/lab_04_exercise.html) | Text chunks and vectors | Inspect routing, evidence grading, query rewrite |
| [05 · Agentic RAG with Foundry IQ](05_agentic_rag_with_tools/lab_05_exercise.html) | Two Search indexes, knowledge sources, agent | Inspect Foundry IQ retrieval trace and agent tool call |
| [06 · Evaluation and security](06_evaluation_trace_security/lab_06_exercise.html) | Reuses Lab 02's index | Run `evaluate.py` and inspect filter effect |
| [07 · Architecture workshop](07_architecture_selection_workshop/lab_07_exercise.html) | No index needed | Run the decision rules on example workloads |
| [08 · Enterprise RAG capstone](08_capstone_enterprise_rag/lab_08_exercise.html) | Detailed chunks and document summaries | Combine retrieval, summaries, and a classroom lookup |

The `03a_multihop_foundry_iq` folder is absent from this course checkout, so it has no runnable exercise page. Lab 05 uses a Foundry agent and Foundry IQ. Lab 03B demonstrates document-level routing before chunk-level retrieval. Lab 03C uses an embedded graph database to route retrieval to documents connected by source-backed facts. Lab 04 is single-turn.

## Credentials

Every folder retains its own `.env`. The classic Azure-connected scripts use:

```text
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=2025-04-01-preview
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_API_KEY=
AZURE_SEARCH_INDEX=
AZURE_SEARCH_HIERARCHY_INDEX=
```

Use a text-embedding-3-large deployment producing 3,072-dimensional vectors for the classic vector labs. Lab 05 uses text indexes and its own Foundry project settings, documented in its README. The root `.env` is no longer used by the lessons. Credential files are excluded by `.gitignore`; distribute blank templates instead of keys to participants.

The security lesson demonstrates a fixed classification filter. Production access controls must derive permissions from trusted user identity before evidence reaches the model.

## Verification

```powershell
.\.venv\Scripts\python .\test_all_labs.py
.\.venv\Scripts\python -m pip check
python .\Workshop_Admin\validate_exercise_pages.py
```

The offline suite checks the classic Azure-connected labs, evaluation, and architecture scripts. The HTML validator checks every exercise link and embedded source block. After editing a teaching script, regenerate the pages with `python .\Workshop_Admin\generate_exercise_pages.py` and rerun the validator. Lab 05 has a separate Foundry IQ setup and live test described in its README.
