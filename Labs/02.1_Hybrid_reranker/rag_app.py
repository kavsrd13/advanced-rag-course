import os
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from dotenv import load_dotenv
from openai import AzureOpenAI


load_dotenv(Path(__file__).with_name(".env"), override=True)

openai_client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"].replace("/openai/v1", ""),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
)
search_client = SearchClient(
    os.environ["AZURE_SEARCH_ENDPOINT"],
    os.environ["AZURE_SEARCH_INDEX"],
    AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"]),
)


def answer(question, chunks):
    context = "\n\n".join(
        f"[{chunk['policyId']}] {chunk['content']}" for chunk in chunks
    )
    response = openai_client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        messages=[
            {"role": "system", "content": "Answer only from the evidence. Cite actual policy IDs in brackets, such as [MAN-X200]. If evidence is missing, say so."},
            {"role": "user", "content": f"Question: {question}\n\nEvidence:\n{context}"},
        ],
    )
    return response.choices[0].message.content


def retrieve_hybrid(question):
    embedding = openai_client.embeddings.create(
        model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        input=[question],
    ).data[0].embedding

    keyword_results = search_client.search(
        search_text=question,
        filter="product eq 'ContosoPrint X200'",
        top=50,
        select=["id"],
    )
    keyword_scores = {
        item["id"]: item.get("@search.score") for item in keyword_results if item.get("id")
    }

    vector_results = search_client.search(
        search_text="",
        vector_queries=[
            VectorizedQuery(vector=embedding, k_nearest_neighbors=50, fields="contentVector")
        ],
        filter="product eq 'ContosoPrint X200'",
        top=50,
        select=["id"],
    )
    vector_scores = {
        item["id"]: item.get("@search.score") for item in vector_results if item.get("id")
    }

    results = search_client.search(
        search_text=question,
        vector_queries=[
            VectorizedQuery(vector=embedding, k_nearest_neighbors=12, fields="contentVector")
        ],
        query_type="semantic",
        semantic_configuration_name="rag-semantic-config",
        filter="product eq 'ContosoPrint X200'",
        top=12,
        select=["id", "policyId", "title", "content", "source", "product"],
    )
    candidates = [dict(result) for result in results]
    for candidate in candidates:
        candidate["keyword_score"] = keyword_scores.get(candidate["id"])
        candidate["vector_score"] = vector_scores.get(candidate["id"])
        candidate["hybrid_score"] = candidate.get("@search.score")
        candidate["reranker_score"] = candidate.get("@search.reranker_score")

    selected = candidates[:6]
    return candidates, selected


def main():
    question = "How is error E-4012 resolved?"
    candidates, selected = retrieve_hybrid(question)

    print("CANDIDATES RETRIEVED:", len(candidates))
    print("CHUNKS AFTER SELECTION:", len(selected))
    response = answer(question, selected).encode("ascii", errors="replace").decode("ascii")
    print("\nANSWER\n", response)


if __name__ == "__main__":
    main()
