"""Ask the Foundry agent, which calls Foundry IQ's retrieval tool."""
import os
import sys
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    question = " ".join(sys.argv[1:]) or (
        "What caused X200 error E-4012, how did incidents change, "
        "and which firmware fixes it?"
    )
    project = AIProjectClient(
        endpoint=os.environ["AIPROJECT_ENDPOINT"], credential=AzureCliCredential()
    )
    client = project.get_openai_client(agent_name="rag-05-incident-agent")
    response = client.responses.create(input=question, tool_choice="required")
    print("QUESTION:", question)
    for item in response.output:
        if item.type == "mcp_call":
            print("KNOWLEDGE TOOL:", item.name, "| STATUS:", item.status)
    print("\nANSWER\n", response.output_text)


if __name__ == "__main__":
    main()
