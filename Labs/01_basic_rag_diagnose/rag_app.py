import os
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from dotenv import load_dotenv
from openai import AzureOpenAI


# Each lab reads credentials from the .env file in its own folder.
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


def access_filter(user_id):
    """Allow public documents plus documents assigned to this classroom user."""
    return f"allowedUsers/any(u: search.in(u, 'all,{user_id}', ','))"


def retrieve_chunks(question, user_id, top_k=3):
    """Run keyword retrieval only inside the signed-in user's allowed content."""
    results = search_client.search(
        search_text=question,
        filter=access_filter(user_id),
        top=top_k,
        select=["policyId", "title", "content", "source", "classification"],
    )
    return [dict(result) for result in results]


def generate_answer(question, chunks):
    """Give only authorized retrieved chunks to the answer model."""
    if not chunks:
        return "No authorized document contains this answer."

    context = "\n\n".join(
        f"[{chunk['policyId']}] {chunk['content']}" for chunk in chunks
    )
    response = openai_client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer only from the context. Cite the actual policy ID "
                    "shown beside each passage, for example [SEC-114]. "
                    "Use only IDs present in the context. "
                    "If the context does not contain the answer, reply exactly: "
                    "No authorized document contains this answer."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nContext:\n{context}",
            },
        ],
    )
    return response.choices[0].message.content


def main():
    user_id = "alice"
    question = "What does SEC-114 require for laptops?"

    # Step 1: Keyword search is filtered before any evidence reaches the model.
    chunks = retrieve_chunks(question, user_id)

    # Step 2: Generate from authorized evidence only.
    answer = generate_answer(question, chunks)

    print("SIGNED-IN USER\n", user_id)
    print("ACCESS FILTER\n", access_filter(user_id))
    print("QUESTION\n", question)
    print("\nRETRIEVED CHUNKS")
    for chunk in chunks:
        print(f"- [{chunk['policyId']}] {chunk['source']} ({chunk['classification']})")
    print("\nANSWER\n", answer)


if __name__ == "__main__":
    main()
