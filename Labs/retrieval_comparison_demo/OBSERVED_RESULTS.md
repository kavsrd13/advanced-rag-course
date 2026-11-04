# Observed classroom results

Live retrieval check on 4 November 2026 using text-embedding-3-large (3,072 dimensions) and Azure AI Search semantic ranker. Each mode used the same index and question. These are observations from one run, not guaranteed future rankings.

| Question | Keyword rank 1 | Vector rank 1 | Hybrid + rerank rank 1 | Reranked winner’s prior fusion rank |
|---|---|---|---|---|
| Exact code NS-7428 | 03-scanner-recovery | 01-printer-recovery | 03-scanner-recovery | 2 |
| Offboarding paraphrase | 11-external-sharing | 05-offboarding | 05-offboarding | 6 |
| Code plus held-job requirement | 01-printer-recovery | 01-printer-recovery | 01-printer-recovery | 1 |
| Contractor / Restricted / personal laptop | 07-employee-byod | 08-contractor-restricted | 08-contractor-restricted | 2 |
| Misplaced notebook | 10-device-encryption | 10-device-encryption | 10-device-encryption | 1 |
| Unsupported parental-leave question | 09-remote-access | 09-remote-access | 12-visitor-wifi | 2 |

The first four questions illustrate different lessons:

1. Exact code: keyword retrieval found the scanner procedure; vector-only retrieval favored the nearby printer fault.
2. Paraphrase: keyword retrieval favored external sharing; vector search found offboarding. Hybrid reranking promoted offboarding from fusion rank 6 to rank 1.
3. Detailed printer question: all methods found the same correct recovery passage. A good query can make every method succeed.
4. Conditional policy: keyword retrieval preferred employee BYOD; vector and hybrid reranking preferred the contractor policy. Reranking moved the contractor policy from fusion rank 2 to rank 1.

The parental-leave question has no supporting document. The table still shows returned nearest/matching passages: these are not valid answers. Retrieval rank alone cannot establish answerability.

Validation completed: 12 real text records indexed, six questions across three retrieval methods, and a Gradio HTTP callback with four outputs. Raw ranking snapshots and private connection settings are excluded from Git. See prompts.txt for the teaching sequence.

Answer-generation check with one selected passage and the same gpt-5-mini deployment:

- Offboarding question, Keyword: abstained because the sharing passage did not answer it.
- Offboarding question, Vector: returned the offboarding checklist with a [05-offboarding] citation.
- Offboarding question, Hybrid + rerank: returned the offboarding checklist with a [05-offboarding] citation.
- Unsupported parental-leave question, Hybrid + rerank: abstained.

The README example uses GPT-4.1; replace deployment names with the models actually available on your resource. Answer wording can vary. The live checks above do not establish production accuracy or guarantee the same ranking on every model/service revision.
