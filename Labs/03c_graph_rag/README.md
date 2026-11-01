# Lab 03C: Graph RAG

The old version only asked the model to write relationship triples after Search had already found passages. It did not store or query a graph. This version uses **Pyoxigraph**, an embedded graph database saved in `graph_db`. It runs on Windows without Docker or a separate server.

```text
Question -> matching entity -> graph relationships -> source document IDs
         -> Azure AI Search passages from those documents -> cited answer
```

The graph has a few facts curated from the Q2 review (`OPS-Q2-2026`) and the X200 manual (`MAN-X200`). For example:

```text
Firmware 3.2 -> causes -> E-4012 [OPS-Q2-2026]
Firmware 3.2.1 -> fixes -> E-4012 [MAN-X200]
E-4012 -> documented in -> MAN-X200 [OPS-Q2-2026]
```

Each fact records its source document. The graph chooses which documents to search; the final answer uses passages from those documents, not graph facts alone.

## Run

From the course folder, after configuring this lab's `.env`:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python .\03c_graph_rag\build_index.py
.\.venv\Scripts\python .\03c_graph_rag\rag_app.py
```

Try another question containing a graph entity such as `X200`, `E-4012`, `Firmware 3.2`, or `MAN-X200`:

```powershell
.\.venv\Scripts\python .\03c_graph_rag\rag_app.py "What caused E-4012 and which firmware fixes it?"
```

## Teach in this order

1. Open the two PDFs and locate the facts represented by graph edges.
2. Show the small `facts` list in `build_index.py`, then run the builder. The graph is built once and saved on disk.
3. Show the graph query in `rag_app.py`: it traverses edges touching a named entity.
4. Run the app. Read `GRAPH ENTITIES`, `GRAPH FACT`, and `SEARCHED SOURCES` before the answer.
5. Ask about `X200` and compare the source filter. Remove one fact from the builder, rebuild, and observe the change.

This is a small **curated graph**, so it is easy to inspect. It does not automatically extract relationships from arbitrary PDFs. The app matches entity names that appear in the question; ask using the displayed graph names when experimenting.
