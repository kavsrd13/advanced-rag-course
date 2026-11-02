"""Score saved RAG outputs using five Foundry RAG evaluator classes."""
import argparse
import csv
import json
import math
import os
from pathlib import Path

from azure.ai.evaluation import (
    DocumentRetrievalEvaluator, RetrievalEvaluator, GroundednessEvaluator,
    RelevanceEvaluator, ResponseCompletenessEvaluator,
)
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


def json_safe(value):
    # SDK judges can return NaN for an unscored response; JSON requires null.
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def document_inputs(row, sources):
    # Classroom document-level labels derived from the CSV expected-source list.
    # Deduplicate passages from the same PDF, preserving Search ranking.
    documents = {}
    for chunk in row["chunks"]:
        source = Path(chunk["source"]).stem
        documents.setdefault(source, {
            "document_id": source,
            "relevance_score": chunk.get("@search.reranker_score") or chunk.get("@search.score") or 0.0,
        })
    labels = [{"document_id": source, "query_relevance_label": 4 if source in row["expected_sources"] else 0}
              for source in sources]
    return {"retrieval_ground_truth": labels, "retrieved_documents": list(documents.values())}


def score_row(row, evaluators, sources):
    scores = {
        "retrieval": evaluators["retrieval"](query=row["query"], context=row["context"]),
        "groundedness": evaluators["groundedness"](query=row["query"], response=row["response"], context=row["context"]),
        "relevance": evaluators["relevance"](query=row["query"], response=row["response"]),
        "response_completeness": evaluators["response_completeness"](ground_truth=row["ground_truth"], response=row["response"]),
    }
    if row["expected_sources"]:
        scores["document_retrieval"] = evaluators["document_retrieval"](**document_inputs(row, sources))
    else:
        scores["document_retrieval"] = {"status": "not_applicable", "reason": "No relevant documents; inspect abstention instead of ranking metrics."}
    return scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "results/rag_outputs.jsonl")
    parser.add_argument("--limit", type=int, default=0, help="Use 1 for a paid live smoke test; 0 means every row")
    parser.add_argument("--reasoning-model", action="store_true", help="Enable SDK reasoning-model parameters for GPT-5/o-series judges")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=True)
    model = {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"].replace("/openai/v1", "").rstrip("/"),
        "api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "azure_deployment": os.getenv("AZURE_EVALUATION_DEPLOYMENT", os.environ["AZURE_OPENAI_DEPLOYMENT"]),
        "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
    }
    evaluators = {
        "document_retrieval": DocumentRetrievalEvaluator(ground_truth_label_min=0, ground_truth_label_max=4, top1_relevance_threshold=4, top3_max_relevance_threshold=4, total_retrieved_documents_threshold=1, total_ground_truth_documents_threshold=6),
        "retrieval": RetrievalEvaluator(model_config=model, is_reasoning_model=args.reasoning_model),
        "groundedness": GroundednessEvaluator(model_config=model, is_reasoning_model=args.reasoning_model),
        "relevance": RelevanceEvaluator(model_config=model, is_reasoning_model=args.reasoning_model),
        "response_completeness": ResponseCompletenessEvaluator(model_config=model, is_reasoning_model=args.reasoning_model),
    }
    with (ROOT.parent / "Knowledge Base/Lab_Support/metadata.csv").open(encoding="utf-8-sig", newline="") as file:
        sources = [item["sourceFile"] for item in csv.DictReader(file)]
    rows = [json.loads(line) for line in args.data.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        rows = rows[:args.limit]
    output = ROOT / "results/foundry_scores.jsonl"
    output.parent.mkdir(exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        for row in rows:
            result = json_safe({"query": row["query"], "scores": score_row(row, evaluators, sources)})
            file.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
            file.flush()
            print(row["query"], {name: value.get(name + "_score", value.get(name, value.get("status"))) for name, value in result["scores"].items()}, flush=True)
    print("Saved Foundry scores and judge reasoning to", output)


if __name__ == "__main__":
    main()
