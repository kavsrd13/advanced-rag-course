"""Local checks: real SDK ranking math; fake judges for input routing only."""
import unittest
from evaluate_foundry import DocumentRetrievalEvaluator, document_inputs, score_row


class EvaluationTests(unittest.TestCase):
    def test_deduplication_preserves_ranking_and_labels(self):
        row = {"expected_sources": ["manual"], "chunks": [
            {"source": "manual.pdf", "@search.score": 3},
            {"source": "manual.pdf", "@search.score": 2},
            {"source": "policy.pdf", "@search.score": 1}]}
        inputs = document_inputs(row, ["manual", "policy"])
        self.assertEqual([x["document_id"] for x in inputs["retrieved_documents"]], ["manual", "policy"])
        self.assertEqual(inputs["retrieval_ground_truth"][1]["query_relevance_label"], 0)
        scores = DocumentRetrievalEvaluator(ground_truth_label_min=0, ground_truth_label_max=4, top1_relevance_threshold=4, top3_max_relevance_threshold=4, total_retrieved_documents_threshold=1, total_ground_truth_documents_threshold=6)(**inputs)
        self.assertTrue(scores)
        print("Actual SDK document retrieval metrics:", scores)

    def test_no_answer_does_not_score_document_ranking(self):
        def judge(**kwargs):
            return {"inputs": sorted(kwargs)}
        evaluators = {name: judge for name in ["retrieval", "groundedness", "relevance", "response_completeness"]}
        row = {"query": "Refund?", "context": "Manual", "response": "Insufficient evidence", "ground_truth": "Insufficient evidence", "expected_sources": []}
        scores = score_row(row, evaluators, [])
        self.assertEqual(scores["document_retrieval"]["status"], "not_applicable")
        self.assertEqual(scores["response_completeness"]["inputs"], ["ground_truth", "response"])
        self.assertEqual(set(scores), {"retrieval", "groundedness", "relevance", "response_completeness", "document_retrieval"})


if __name__ == "__main__":
    unittest.main()
