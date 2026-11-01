"""Build two indexed knowledge sources, a Foundry IQ base, and a prompt agent."""
import os
import sys
from pathlib import Path

import requests
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from azure.core.credentials import AzureKeyCredential
from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchableField, SimpleField, SearchFieldDataType,
    SemanticConfiguration, SemanticField, SemanticPrioritizedFields, SemanticSearch,
)
from dotenv import load_dotenv
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env", override=True)
SEARCH = os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/")
PROJECT = os.environ["AIPROJECT_ENDPOINT"]
PROJECT_ID = os.environ["FOUNDRY_PROJECT_RESOURCE_ID"]
MODEL = os.environ["AZURE_OPENAI_DEPLOYMENT"]
KEY = os.environ["AZURE_SEARCH_API_KEY"]
VERSION = "2026-08-01-preview"
KB = "rag-05-incident-kb"
AGENT = "rag-05-incident-agent"
CONNECTION = "rag-05-iq-connection"
SOURCES = [
    ("OPS-Q2-2026", "04_Q2_Operations_and_Incident_Review", "rag-05-operations", "rag-05-operations-source",
     "Operations review: incident cause, symptoms, impact, and trend."),
    ("MAN-X200", "03_X200_Service_Manual_and_Troubleshooting", "rag-05-manual", "rag-05-manual-source",
     "X200 manual: E-4012 recovery steps and firmware fix."),
]


def put_search(path, body):
    response = requests.put(
        f"{SEARCH}/{path}?api-version={VERSION}",
        headers={"api-key": KEY}, json=body, timeout=60,
    )
    response.raise_for_status()


def main():
    index_client = SearchIndexClient(SEARCH, AzureKeyCredential(KEY))
    for policy_id, filename, index_name, source_name, description in SOURCES:
        index_client.create_or_update_index(SearchIndex(
            name=index_name, description=description,
            fields=[
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SearchableField(name="policyId", type=SearchFieldDataType.String),
                SearchableField(name="title", type=SearchFieldDataType.String),
                SearchableField(name="content", type=SearchFieldDataType.String),
                SimpleField(name="page", type=SearchFieldDataType.Int32),
            ],
            semantic_search=SemanticSearch(configurations=[SemanticConfiguration(
                name="rag-semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="content")],
                ),
            )]),
        ))
        pages = PdfReader(HERE.parent / "Knowledge Base" / "PDF_Files" / f"{filename}.pdf").pages
        chunks = [
            {"id": f"{policy_id}-{page_no}-{start}", "policyId": policy_id,
             "title": policy_id, "content": text[start:start + 1300], "page": page_no}
            for page_no, page in enumerate(pages, 1)
            for text in [page.extract_text() or ""]
            for start in range(0, len(text), 1100)
        ]
        SearchClient(SEARCH, index_name, AzureKeyCredential(KEY)).upload_documents(chunks)
        put_search(f"knowledgesources/{source_name}", {
            "name": source_name, "kind": "searchIndex", "description": description,
            "searchIndexParameters": {
                "searchIndexName": index_name,
                "semanticConfigurationName": "rag-semantic-config",
                "sourceDataFields": [{"name": name} for name in ("id", "policyId", "page")],
            },
        })
        print("SOURCE:", source_name, "| CHUNKS:", len(chunks))

    put_search(f"knowledgebases/{KB}", {
        "name": KB,
        "knowledgeSources": [{"name": name} for _, _, _, name, _ in SOURCES],
        "models": [{"kind": "azureOpenAI", "azureOpenAIParameters": {
            "resourceUri": os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/"),
            "deploymentId": MODEL, "modelName": MODEL,
        }}],
        "outputMode": "extractiveData",
        "retrievalReasoningEffort": {"kind": "low"},
        "retrievalInstructions": (
            "Use operations for E-4012 cause, symptoms and incident trends. "
            "Use the X200 manual for recovery and firmware fixes. "
            "For questions combining cause and fix, search both sources. "
            "Preserve policy IDs and pages in citations."
        ),
    })
    mcp_url = f"{SEARCH}/knowledgebases/{KB}/mcp?api-version={VERSION}"
    print("KNOWLEDGE BASE:", KB)

    create_agent()


def create_agent():
    mcp_url = f"{SEARCH}/knowledgebases/{KB}/mcp?api-version={VERSION}"
    credential = AzureCliCredential()
    token = credential.get_token("https://management.azure.com/.default").token
    response = requests.put(
        f"https://management.azure.com{PROJECT_ID}/connections/{CONNECTION}?api-version=2025-10-01-preview",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": CONNECTION, "type": "Microsoft.MachineLearningServices/workspaces/connections",
              "properties": {"authType": "ProjectManagedIdentity", "category": "RemoteTool",
                             "target": mcp_url, "isSharedToAll": True,
                             "audience": "https://search.azure.com/", "metadata": {"ApiType": "Azure"}}},
        timeout=60,
    )
    response.raise_for_status()
    print("PROJECT CONNECTION:", CONNECTION)
    agent = AIProjectClient(endpoint=PROJECT, credential=credential).agents.create_version(
        agent_name=AGENT,
        definition=PromptAgentDefinition(
            model=MODEL,
            instructions=(
                "You are an X200 incident support agent. Call knowledge_base_retrieve "
                "for every question. For cause and fix questions, ask it to search "
                "both operations and manual. Answer only from retrieved evidence, "
                "include its source citations, and say when evidence is missing."
            ),
            tools=[MCPTool(server_label="incident-knowledge", server_url=mcp_url,
                           require_approval="never", allowed_tools=["knowledge_base_retrieve"],
                           project_connection_id=CONNECTION)],
        ),
    )
    print("AGENT:", agent.name, "| VERSION:", agent.version)


if __name__ == "__main__":
    create_agent() if "--agent-only" in sys.argv else main()
