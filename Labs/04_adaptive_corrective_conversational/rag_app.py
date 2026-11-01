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


def ask_model(system_prompt, user_prompt):
    response = openai_client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


def retrieve(question, mode, top_k):
    options = {
        "search_text": question if mode != "vector" else "",
        "top": top_k,
        "select": ["policyId", "content", "source"],
    }

    if mode in {"vector", "hybrid"}:
        embedding = openai_client.embeddings.create(
            model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
            input=[question],
        ).data[0].embedding
        options["vector_queries"] = [
            VectorizedQuery(
                vector=embedding,
                k_nearest_neighbors=top_k,
                fields="contentVector",
            )
        ]

    if mode in {"semantic", "hybrid"}:
        options["query_type"] = "semantic"
        options["semantic_configuration_name"] = "rag-semantic-config"

    return [dict(result) for result in search_client.search(**options)]


def main():
    question = "Can a contractor download restricted data to an unmanaged device?"

    # Step 1: Choose retrieval depth from question complexity.
    complexity = ask_model(
        "Classify the question as simple, moderate, or complex. Return one word.",
        question,
    ).lower()
    if "simple" in complexity:
        mode, top_k = "keyword", 4
    elif "complex" in complexity:
        mode, top_k = "hybrid", 8
    else:
        mode, top_k = "semantic", 6

    # Step 2: Retrieve and ask the model whether the evidence is good enough.
    chunks = retrieve(question, mode, top_k)
    context = "\n\n".join(chunk["content"] for chunk in chunks)
    quality = ask_model(
        "Classify the evidence as sufficient, ambiguous, or insufficient. Return one word.",
        context,
    ).lower()

    # Step 3: Rewrite and retrieve again when evidence is weak.
    rewritten_question = None
    if quality.strip() != "sufficient":
        rewritten_question = ask_model(
            "Rewrite the question for better document retrieval. Return one sentence.",
            question,
        )
        chunks = retrieve(rewritten_question, "hybrid", 8)

    final_context = "\n\n".join(
        f"[{chunk['policyId']}] {chunk['content']}" for chunk in chunks
    )
    answer = ask_model(
        "Answer only from the evidence. Cite actual policy IDs in brackets, such as [SEC-114]. If evidence is missing, say so.",
        f"Question: {question}\n\nEvidence:\n{final_context}",
    )

    print("COMPLEXITY:", complexity)
    print("RETRIEVAL MODE:", mode)
    print("EVIDENCE QUALITY:", quality)
    print("REWRITTEN QUESTION:", rewritten_question)
    print("\nANSWER\n", answer)


if __name__ == "__main__":
    main()
