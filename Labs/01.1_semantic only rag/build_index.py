import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import AzureOpenAI
from pypdf import PdfReader


LAB_FOLDER = Path(__file__).resolve().parent
COURSE_FOLDER = LAB_FOLDER.parent
PDF_FOLDER = COURSE_FOLDER / "Knowledge Base" / "PDF_Files"
METADATA_FILE = COURSE_FOLDER / "Knowledge Base" / "Lab_Support" / "metadata.csv"
LOCAL_INDEX_FILE = LAB_FOLDER / "local_vector_index.json"

# This lab reads credentials from its own .env file.
load_dotenv(LAB_FOLDER / ".env", override=True)

openai_client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"].replace("/openai/v1", ""),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
)


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


def write_local_index(documents):
    with LOCAL_INDEX_FILE.open("w", encoding="utf-8") as file_handle:
        json.dump(documents, file_handle, ensure_ascii=False, indent=2)


def main():
    documents = []
    metadata = pd.read_csv(METADATA_FILE)
    for _, row in metadata.iterrows():
        document_id = str(row["sourceFile"])
        source_path = PDF_FOLDER / f"{document_id}.pdf"
        chunks = chunk_text(read_pdf(source_path))

        for order, chunk in enumerate(chunks):
            documents.append(
                {
                    "id": f"{document_id}-leaf-{order}",
                    "title": str(row["title"]),
                    "content": chunk,
                    "source": source_path.name,
                    "documentId": document_id,
                    "policyId": str(row["documentId"]),
                    "owner": str(row["owner"]),
                    "version": str(row["version"]),
                    "effectiveDate": str(row["effectiveDate"]),
                    "classification": str(row["classification"]),
                    "status": str(row["status"]),
                    "product": "" if pd.isna(row["product"]) else str(row["product"]),
                }
            )

    add_embeddings(documents)
    write_local_index(documents)
    print("LOCAL INDEX:", LOCAL_INDEX_FILE)
    print("CHUNKS:", len(documents))


if __name__ == "__main__":
    main()
