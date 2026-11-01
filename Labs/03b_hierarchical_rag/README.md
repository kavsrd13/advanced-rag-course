# Lab 03B: hierarchical RAG

This exercise has two levels in one Search index:

```text
Document summary (parent) -> PDF detail chunks (children)
```

`build_index.py` reads each PDF, makes detail chunks, and asks the model for one short **routing summary** per document. Each summary and its chunks share the same `documentId`.

`rag_app.py` searches summaries first, keeps the top parent documents in ranked order, then searches detail chunks **inside each parent**. The final answer uses original detail chunks, with policy ID citations. Summaries help choose where to look; they are not final evidence.

Use this question to make the route visible:

> Why did X200 E-4012 incidents fall from April to June, and what should support do if E-4012 occurs again?

The answer needs the Q2 incident review (`OPS-Q2-2026`) for the trend and cause and the X200 manual (`MAN-X200`) for recovery steps. The run prints summary matches, selected parents, and detail chunks. Check that both documents appear. If one is missing, inspect the generated summaries and search ranking before trusting the answer.

## Run

From the course folder, after configuring this lab's `.env`:

```powershell
.\.venv\Scripts\python .\03b_hierarchical_rag\build_index.py
.\.venv\Scripts\python .\03b_hierarchical_rag\rag_app.py
```

Try a different question:

```powershell
.\.venv\Scripts\python .\03b_hierarchical_rag\rag_app.py "What is the trend in X200 incidents across Q2?"
```

## Teach in this order

1. Show one source PDF and its short summary plus several chunks.
2. Explain the shared `documentId` as the parent-child link.
3. Run the app and read the three printed stages from top to bottom.
4. Show that the final prompt contains detail chunks only.
5. Change the question and observe whether different summaries are selected.

With six small PDFs, this lab demonstrates the retrieval route. It does not prove that hierarchy improves answer quality or speed over flat search; compare those with a larger corpus and a fixed evaluation set.
