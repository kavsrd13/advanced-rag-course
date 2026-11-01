# Lab 05: Foundry agent + Foundry IQ

Scenario: an X200 support analyst asks why E-4012 happened, whether incidents improved, and which firmware fixes it. The operations report explains the incident; the manual contains the recovery. The agent must consult the knowledge base, whose retrieval instructions choose the relevant sources and plan queries.

Execution order:

1. `build_index.py` reads two course PDFs and uploads small page chunks to two Azure AI Search indexes.
2. It creates two indexed knowledge sources, then a Foundry IQ knowledge base with **low** retrieval reasoning effort and explicit `retrievalInstructions`.
3. It creates a Foundry project RemoteTool connection to the knowledge base MCP endpoint, then a prompt agent with the `knowledge_base_retrieve` tool.
4. `inspect_retrieval.py` shows which sources and queries Foundry IQ selected.
5. `rag_app.py` asks the agent one question with `tool_choice="required"`. Inspect the tool status and cited answer.

The two instruction layers are distinct: knowledge base instructions route the information search; agent instructions require use of the tool and evidence-based citations. Low effort performs one LLM query-planning pass. Medium effort can add a follow-up retrieval pass at greater cost and latency.

Use a dedicated virtual environment because the current Foundry SDK requires OpenAI 3.x, while older labs pin OpenAI 1.x:

```powershell
python -m venv .venv-foundry
.\.venv-foundry\Scripts\python -m pip install -r .\05_agentic_rag_with_tools\requirements.txt
.\.venv-foundry\Scripts\python .\05_agentic_rag_with_tools\build_index.py
.\.venv-foundry\Scripts\python .\05_agentic_rag_with_tools\inspect_retrieval.py
.\.venv-foundry\Scripts\python .\05_agentic_rag_with_tools\rag_app.py
```

Configure `.env` with the existing Search admin key and endpoints, Foundry project endpoint, model deployment and `FOUNDRY_PROJECT_RESOURCE_ID`. Sign in with `az login` to the subscription that owns the project. The Search service needs a managed identity with Cognitive Services User on Foundry; the project identity needs Search Index Data Reader on Search. The instructor needs Foundry User and Foundry Project Manager. These identities and roles are required for keyless model planning and MCP access.

Try these questions:

- What caused X200 error E-4012, how did incidents change, and which firmware fixes it?
- Which firmware fixes E-4012 according to the X200 manual?
- What did the Q2 operations review report about X200 incidents?

Inspect the Search service's knowledge sources and knowledge base, then the Foundry agent's MCP tool. Change `retrievalInstructions` in `build_index.py`, rerun it, and compare source selection. These synthetic course documents are for demonstration; this lab does not implement user-specific document authorization.

Observed routing in the live demo: the combined cause-and-fix question queried both sources; a question asking only for the manual's exact recovery steps queried only `rag-05-manual-source`. The agent called `knowledge_base_retrieve` and cited both `OPS-Q2-2026` and `MAN-X200` for the combined question.

References: [Microsoft's end-to-end tutorial](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-create-pipeline), [knowledge base instructions](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-create-knowledge-base), [retrieval reasoning effort](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-set-retrieval-reasoning-effort).
