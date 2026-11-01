import json
import math
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AzureOpenAI


LAB_FOLDER = Path(__file__).resolve().parent
LOCAL_INDEX_FILE = LAB_FOLDER / "local_vector_index.json"

# This lab reads credentials from its own .env file.
load_dotenv(LAB_FOLDER / ".env", override=True)

openai_client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"].replace("/openai/v1", ""),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
)

DEFAULT_TOP_K = 12


def load_local_index():
    if not LOCAL_INDEX_FILE.exists():
        raise FileNotFoundError(
            f"Local index not found: {LOCAL_INDEX_FILE}. "
            "Run build_index.py first."
        )
    with LOCAL_INDEX_FILE.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def cosine_similarity(vector_a, vector_b):
    dot = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve_semantic(question, documents, top_k=DEFAULT_TOP_K):
    question_vector = openai_client.embeddings.create(
        model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        input=[question],
    ).data[0].embedding

    scored = []
    for document in documents:
        score = cosine_similarity(question_vector, document["contentVector"])
        scored.append((score, document))

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:top_k]


def answer(question, scored_chunks):
    context = "\n\n".join(
        f"[{chunk['policyId']}] {chunk['content']}" for _, chunk in scored_chunks
    )
    response = openai_client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        messages=[
            {
                "role": "system",
                "content": "Answer only from the context. Cite actual policy IDs in brackets, such as [SEC-114]. If evidence is missing, say so.",
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nContext:\n{context}",
            },
        ],
    )
    return response.choices[0].message.content


def main():
    question = "What does SEC-114 require for laptops?"
    documents = load_local_index()
    scored_chunks = retrieve_semantic(question, documents, top_k=DEFAULT_TOP_K)
    response = answer(question, scored_chunks)

    print("QUESTION\n", question)
    print("\nRETRIEVED CHUNKS")
    for score, chunk in scored_chunks:
        print(f"- score={score:.4f} [{chunk['policyId']}] {chunk['source']}")
    print("\nANSWER\n", response)


if __name__ == "__main__":
    main()
