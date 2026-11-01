import os
import sys
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
    os.environ["AZURE_SEARCH_HIERARCHY_INDEX"],
    AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"]),
)


def main():
    question = " ".join(sys.argv[1:]) or (
        "Why did X200 E-4012 incidents fall from April to June, "
        "and what should support do if E-4012 occurs again?"
    )
    embedding = openai_client.embeddings.create(
        model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        input=[question],
    ).data[0].embedding
    vector_query = VectorizedQuery(
        vector=embedding,
        k_nearest_neighbors=5,
        fields="contentVector",
    )

    # First retrieve small document summaries to locate relevant documents.
    summary_results = search_client.search(
        search_text=question,
        vector_queries=[vector_query],
        query_type="semantic",
        semantic_configuration_name="rag-semantic-config",
        filter="level eq 'summary'",
        top=3,
        select=["policyId", "documentId", "content", "source", "level"],
    )
    summaries = [dict(result) for result in summary_results]
    # Keep search ranking: a set would scramble which parent documents we open.
    document_ids = list(dict.fromkeys(item["documentId"] for item in summaries))

    # Search each selected document separately so each parent contributes details.
    details = []
    for document_id in document_ids:
        detail_results = search_client.search(
            search_text=question,
            vector_queries=[vector_query],
            query_type="semantic",
            semantic_configuration_name="rag-semantic-config",
            filter=f"documentId eq '{document_id}' and level eq 'leaf'",
            top=3,
            select=["policyId", "documentId", "content", "source", "level"],
        )
        details.extend(dict(result) for result in detail_results)

    # Summaries route the search; original detail chunks support the final answer.
    context = "\n\n".join(
        f"[{item['policyId']}] {item['content']}" for item in details
    )
    response = openai_client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer only from the detail evidence. Cite the exact bracketed "
                    "policy IDs shown in the evidence, such as [MAN-X200] or "
                    "[OPS-Q2-2026]. Never write the placeholder [POLICY_ID]. "
                    "If evidence is missing, say so. Use ASCII punctuation."
                ),
            },
            {"role": "user", "content": f"Question: {question}\n\nEvidence:\n{context}"},
        ],
    )

    print("SUMMARY MATCHES:", [item["policyId"] for item in summaries])
    print("SELECTED DOCUMENTS:", document_ids)
    print("DETAIL CHUNKS:", [item["policyId"] for item in details])
    answer = response.choices[0].message.content.translate(
        str.maketrans({"→": "->", "–": "-", "—": "-", "≈": "about "})
    ).encode(
        "ascii", errors="replace"
    ).decode("ascii")
    print("\nANSWER\n", answer)


if __name__ == "__main__":
    main()
