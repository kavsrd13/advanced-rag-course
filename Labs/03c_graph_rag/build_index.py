import os
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from dotenv import load_dotenv
from openai import AzureOpenAI
from pypdf import PdfReader
from pyoxigraph import Literal, NamedNode, Quad, Store


LAB_FOLDER = Path(__file__).resolve().parent
COURSE_FOLDER = LAB_FOLDER.parent
PDF_FOLDER = COURSE_FOLDER / "Knowledge Base" / "PDF_Files"
METADATA_FILE = COURSE_FOLDER / "Knowledge Base" / "Lab_Support" / "metadata.csv"
GRAPH_DB = LAB_FOLDER / "graph_db"

# This lab reads credentials from its own .env file.
load_dotenv(LAB_FOLDER / ".env", override=True)

openai_client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"].replace("/openai/v1", ""),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
)
search_credential = AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"])


def create_index(index_name):
    """Create one index that supports filters, vectors, and semantic ranking."""
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=3072,
            vector_search_profile_name="rag-vector-profile",
        ),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="documentId", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="policyId", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="classification", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="product", type=SearchFieldDataType.String, filterable=True),
    ]

    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="rag-hnsw")],
            profiles=[
                VectorSearchProfile(
                    name="rag-vector-profile",
                    algorithm_configuration_name="rag-hnsw",
                )
            ],
        ),
        semantic_search=SemanticSearch(
            configurations=[
                SemanticConfiguration(
                    name="rag-semantic-config",
                    prioritized_fields=SemanticPrioritizedFields(
                        title_field=SemanticField(field_name="title"),
                        content_fields=[SemanticField(field_name="content")],
                    ),
                )
            ]
        ),
    )
    SearchIndexClient(
        os.environ["AZURE_SEARCH_ENDPOINT"],
        search_credential,
    ).create_or_update_index(index)


def read_pdf(path):
    """Read page text and keep the page number inside the text."""
    pages = PdfReader(path).pages
    return "\n".join(
        f"[Page {number}] {page.extract_text() or ''}"
        for number, page in enumerate(pages, start=1)
    )


def chunk_text(text, size=1400, overlap=220):
    """Split text into overlapping pieces so boundary information is preserved."""
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size].strip())
        if start + size >= len(text):
            break
        start += size - overlap
    return chunks


def add_embeddings(documents):
    """Add an embedding vector to every document in small batches."""
    for start in range(0, len(documents), 16):
        batch = documents[start : start + 16]
        response = openai_client.embeddings.create(
            model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
            input=[document["content"] for document in batch],
        )
        for document, item in zip(batch, response.data):
            document["contentVector"] = item.embedding


def upload(index_name, documents):
    """Upload documents to Azure AI Search."""
    client = SearchClient(
        os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name,
        search_credential,
    )
    for start in range(0, len(documents), 500):
        client.upload_documents(documents[start : start + 500])


def main():
    base_index = os.environ["AZURE_SEARCH_INDEX"]
    create_index(base_index)

    # Step 1: Turn every source PDF into searchable leaf chunks.
    leaf_documents = []
    metadata = pd.read_csv(METADATA_FILE)
    for _, row in metadata.iterrows():
        document_id = str(row["sourceFile"])
        source_path = PDF_FOLDER / f"{document_id}.pdf"
        chunks = chunk_text(read_pdf(source_path))

        for order, chunk in enumerate(chunks):
            leaf_documents.append(
                {
                    "id": f"{document_id}-leaf-{order}",
                    "title": str(row["title"]),
                    "content": chunk,
                    "source": source_path.name,
                    "documentId": document_id,
                    "policyId": str(row["documentId"]),
                    "classification": str(row["classification"]),
                    "product": "" if pd.isna(row["product"]) else str(row["product"]),
                }
            )

    # Step 2: Embed the chunks and upload them to this lesson's index.
    add_embeddings(leaf_documents)
    upload(base_index, leaf_documents)
    print("INDEX:", base_index, "| CHUNKS:", len(leaf_documents))

    # These source-backed relationships come from the Q2 review and X200 manual.
    facts = [
        ("Firmware 3.2", "causes", "E-4012", "OPS-Q2-2026"),
        ("E-4012", "affects", "X200", "OPS-Q2-2026"),
        ("E-4012", "appears_as", "nightly restarts", "OPS-Q2-2026"),
        ("Firmware 3.2.1", "fixes", "E-4012", "MAN-X200"),
        ("E-4012", "documented_in", "MAN-X200", "OPS-Q2-2026"),
        ("OPS-Q2-2026", "reports_declining_incidents_for", "X200", "OPS-Q2-2026"),
    ]

    # The embedded graph database persists beside this script; no server is needed.
    graph = Store(str(GRAPH_DB))
    graph.clear()
    label = NamedNode("urn:label")
    for name in {name for subject, _, target, _ in facts for name in (subject, target)}:
        graph.add(Quad(NamedNode("urn:entity:" + quote(name)), label, Literal(name)))
    for subject, relation, target, source in facts:
        graph.add(
            Quad(
                NamedNode("urn:entity:" + quote(subject)),
                NamedNode("urn:relation:" + relation),
                NamedNode("urn:entity:" + quote(target)),
                NamedNode("urn:source:" + source),
            )
        )
    print("GRAPH:", GRAPH_DB, "| RELATIONSHIPS:", len(facts))


if __name__ == "__main__":
    main()
