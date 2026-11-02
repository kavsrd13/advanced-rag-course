# Lab 06: evaluate a RAG pipeline with Foundry

Run commands from `Labs`. Reuse Lab 02's Search index and model settings in this folder's `.env`. No new Azure resources are created.

## 1. Capture real RAG answers

```powershell
.\.venv\Scripts\python.exe .\06_evaluation_trace_security\evaluate.py
```

This writes `results/rag_outputs.jsonl`: query, generated answer, exact evidence, expected answer, ranked chunks, latency and local checks. Source recall excludes the unsupported question. Citation presence requires a retrieved policy ID, but does not prove that a cited passage supports a claim. Inspect the refund question's abstention separately. The classification filter is a retrieval security demonstration, not a complete authorization test.

## 2. Install the Foundry evaluator SDK separately

```powershell
python -m venv .venv-eval
.\.venv-eval\Scripts\python.exe -m pip install -r .\06_evaluation_trace_security\requirements.txt
.\.venv-eval\Scripts\python.exe -m pip check
```

Keep this environment separate from the classic labs' pinned OpenAI dependencies. Add these settings to this lab's `.env`:

```dotenv
AZURE_EVALUATION_DEPLOYMENT=<judge-model-deployment>
```

The judge uses the existing Azure OpenAI endpoint and key. Choose an evaluator-supported chat deployment (for example GPT-4.1) on that resource; the generator deployment is used if no judge deployment is specified.

## 3. Score with five built-in RAG evaluators

```powershell
.\.venv-eval\Scripts\python.exe .\06_evaluation_trace_security\evaluate_foundry.py --limit 1
.\.venv-eval\Scripts\python.exe .\06_evaluation_trace_security\evaluate_foundry.py
```

| Evaluator | Question it answers |
|---|---|
| DocumentRetrievalEvaluator | Are relevant documents retrieved and ranked well? Reports fidelity, NDCG, XDCG, relevance and holes metrics. |
| RetrievalEvaluator | Is the retrieved text useful for this question? |
| GroundednessEvaluator | Does the answer stay within the evidence? |
| RelevanceEvaluator | Does the answer address the question? |
| ResponseCompletenessEvaluator (preview) | Does it cover the expected answer? |

All five evaluators run by default. JSONL results include raw scores and judge reasoning in `results/foundry_scores.jsonl`. Each run replaces that file; copy it before changing retrieval settings to compare experiments. Calls to the judge and service can incur charges. Results stay local; this script does not publish a Foundry portal run.

Document-level relevance labels are derived from the course's expected-source list: expected documents receive 4 and the other corpus documents receive 0. Repeated chunks are deduplicated in retrieval order. These are coarse classroom labels, not independently judged chunk relevance labels. Review labels before interpreting ranking scores. Document Retrieval is not applicable to the no-answer row. The CSV's brief expected answers also limit completeness scoring; expand them when teaching detailed answer evaluation. LLM scores can vary between runs.

## 4. Inspect and compare

Compare the manual-only, two-source and unsupported questions. Check groundedness separately from completeness: an answer can use only the evidence yet omit the recovery steps. Change retrieval settings, regenerate outputs, rerun evaluators and compare saved runs. Do not read citation presence as citation correctness.

## 5. Cleanup

Remove local `results` when finished; it contains retrieved document text. This lab creates no Search index or model deployment. Keep assigned resources. Delete your own student resource group only after all dependent labs are complete.

Sources: [Foundry RAG evaluator catalog](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/rag-evaluators), [Python SDK evaluation](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/evaluate-sdk).

For a GPT-5 or o-series judge, add `--reasoning-model` so the SDK uses reasoning-compatible token and temperature parameters.

The SDK default relevance/count thresholds target larger datasets. This lab sets relevance thresholds to 4 (the classroom label maximum), expects at least one retrieved document, and expects six labeled corpus documents. These are teaching thresholds; tune them for your workload. Token-limited deployments can return 429 while running four judge calls per question; use a one-row smoke test first.

If a judge returns no numeric score, the JSON output records null; inspect its reasoning and treat it as unscored, not passed. This can occur even when the SDK reports completed. Re-run affected samples with a suitable judge before comparing averages.
