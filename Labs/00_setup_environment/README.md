# Lab 00: Create the Azure environment

The PowerShell [setup script](setup.ps1) runs these steps in order:

1. Read the subscription selected during `az login` and create a resource group.
2. Create a Storage account and upload all files from `Knowledge Base` to a private Blob container.
3. Create an Azure AI Search service and an **empty** 3,072-dimension vector index called `rag-basic`.
4. Create a Microsoft Foundry resource and project.
5. Deploy `gpt-5-mini` for answers and `text-embedding-3-large` for embeddings.
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
