import gradio as gr

from rag_app import answer, retrieve_hybrid


SUGGESTED_PROMPTS = [
    "How is error E-4012 resolved?",
    "What were the key actions from the Q2 operations incident review?",
    "What governance controls are required for RAG security evaluations?",
]


def format_scores(selected):
    lines = ["### Hybrid scores (reranker ON)"]
    for index, chunk in enumerate(selected, start=1):
        keyword_score = chunk.get("keyword_score")
        vector_score = chunk.get("vector_score")
        hybrid_score = chunk.get("hybrid_score")
        reranker_score = chunk.get("reranker_score")
        keyword_text = "n/a" if keyword_score is None else f"{keyword_score:.4f}"
        vector_text = "n/a" if vector_score is None else f"{vector_score:.4f}"
        hybrid_text = "n/a" if hybrid_score is None else f"{hybrid_score:.4f}"
        reranker_text = "n/a" if reranker_score is None else f"{reranker_score:.4f}"
        lines.append(
            f"{index}. [{chunk['policyId']}] {chunk['source']}  \n"
            f"keyword={keyword_text}, vector={vector_text}, hybrid={hybrid_text}, reranker={reranker_text}"
        )
    return "\n\n".join(lines)


def run_rag(question):
    if not question.strip():
        raise gr.Error("Please enter a question.")

    _, selected = retrieve_hybrid(question)
    response = answer(question, selected)
    return f"### Answer\n\n{response}", format_scores(selected)


def build_demo():
    with gr.Blocks(title="Hybrid RAG Visual Tester (reranker ON)") as demo:
        gr.Markdown("# Hybrid RAG Visual Tester (reranker ON)")
        question = gr.Textbox(
            label="Question",
            lines=4,
            placeholder="Ask a question...",
        )
        run_button = gr.Button("Run RAG", variant="primary")
        with gr.Row():
            with gr.Column(scale=3):
                output = gr.Markdown()
            with gr.Column(scale=2):
                scores = gr.Markdown()

        with gr.Accordion("Suggested prompts", open=False):
            gr.Examples(
                examples=[[item] for item in SUGGESTED_PROMPTS],
                inputs=question,
                label="Click a prompt to copy it into the question box",
            )

        run_button.click(run_rag, inputs=question, outputs=[output, scores])
        question.submit(run_rag, inputs=question, outputs=[output, scores])

    return demo


if __name__ == "__main__":
    build_demo().launch()
