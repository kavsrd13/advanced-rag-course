# Sunny Cafe: three simple RAG patterns

One Gradio app and **8 short text files**. The cafe sells mango milkshake,
lemonade and coffee. It also has simple rules for delivery, takeaway, refunds
and opening hours. Read the entire dataset in the app before asking questions.

## 1. Get the code

Install Git and Python 3.11, then open Windows PowerShell:

```powershell
git clone https://github.com/kavsrd13/advanced-rag-course.git
Set-Location .\advanced-rag-course\Labs\retrieval_comparison_demo
```

If you already have the repository, save your work, run `git pull --ff-only`,
and open `Labs\retrieval_comparison_demo`. Run the remaining commands here.

## 2. Install packages

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\.venv\Scripts\python.exe -m pip check
$env:PYTHONIOENCODING = 'utf-8'
```

Alternatively use the existing classic course environment at
`..\.venv\Scripts\python.exe` instead of this folder's environment.

## 3. Configure your existing Azure resources

Use a Search service with semantic ranker enabled and your existing embedding
and chat deployments. For new resources, complete the course Azure setup first.

```powershell
Copy-Item .\.env.example .\.env
notepad .\.env
```

Fill in your own endpoints, resource keys and deployed model names. Use the
Azure OpenAI endpoint, not the Foundry project endpoint. Give the index a unique
name such as `rag-compare-cafe-u02`. Keep the `rag-compare-` prefix. Never share
`.env`; it is ignored by Git. The builder detects the embedding dimensions.

**Updating the old IT demo?** Change `DEMO_SEARCH_INDEX` to a new cafe index name
and rebuild. Restart Gradio after editing `.env`. Otherwise old indexed IT
passages could still be returned. Use the same embedding deployment at build
and query time. Do not reuse another course index such as `rag-basic`.

For corporate certificate errors, use an IT-approved CA bundle and the course's
certificate troubleshooting guide. Do not disable certificate verification.

## 4. Build once and open Gradio

```powershell
.\.venv\Scripts\python.exe .\app.py --build-index
.\.venv\Scripts\python.exe .\app.py
```

The builder creates a new index with 8 documents. It deliberately fails if the
index exists, rather than overwriting another schema. For a rebuild, choose a
new demo index name or delete only your own demo index in Azure Portal first.
Wait a few moments after uploading for records to become searchable.

Open the local URL printed by Gradio. Stop the app with Ctrl+C.

## 5. Teach with three questions

Set the passage count to **1** and turn **Generate an answer** off first.

| Question | What to explain |
|---|---|
| What is the price of Mango Milkshake? | Keyword search matches the menu words directly. All three may succeed. |
| Can you bring my order to my house? | The delivery note says purchases/address. Vector search can connect these meanings. |
| My mango milkshake has gone sour. Can I get a refund after opening it? | The spoiled-drink exception must be distinguished from the general refund rule and the menu item. |

Switch methods and click **Run selected method**, or choose **Compare all three**.
Read the selected note and rank before turning answers on. Hybrid mode shows
both the fusion rank before reranking and the final rank. The same question,
passage count, chat model and answer prompt are used across modes.

More prompts and the teacher walkthrough are in [prompts.txt](prompts.txt).
Actual live observations are in [OBSERVED_RESULTS.md](OBSERVED_RESULTS.md).
Rankings can change; the app does not force a winner. The Wi-Fi question has no
answer in the notes and should produce an abstention.

## 6. Understand the single code file

- `read_documents()`: first line is the title; the remaining text is one passage.
- `build_index()`: embeds the 8 notes and uploads them to a dedicated Search index.
- `retrieve()`: Keyword uses BM25; Vector uses only an embedding query; Hybrid
  combines both with Azure RRF, then applies the semantic ranker.
- `generate()`: gives only selected notes to the chat model and requests citations.
- `run_mode()` and `compare_all()`: connect the retrieval choices to Gradio.

Vector mode uses exhaustive search for this tiny dataset. Hybrid makes an extra
request to show ranking before reranking. It reports an error if semantic
reranking is unavailable instead of silently showing ordinary hybrid results.
Raw BM25, vector, RRF and reranker scores have different scales. Compare the
passages and their order, not raw score magnitudes. Search time excludes
embeddings and generation; hybrid includes its extra teaching request.

## 7. Cleanup

Stop Gradio. In Azure Portal, delete only the Search index named by this demo's
`DEMO_SEARCH_INDEX`. Keep other course indexes, services and model deployments.
Model calls, embeddings and semantic ranking may incur charges. The app does
not implement production sign-in or document permissions.

References: [hybrid ranking](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking),
[vector quickstart](https://learn.microsoft.com/en-us/azure/search/search-get-started-vector).
