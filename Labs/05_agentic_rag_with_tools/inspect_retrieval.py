"""Show which knowledge sources Foundry IQ selected for a question."""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=True)
question = " ".join(sys.argv[1:]) or "What caused E-4012 and how do I fix it?"
search = os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/")
response = requests.post(
    f"{search}/knowledgebases/rag-05-incident-kb/retrieve?api-version=2026-08-01-preview",
    headers={"api-key": os.environ["AZURE_SEARCH_API_KEY"]},
    json={"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
          "includeActivity": True},
    timeout=120,
)
response.raise_for_status()
result = response.json()
print("QUESTION:", question)
for step in result["activity"]:
    if step["type"] == "searchIndex":
        print("SOURCE:", step["knowledgeSourceName"],
              "| QUERY:", step["searchIndexArguments"]["search"])
documents = json.loads(result["response"][0]["content"][0]["text"])
print("EVIDENCE:", ", ".join(dict.fromkeys(item["title"] for item in documents)))
