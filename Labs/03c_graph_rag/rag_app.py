import os
import sys
from pathlib import Path
from urllib.parse import quote

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from dotenv import load_dotenv
from openai import AzureOpenAI
from pyoxigraph import Store


LAB_FOLDER = Path(__file__).resolve().parent
load_dotenv(LAB_FOLDER / ".env", override=True)

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


def main():
    question = " ".join(sys.argv[1:]) or (
        "How are X200 nightly restarts, E-4012, firmware 3.2, "
        "and the documented recovery connected?"
    )
    graph = Store(str(LAB_FOLDER / "graph_db"))

    # Find graph entity names mentioned in the question.
    names = [row["name"].value for row in graph.query(
        "SELECT ?name WHERE { ?entity <urn:label> ?name }"
    )]
    matched_names = sorted(name for name in names if name.lower() in question.lower())
    if not matched_names:
        print("No graph entity found in the question. Try one of:", sorted(names))
        return

    # Traverse relationships touching those entities and collect their source IDs.
    facts = set()
    for name in matched_names:
        entity = "urn:entity:" + quote(name)
        query = f"""
            SELECT ?aName ?relation ?bName ?source WHERE {{
                GRAPH ?source {{
                    ?a ?relation ?b .
                    FILTER(?a = <{entity}> || ?b = <{entity}>)
                }}
                ?a <urn:label> ?aName .
                ?b <urn:label> ?bName .
            }}
        """
        for row in graph.query(query):
            facts.add((
                row["aName"].value,
                row["relation"].value.removeprefix("urn:relation:").replace("_", " "),
                row["bName"].value,
                row["source"].value.removeprefix("urn:source:"),
            ))

    sources = sorted({source for _, _, _, source in facts})
    print("GRAPH ENTITIES:", matched_names)
    for subject, relation, target, source in sorted(facts):
        print(f"GRAPH FACT: {subject} -> {relation} -> {target} [{source}]")

    # Search only the documents linked to those graph facts.
    embedding = openai_client.embeddings.create(
        model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        input=[question],
    ).data[0].embedding
    source_filter = " or ".join(f"policyId eq '{source}'" for source in sources)
    results = search_client.search(
        search_text=question,
        vector_queries=[
            VectorizedQuery(
                vector=embedding,
                k_nearest_neighbors=8,
                fields="contentVector",
            )
        ],
        query_type="semantic",
        semantic_configuration_name="rag-semantic-config",
        filter=source_filter,
        top=8,
        select=["policyId", "content", "source"],
    )
    chunks = [dict(result) for result in results]
    evidence = "\n\n".join(
        f"[{chunk['policyId']}] {chunk['content']}" for chunk in chunks
    )

    # Graph facts guide retrieval; the answer must be grounded in source passages.
    response = openai_client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        messages=[
            {
                "role": "system",
                "content": "Answer only from the retrieved passages. Cite actual policy IDs in brackets, such as [MAN-X200]. If evidence is missing, say so.",
            },
            {"role": "user", "content": f"Question: {question}\n\nPassages:\n{evidence}"},
        ],
    )
    print("SEARCHED SOURCES:", sources)
    print("\nANSWER\n", response.choices[0].message.content)


if __name__ == "__main__":
    main()
