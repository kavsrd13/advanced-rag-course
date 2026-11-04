"""One teaching app: keyword, vector, and hybrid + semantic reranking."""
import argparse
import json
import os
from pathlib import Path
from time import perf_counter

import gradio as gr
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration, SearchField, SearchFieldDataType, SearchIndex,
    SearchableField, SemanticConfiguration, SemanticField,
    SemanticPrioritizedFields, SemanticSearch, SimpleField, VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery
from dotenv import load_dotenv
from openai import AzureOpenAI


HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env", override=True)
MODES = ["Keyword", "Vector", "Hybrid + rerank"]
PROMPTS = [
    "NS-7428",
    "A colleague has left the organisation. How do we stop them getting into our systems?",
    "For NS-7429 after replacing the finishing module, how can I continue without losing the queued job?",
    "Can a contractor edit Restricted forecasts on a personal laptop if employee BYOD is allowed?",
    "I left my notebook in a taxi. Can the finder view the information stored on it?",
    "How many days of parental leave does Northstar provide?",
]


def clients():
    index = os.environ["DEMO_SEARCH_INDEX"]
    if not index.startswith("rag-compare-"):
        raise ValueError("Use a dedicated DEMO_SEARCH_INDEX starting with rag-compare-.")
    key = AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"])
    search = SearchClient(os.environ["AZURE_SEARCH_ENDPOINT"], index, key)
    model = AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"].removesuffix("/openai/v1").rstrip("/"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
    )
    return search, model


def build_index():
    search, model = clients()
    documents = []
    for path in sorted((HERE / "data").glob("*.txt")):
        title, content = path.read_text(encoding="utf-8").split("\n", 1)
        documents.append({"id": path.stem, "title": title, "content": content.strip(), "source": path.name})
    vectors = model.embeddings.create(
        model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        input=[d["title"] + "\n" + d["content"] for d in documents],
    ).data
    for document, vector in zip(documents, vectors):
        document["contentVector"] = vector.embedding
    schema = SearchIndex(
        name=os.environ["DEMO_SEARCH_INDEX"],
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(name="source", type=SearchFieldDataType.String),
            SearchField(name="contentVector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        searchable=True, vector_search_dimensions=len(vectors[0].embedding),
                        vector_search_profile_name="vectors"),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
            profiles=[VectorSearchProfile(name="vectors", algorithm_configuration_name="hnsw")],
        ),
        semantic_search=SemanticSearch(configurations=[SemanticConfiguration(
            name="meaning",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[SemanticField(field_name="content")],
            ),
        )]),
    )
    index_client = SearchIndexClient(os.environ["AZURE_SEARCH_ENDPOINT"],
                                    AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"]))
    # Create a new demo index. Fail rather than overwrite an existing index/schema.
    index_client.create_index(schema)
    uploaded = search.upload_documents(documents)
    if not all(item.succeeded for item in uploaded):
        raise RuntimeError("Some uploads failed. Inspect the Search service before running the demo.")
    print(f"Created {schema.name}: {len(documents)} text files, {len(vectors[0].embedding)} dimensions.")


def retrieve(question, mode):
    search, model = clients()
    options = {"search_text": question, "top": 50, "select": ["id", "title", "content", "source"]}
    if mode != "Keyword":
        vector = model.embeddings.create(
            model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"], input=[question],
        ).data[0].embedding
        options["vector_queries"] = [VectorizedQuery(
            vector=vector, fields="contentVector", k_nearest_neighbors=50, exhaustive=True,
        )]
    if mode == "Vector":
        options["search_text"] = None  # No text query: genuinely vector-only.
    before = {}
    start = perf_counter()
    if mode == "Hybrid + rerank":
        # This extra request makes the before/after ranking visible for teaching.
        before = {r["id"]: rank for rank, r in enumerate(search.search(**options), 1)}
        options.update(query_type="semantic", semantic_configuration_name="meaning", semantic_error_mode="fail")
    hits = [dict(r) for r in search.search(**options)]
    elapsed = perf_counter() - start
    for hit in hits:
        hit["rerank_score"] = hit.get("@search.reranker_score", hit.get("@search.rerankerScore"))
        hit["before_rank"] = before.get(hit["id"])
    if mode == "Hybrid + rerank" and hits and hits[0]["rerank_score"] is None:
        raise RuntimeError("Semantic reranking did not return scores. Enable semantic ranker on the Search service.")
    return hits, elapsed


def generate(question, evidence):
    if not evidence:
        return "No matching evidence was retrieved."
    _, model = clients()
    context = "\n\n".join(f"[{d['id']}] {d['title']}\n{d['content']}" for d in evidence)
    response = model.chat.completions.create(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        messages=[
            {"role": "system", "content": "Answer briefly using only the supplied evidence. Cite document IDs in square brackets. Respect device, person and data-classification conditions. If the evidence does not answer the question, say: The supplied evidence does not contain the answer."},
            {"role": "user", "content": f"Question: {question}\n\nEvidence:\n{context}"},
        ],
    )
    return response.choices[0].message.content


def run_mode(question, mode, top_k, generate_answer):
    if not question.strip():
        raise gr.Error("Enter a question.")
    hits, seconds = retrieve(question, mode)
    selected = hits[:int(top_k)]
    answer = generate(question, selected) if generate_answer else "Answer generation is off. Inspect retrieval first."
    evidence = "\n\n---\n\n".join(f"**[{d['id']}] {d['title']}**\n\n{d['content']}" for d in selected) or "No passages."
    rows = [[rank, rank <= int(top_k), d["id"], d["title"], d.get("@search.score"),
             d["rerank_score"], d["before_rank"]] for rank, d in enumerate(hits, 1)]
    flow = {
        "Keyword": "Words → BM25 → selected evidence → answer",
        "Vector": "Question embedding → vector similarity → selected evidence → answer",
        "Hybrid + rerank": "Words + question embedding → RRF fusion → semantic reranking → selected evidence → answer",
    }[mode]
    trace = f"**{flow}**\n\nReturned {len(hits)} candidates; sent {len(selected)} passages to the model. Search calls: {seconds:.2f}s (excludes embeddings and generation; hybrid includes the teaching before-rerank request)."
    return answer, rows, evidence, trace


def compare_all(question, top_k, generate_answer):
    outputs = []
    for mode in MODES:
        answer, rows, evidence, trace = run_mode(question, mode, top_k, generate_answer)
        ranking = "\n".join(f"{r[0]}. `{r[2]}`" for r in rows[:int(top_k)]) or "No matching passages."
        outputs.append(f"## {mode}\n\n{ranking}\n\n### Answer\n{answer}\n\n### Selected evidence\n{evidence}")
    return outputs


def demo():
    with gr.Blocks(title="Three ways to retrieve: Northstar IT support") as ui:
        gr.Markdown("# One question, three RAG patterns\nFictional Northstar IT support. Use the same question and evidence count in each mode. Try exact codes, everyday paraphrases and conditional policies.")
        question = gr.Textbox(label="Question", lines=3, value=PROMPTS[1])
        with gr.Row():
            mode = gr.Dropdown(MODES, value="Keyword", label="Retrieval method")
            top_k = gr.Slider(1, 5, value=1, step=1, label="Passages given to the model")
            generate_answer = gr.Checkbox(value=True, label="Generate an answer (uses model tokens)")
        gr.Examples([[p] for p in PROMPTS], inputs=question, label="Click a test question")
        with gr.Tabs():
            with gr.Tab("Switch method"):
                run = gr.Button("Run selected method", variant="primary")
                trace = gr.Markdown()
                answer = gr.Markdown()
                ranking = gr.Dataframe(headers=["Rank", "Selected", "Document", "Title", "Search score", "Reranker score", "Hybrid rank before rerank"], interactive=False)
                evidence = gr.Markdown()
                run.click(run_mode, [question, mode, top_k, generate_answer], [answer, ranking, evidence, trace])
            with gr.Tab("Compare all three"):
                compare = gr.Button("Run all three (up to 3 answer calls)", variant="primary")
                with gr.Row():
                    outputs = [gr.Markdown() for _ in MODES]
                compare.click(compare_all, [question, top_k, generate_answer], outputs)
        gr.Markdown("**Read ranks and passages first.** BM25, vector, RRF and reranker scores have different scales; do not compare their raw numbers across methods. Vector Search scores here are Azure scores, not raw cosine similarity. Reranking can only reorder retrieved candidates. This app uses real Azure calls; it does not force any method to win. See prompts.txt for classroom questions and limitations.")
    return ui


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-index", action="store_true")
    parser.add_argument("--question", help="Compare retrieval in the terminal instead of starting Gradio")
    args = parser.parse_args()
    if args.build_index:
        build_index()
    elif args.question:
        for method in MODES:
            results, _ = retrieve(args.question, method)
            print(json.dumps({"mode": method, "top3": [{"id": r["id"], "score": r.get("@search.score"), "reranker": r["rerank_score"], "before": r["before_rank"]} for r in results[:3]]}))
    else:
        demo().launch()
