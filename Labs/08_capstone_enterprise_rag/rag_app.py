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
credential = AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"])
base_search = SearchClient(
    os.environ["AZURE_SEARCH_ENDPOINT"],
    os.environ["AZURE_SEARCH_INDEX"],
    credential,
)
hierarchy_search = SearchClient(
    os.environ["AZURE_SEARCH_ENDPOINT"],
    os.environ["AZURE_SEARCH_HIERARCHY_INDEX"],
    credential,
)


def incident_status(issue_code):
    statuses = {"E-4012": "Mitigated after firmware 3.2.1 rollout."}
    return statuses.get(issue_code, "No incident found.")


def main():
    question = "What policy and product evidence explains the incident, and what should we do next?"
    embedding = openai_client.embeddings.create(
        model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        input=[question],
    ).data[0].embedding
    vector_query = VectorizedQuery(
        vector=embedding,
        k_nearest_neighbors=8,
        fields="contentVector",
    )

    # Evidence source 1: detailed chunks from the normal index.
    base_results = base_search.search(
        search_text=question,
        vector_queries=[vector_query],
        query_type="semantic",
        semantic_configuration_name="rag-semantic-config",
        top=8,
        select=["policyId", "content", "source"],
    )
    base_chunks = [dict(result) for result in base_results]

    # Evidence source 2: document summaries from the hierarchy index.
    summary_results = hierarchy_search.search(
        search_text=question,
        vector_queries=[vector_query],
        filter="level eq 'summary'",
        top=3,
        select=["policyId", "content", "source"],
    )
    summary_chunks = [dict(result) for result in summary_results]

    # Evidence source 3: a classroom incident-status lookup.
    tool_result = incident_status("E-4012")

    document_evidence = "\n\n".join(
        f"[{chunk['policyId']}] {chunk['content']}"
        for chunk in base_chunks + summary_chunks
    )
    response = openai_client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        messages=[
            {
                "role": "system",
                "content": "Answer only from the supplied evidence. Cite policy IDs.",
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"Document evidence:\n{document_evidence}\n\n"
                    f"Incident tool result:\n{tool_result}"
                ),
            },
        ],
    )

    print("BASE CHUNKS:", len(base_chunks))
    print("SUMMARY CHUNKS:", len(summary_chunks))
    print("TOOL RESULT:", tool_result)
    print("\nANSWER\n", response.choices[0].message.content)


if __name__ == "__main__":
    main()
