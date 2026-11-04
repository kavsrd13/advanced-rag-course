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

GPT-4.1 is the default chat/judge deployment and text-embedding-3-large supplies 3,072-dimensional embeddings. The script requests capacity 10 for each deployment. The instructor removed the classroom model, SKU and capacity deny policies; Azure quota and regional availability still apply. Use separate environments for classic RAG, Foundry agents and Foundry evaluators. The five-evaluator lab uses no Groundedness Pro service.

## Certificate errors on corporate networks

The Search index request uses native PowerShell `Invoke-RestMethod`, which uses Windows certificate trust. This supports a corporate HTTPS inspection certificate already installed by IT in the Windows trusted certificate store. HTTPS certificate verification remains enabled.

If the previous script failed at `/indexes/rag-basic` with `CERTIFICATE_VERIFY_FAILED`, download the updated `setup.ps1` and rerun it with **the same student tag, group and region**. The script reuses the same resource names. If an existing `rag-basic` index already contains lab data, use the CA-bundle configuration below and resume your lab rather than reprovisioning its schema.

If native PowerShell also reports an untrusted certificate, ask IT to install the approved corporate root CA and its certificate chain. The affected student workstation must trust that issuer; changing Azure IAM cannot repair local certificate trust.

If another Azure CLI command or a later Python lab has the same certificate error, obtain an approved **PEM CA bundle containing the normal public roots plus the corporate CA chain** from IT, then set these in the same PowerShell window before rerunning:

```powershell
$env:REQUESTS_CA_BUNDLE = 'C:\Certificates\approved-ca-bundle.pem'
$env:SSL_CERT_FILE = $env:REQUESTS_CA_BUNDLE
```

The example path must point to the actual IT-provided bundle. `REQUESTS_CA_BUNDLE` covers Azure CLI and Requests-based SDK clients; `SSL_CERT_FILE` covers clients such as HTTPX/OpenAI that honor that setting. Set them again in each new terminal. Do not disable certificate verification or use `--skip-certificate-check`.

See [Microsoft's Azure CLI proxy guidance](https://learn.microsoft.com/en-us/cli/azure/use-azure-cli-successfully-troubleshooting#work-behind-a-proxy).
