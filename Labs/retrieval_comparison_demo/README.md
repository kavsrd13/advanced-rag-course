# One app: keyword, vector, and hybrid RAG with reranking

A fictional Northstar IT support desk has 12 small text files. Some use exact
error codes, some express the same idea in different words, and some contain
similar policies with different conditions. The app compares real retrieval
results, then uses the same chat model and grounding prompt to answer.

## 1. Get the code and open this folder

Install Git, Python 3.11 and Azure CLI. Open Windows PowerShell:

```powershell
git clone https://github.com/kavsrd13/advanced-rag-course.git
Set-Location .\advanced-rag-course\Labs\retrieval_comparison_demo
```

If the instructor supplied this folder directly, open PowerShell in that folder.
If the repository already exists, save local edits before updating it with
`git pull --ff-only`, then open `Labs\retrieval_comparison_demo`.

## 2. Create a Python environment

Run all commands below from **retrieval_comparison_demo**, not the parent Labs folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe -m pip check
$env:PYTHONIOENCODING = 'utf-8'
```

You can also use the course's existing classic RAG environment by invoking its
Python at `..\.venv\Scripts\python.exe` instead of the local environment.

## 3. Configure existing Azure resources

Use an Azure AI Search service with **semantic ranker enabled** and room for one
additional index, plus a chat deployment and an embedding deployment. The
instructor's course setup supplies these resources. If you need to create them,
follow `../00_setup_environment/lab_00_exercise.html` first; this app creates no
Search service, Storage account or Foundry resource.

```powershell
Copy-Item .\.env.example .\.env
notepad .\.env
```

Paste your actual endpoints, keys and deployment names. Change
`DEMO_SEARCH_INDEX=rag-compare-yourtag` to a unique name such as
`rag-compare-u02`. The app deliberately requires the `rag-compare-` prefix and
creates a **new index** instead of modifying an existing lesson index. Do not
point it at `rag-basic`. `.env` is private and ignored by Git.

Use the Azure OpenAI endpoint ending in `.openai.azure.com`, not the Foundry
project endpoint. `text-embedding-3-large` works; the builder detects the vector
dimensions returned by your embedding deployment. Keep that deployment unchanged
between indexing and querying.

For a private instructor checkout, configuration can be copied from a working
course `.env`, but use only your assigned credentials and add `DEMO_SEARCH_INDEX`.
No student should receive another person's key file.

If you see SSL certificate errors, use the IT-approved CA bundle and the
certificate guidance in the course setup exercise. Do not disable verification.
If Azure requires authentication for resource management, run `az login` and
complete MFA; the app itself uses the configured resource keys.

## 4. Build the dedicated demo index

```powershell
.\.venv\Scripts\python.exe .\app.py --build-index
```

Expected: 12 documents and the detected embedding dimension. Each text file is
already a short passage, so there is no additional chunking algorithm to distract
from retrieval. The first line becomes the title; the rest is the content.

The command fails if that index already exists. To rebuild, choose a fresh unique
`DEMO_SEARCH_INDEX` or delete only this demo index in Azure Portal first. It never
deletes an existing index automatically. Allow a few moments after upload for the
new records to become searchable.

## 5. Launch Gradio

```powershell
.\.venv\Scripts\python.exe .\app.py
```

Open the local URL printed by Gradio. Keep the terminal running and use Ctrl+C
to stop. The app does not create a public sharing link.

1. Leave the paraphrased offboarding question in the textbox.
2. Turn off **Generate an answer** and set the evidence count to **1**.
3. Run Keyword, then Vector. Inspect the different documents, not just the scores.
4. Open **Compare all three** and click its button for a side-by-side view.
5. Try the printer and contractor questions from `prompts.txt`.
6. Turn generation on and inspect citations and selected source text.
7. Increase the evidence count and observe how the answer changes.

The selector does not run automatically: click Run after switching it. Compare
all three can make three paid answer calls. Disable generation to teach retrieval
first; embedding and semantic Search calls can still incur charges.

## 6. Understand the information flow in app.py

| Mode | Retrieval flow |
|---|---|
| Keyword | Text query → Azure BM25 → top passages → grounded answer |
| Vector | Question embedding → vector-only query → top passages → grounded answer |
| Hybrid + rerank | Text + vector → Azure RRF fusion → semantic reranker → top passages → grounded answer |

`build_index()` loads the text files, embeds title + content, defines the Search
schema and uploads records. `retrieve()` changes only retrieval according to the
mode. The candidate limit is 50; the small dataset contains only 12 documents.
Vector mode uses exhaustive search for this small teaching corpus. Hybrid makes
an extra request to expose the fusion ranking before reranking. It fails visibly
if semantic reranking is unavailable, rather than presenting plain hybrid as
reranked results.

`run_mode()` takes the first N ranked passages and passes them to `generate()`.
The same chat deployment, question and system prompt are used for every mode.
`compare_all()` calls the same function for all three methods. Gradio only wires
these functions to the controls; it does not choose or fabricate evidence.

The ranking table shows every returned candidate and which ones reached the
answer model. Hybrid mode also shows its rank before reranking. BM25 scores,
Azure vector scores, RRF scores and semantic reranker scores have different
scales. The Azure vector score is not raw cosine similarity. Compare source
relevance and order, not score magnitudes across methods. Search time excludes
query embeddings and generation; hybrid includes the extra teaching request,
so this display is not an end-to-end latency benchmark.

## 7. Prompts and expected differences

Read `prompts.txt` for seven questions, expected source IDs, and what to inspect.
The offboarding paraphrase is designed to expose a vocabulary mismatch; the exact
codes show lexical matching; the contractor and recovery questions need precise
conditions. Rankings are not guaranteed, and all three may answer an easy query
correctly. The unsupported parental-leave question should produce abstention.

These are real service results, not a scripted demonstration that forces hybrid
to win. This app does not implement document authorization or production sign-in.
See [OBSERVED_RESULTS.md](OBSERVED_RESULTS.md) for the actual source rankings
recorded during the instructor's live run.

## 8. Cleanup

Stop Gradio. In Azure Portal → your Search service → Indexes, delete only the
index matching `DEMO_SEARCH_INDEX` in this folder's `.env`. Keep the Search
service, other indexes and shared model deployments. Remove the local `.env`
and virtual environment when no longer needed. No resource group deletion is
required for this demo.

References: [hybrid ranking](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking),
[hybrid queries](https://learn.microsoft.com/en-us/azure/search/hybrid-search-how-to-query),
[vector quickstart](https://learn.microsoft.com/en-us/azure/search/search-get-started-vector).
