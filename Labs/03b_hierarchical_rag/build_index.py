import os
from pathlib import Path

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


LAB_FOLDER = Path(__file__).resolve().parent
COURSE_FOLDER = LAB_FOLDER.parent
PDF_FOLDER = COURSE_FOLDER / "Knowledge Base" / "PDF_Files"
METADATA_FILE = COURSE_FOLDER / "Knowledge Base" / "Lab_Support" / "metadata.csv"

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
        SimpleField(name="level", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunkOrder", type=SearchFieldDataType.Int32, filterable=True),
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
    hierarchy_index = os.environ["AZURE_SEARCH_HIERARCHY_INDEX"]
    create_index(hierarchy_index)

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
                    "level": "leaf",
                    "chunkOrder": order,
                }
            )

    # Step 2: Create one model-generated summary for each source document.
    summary_documents = []
    for document_id in metadata["sourceFile"]:
        document_chunks = [
            item for item in leaf_documents if item["documentId"] == document_id
        ]
        # Summarize the original PDF text, not overlapping chunks with repeated lines.
        source_text = read_pdf(PDF_FOLDER / f"{document_id}.pdf")
        response = openai_client.chat.completions.create(
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write a short routing summary of this document. Include its main "
                        "topics, exact product and incident IDs, important outcomes, "
                        "and references to other documents. Use only the source text."
                    ),
                },
                {"role": "user", "content": source_text},
            ],
        )
        first = document_chunks[0]
        summary_documents.append(
            {
                **first,
                "id": f"{document_id}-summary",
                "content": response.choices[0].message.content,
                "level": "summary",
                "chunkOrder": 0,
            }
        )

    # Step 3: Put summaries and their detail chunks in the same index.
    add_embeddings(leaf_documents)
    add_embeddings(summary_documents)
    upload(hierarchy_index, leaf_documents + summary_documents)

    print(
        "HIERARCHY INDEX:",
        hierarchy_index,
        "| SUMMARIES:", len(summary_documents),
        "| DETAIL CHUNKS:", len(leaf_documents),
    )


if __name__ == "__main__":
    main()
