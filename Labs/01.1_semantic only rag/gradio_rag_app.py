import gradio as gr

from rag_app import answer, load_local_index, retrieve_semantic


SUGGESTED_PROMPTS = [
    "What does SEC-114 require for laptops?",
    "Summarize remote work data handling expectations for employees.",
    "How is error E-4012 resolved for ContosoPrint X200?",
    "Find every page across all six documents where the exact phrase 'ContosoPrint X200' appears, and give a full per-document count.",
    "List every policy effective after 2026-08-01 with version and owner in a table.",
]


def run_rag(question):
    if not question.strip():
        raise gr.Error("Please enter a question.")

    documents = load_local_index()
    scored_chunks = retrieve_semantic(question, documents, top_k=12)
    response = answer(question, scored_chunks)
    return f"### Answer\n\n{response}"


def build_demo():
    with gr.Blocks(title="Semantic only RAG - Visual Tester") as demo:
        gr.Markdown("# Semantic only RAG: Visual Tester")
        question = gr.Textbox(
            label="Question",
            lines=4,
            placeholder="Ask a question...",
        )
        run_button = gr.Button("Run RAG", variant="primary")
        output = gr.Markdown()

        with gr.Accordion("Suggested prompts", open=False):
            gr.Examples(
                examples=[[item] for item in SUGGESTED_PROMPTS],
                inputs=question,
                label="Click a prompt to copy it into the question box",
            )

        run_button.click(run_rag, inputs=question, outputs=output)
        question.submit(run_rag, inputs=question, outputs=output)

    return demo


if __name__ == "__main__":
    build_demo().launch()
