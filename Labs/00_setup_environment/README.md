# Lab 00: Create the Azure environment

The PowerShell [setup script](setup.ps1) runs these steps in order:

1. Read the subscription selected during `az login` and create a resource group.
2. Create a Storage account and upload all files from `Knowledge Base` to a private Blob container.
3. Create an Azure AI Search service and an **empty** 3,072-dimension vector index called `rag-basic`.
4. Create a Microsoft Foundry resource and project.
5. Deploy `gpt-4.1` for answers and `text-embedding-3-large` for embeddings.
6. Save the new endpoints and keys to `.env.generated` in this folder.

## Before you run it

You need PowerShell, Azure CLI 2.80 or later, an Azure subscription, resource creation permissions, and quota for both model deployments. The script uses `eastus` and requests capacity 10 for chat and 10 for embeddings. Chat uses the `GlobalStandard` SKU; embeddings use the regional `Standard` SKU. If you need different values, edit the three settings near the top of `setup.ps1` before running it. These resources can incur charges.

Sign in and select your subscription, then run the script from the `Labs` folder. For a shared classroom subscription, give each student a unique lowercase tag of 3 to 8 letters or digits (for example, `s01`). The script combines that tag with the first section of the subscription ID so each student gets separate resources. Without a tag, the original subscription-based names are used.

```powershell
az login
az account set --subscription "<your-subscription-id>"
.\00_setup_environment\setup.ps1 -StudentTag s01
```

WSL and Git Bash are not needed. If you already completed `az login`, run only the second command.

The script does not overwrite the lesson `.env` files. After it finishes, copy the shared connection values from `00_setup_environment/.env.generated` into the `.env` of each lesson you plan to run. Keep each lesson's own `AZURE_SEARCH_INDEX` value, except set Lab 01 to `rag-basic`. Keep its `AZURE_SEARCH_HIERARCHY_INDEX` value where present. Do not share `.env.generated`; it contains keys and is ignored by Git.

Blob upload stores the original files. It does **not** add searchable chunks to Azure AI Search. Create the Python environment from the [course README](../README.md), then run Lab 01's builder and app:

```powershell
.\.venv\Scripts\python .\01_basic_rag_diagnose\build_index.py
.\.venv\Scripts\python .\01_basic_rag_diagnose\rag_app.py
```

The Search index is created with the same field names as Lab 01's builder. Each later lesson still creates its own index with the schema needed for that concept.

## Assigned classroom groups

Use the participant-to-group mapping supplied by your instructor. Keep every lab resource inside your assigned group. Pass your unique assigned student tag and group explicitly:

```powershell
.\00_setup_environment\setup.ps1 -StudentTag u01 -ResourceGroupName "<your-assigned-resource-group>"
```

The script reads the existing group location unless you explicitly pass `-Location`. This classroom splits Basic Search services across East US and East US 2 to stay below the 16-services-per-region limit. Do not override your assigned region without checking quota.

The setup enables Search API-key and Entra authentication, gives Search and the Foundry project system-assigned identities, grants Cognitive Services User to the Search identity on Foundry, and grants Search Index Data Reader to the project identity on Search. Students need permission to assign these two service-identity roles; the classroom's constrained delegation provides that permission within the assigned group. Foundry User and Foundry Project Manager provide the student-side agent permissions. Allow new role assignments time to propagate before running Agentic RAG.

Classic RAG builders use a Search admin key. With Entra authentication, Search Index Data Contributor permits both loading and reading documents; Search Index Data Reader provides query-only access. Contributor covers management operations such as index creation and listing service keys. The classroom explicitly assigns both Search data roles for teaching clarity.

GPT-4.1 is the default chat/judge deployment and text-embedding-3-large supplies 3,072-dimensional embeddings. GPT-5.2 is also permitted by classroom policy; provisioned deployments and capacities above 10 are blocked. Use separate environments for classic RAG, Foundry agents and Foundry evaluators. The five-evaluator lab uses no Groundedness Pro service.
