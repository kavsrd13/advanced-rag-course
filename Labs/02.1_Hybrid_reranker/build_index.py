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

load_dotenv(LAB_FOLDER / ".env", override=True)

openai_client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"].replace("/openai/v1", ""),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
)
search_credential = AzureKeyCredential(os.environ["AZURE_SEARCH_API_KEY"])


def create_index(index_name):
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
    pages = PdfReader(path).pages
    return "\n".join(
        f"[Page {number}] {page.extract_text() or ''}"
        for number, page in enumerate(pages, start=1)
    )


def chunk_text(text, size=1400, overlap=220):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size].strip())
        if start + size >= len(text):
            break
        start += size - overlap
    return chunks


def add_embeddings(documents):
    for start in range(0, len(documents), 16):
        batch = documents[start : start + 16]
        response = openai_client.embeddings.create(
            model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
            input=[document["content"] for document in batch],
        )
        for document, item in zip(batch, response.data):
            document["contentVector"] = item.embedding


def upload(index_name, documents):
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

    add_embeddings(leaf_documents)
    upload(base_index, leaf_documents)
    print("INDEX:", base_index, "| CHUNKS:", len(leaf_documents))


if __name__ == "__main__":
    main()
