"""Run Azure-connected lessons offline with mocked services and real course files."""

import ast
import contextlib
import importlib.util
import io
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from dotenv import dotenv_values
from pyoxigraph import Store


ROOT = Path(__file__).resolve().parent


def load_module(path):
    spec = importlib.util.spec_from_file_location(path.parent.name + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def completion(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=[]))]
    )


def main():
    folders = sorted(ROOT.glob("[0-9]*"))
    # The local semantic lesson writes JSON instead of an Azure Search index.
    builders = [
        path for path in ROOT.glob("*/build_index.py")
        if not path.parent.name.startswith(("01.1", "05_agentic"))
    ]
    assert len(builders) == 7
    names = []
    for path in builders:
        names.append(dotenv_values(path.with_name(".env"))["AZURE_SEARCH_INDEX"])
    # The reranker lesson deliberately reuses Lab 02's index.
    assert len(names) - len(set(names)) == 1
    evaluation_env = dotenv_values(ROOT / "06_evaluation_trace_security/.env")
    hybrid_env = dotenv_values(ROOT / "02_hybrid_semantic_metadata/.env")
    assert evaluation_env["AZURE_SEARCH_INDEX"] == hybrid_env["AZURE_SEARCH_INDEX"]

    # Prevent every SDK request from reaching a real endpoint.
    with (
        patch("openai.AzureOpenAI") as openai_factory,
        patch("azure.search.documents.SearchClient") as search_factory,
        patch("azure.search.documents.indexes.SearchIndexClient") as index_factory,
        contextlib.redirect_stdout(io.StringIO()),
    ):
        llm = openai_factory.return_value
        llm.embeddings.create.side_effect = lambda **kwargs: SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.0] * 3072) for _ in kwargs["input"]]
        )
        llm.chat.completions.create.return_value = completion("Document summary.")

        # Execute ingestion with the actual PDFs, metadata, and Word tables.
        for path in builders:
            module = load_module(path)
            index_factory.return_value.reset_mock()
            search_factory.return_value.reset_mock()
            module.main()
            uploaded = [
                document
                for call in search_factory.return_value.upload_documents.call_args_list
                for document in call.args[0]
            ]
            assert uploaded
            assert all(len(item["contentVector"]) == 3072 for item in uploaded)
            indexes = index_factory.return_value.create_or_update_index.call_args_list
            schema = {field.name for field in indexes[0].args[0].fields}
            assert set(uploaded[0]) <= schema
            assert module.chunk_text("abcdefghij", 6, 2) == ["abcdef", "efghij"]
            if path.parent.name.startswith("01_basic"):
                assert {"classification", "allowedUsers"} <= schema
                assert all(document["allowedUsers"] for document in uploaded)
                alice_documents = {
                    document["policyId"]
                    for document in uploaded
                    if "alice" in document["allowedUsers"] or "all" in document["allowedUsers"]
                }
                assert alice_documents == {"SEC-114", "HR-REM-220", "MAN-X200", "AI-GOV-310"}
            if path.parent.name.startswith("03c"):
                graph = Store.read_only(str(module.GRAPH_DB))
                graph_facts = list(graph.query(
                    "SELECT ?source WHERE { GRAPH ?source { ?a ?relation ?b } }"
                ))
                assert len(graph_facts) == 6
                del graph
            if path.parent.name.startswith("08"):
                assert len(indexes) == 2
                assert any(item["level"] == "summary" for item in uploaded)
            else:
                assert len(indexes) == 1
                if path.parent.name.startswith("03b"):
                    assert any(item["level"] == "summary" for item in uploaded)

        # Execute each app using evidence returned by mocked Search.
        evidence = {
            "id": "sample", "policyId": "MAN-X200", "title": "Manual",
            "content": "Install firmware 3.2.1.", "source": "manual.pdf",
            "documentId": "manual", "level": "summary", "classification": "Public",
        }
        apps = [
            path for path in sorted(ROOT.glob("*/rag_app.py"))
            if not path.parent.name.startswith(("01.1", "05_agentic"))
        ]
        for path in apps:
            module = load_module(path)
            search_factory.return_value.reset_mock()
            search_factory.return_value.search.side_effect = None
            search_factory.return_value.search.return_value = [evidence]
            llm.chat.completions.create.side_effect = None
            llm.chat.completions.create.return_value = completion('{"ids": ["sample"]}')
            if path.parent.name.startswith("03b"):
                def hierarchy_results(**kwargs):
                    selected = kwargs["filter"]
                    if selected == "level eq 'summary'":
                        return [
                            {**evidence, "documentId": "ops", "policyId": "OPS-Q2-2026", "content": "Routing summary for operations."},
                            {**evidence, "documentId": "manual", "policyId": "MAN-X200", "content": "Routing summary for manual."},
                        ]
                    if "documentId eq 'ops'" in selected:
                        return [{**evidence, "documentId": "ops", "level": "leaf", "policyId": "OPS-Q2-2026", "content": "Incidents fell from 30 to 10."}]
                    return [{**evidence, "documentId": "manual", "level": "leaf", "content": "Reset Print Service and install 3.2.1."}]

                search_factory.return_value.search.side_effect = hierarchy_results
            if path.parent.name.startswith("03a"):
                first = completion("")
                first.choices[0].message.tool_calls = [SimpleNamespace(
                    id="search-1",
                    function=SimpleNamespace(
                        name="search_documents", arguments='{"query": "Q2 incident trend"}'
                    ),
                )]
                second = completion("")
                second.choices[0].message.tool_calls = [SimpleNamespace(
                    id="search-2",
                    function=SimpleNamespace(
                        name="search_documents", arguments='{"query": "E-4012 recovery"}'
                    ),
                )]
                llm.chat.completions.create.side_effect = [
                    first, second, completion("Answer [MAN-X200].")
                ]
            if path.parent.name.startswith("04"):
                llm.chat.completions.create.side_effect = [
                    completion("complex"), completion("insufficient"),
                    completion("rewritten query"), completion("Answer [MAN-X200]."),
                ]
            if path.parent.name.startswith("05"):
                tool_call = SimpleNamespace(
                    id="call-1",
                    function=SimpleNamespace(
                        name="downtime_cost", arguments='{"impacted_devices": 100}'
                    ),
                )
                tool_response = completion("")
                tool_response.choices[0].message.tool_calls = [tool_call]
                llm.chat.completions.create.side_effect = [
                    tool_response, completion("Estimated 3.2 hours [MAN-X200].")
                ]
            module.main()
            if path.parent.name.startswith("01_basic"):
                keyword_query = search_factory.return_value.search.call_args
                assert keyword_query.kwargs["search_text"] == "What does SEC-114 require for laptops?"
                assert "alice" in keyword_query.kwargs["filter"]
                assert "all" in keyword_query.kwargs["filter"]
                assert "vector_queries" not in keyword_query.kwargs
            if path.parent.name.startswith("03a"):
                searches = search_factory.return_value.search.call_args_list
                assert [call.kwargs["search_text"] for call in searches] == [
                    "Q2 incident trend", "E-4012 recovery"
                ]
                messages = llm.chat.completions.create.call_args.kwargs["messages"]
                assert sum(message["role"] == "tool" for message in messages if isinstance(message, dict)) == 2
            if path.parent.name.startswith("03b"):
                filters = [call.kwargs["filter"] for call in search_factory.return_value.search.call_args_list]
                assert filters == [
                    "level eq 'summary'",
                    "documentId eq 'ops' and level eq 'leaf'",
                    "documentId eq 'manual' and level eq 'leaf'",
                ]
                final_prompt = llm.chat.completions.create.call_args.kwargs["messages"][-1]["content"]
                assert "Incidents fell from 30 to 10" in final_prompt
                assert "Reset Print Service" in final_prompt
                assert "Routing summary" not in final_prompt
            if path.parent.name.startswith("03c"):
                graph_filter = search_factory.return_value.search.call_args.kwargs["filter"]
                assert "OPS-Q2-2026" in graph_filter
                assert "MAN-X200" in graph_filter
                with patch("sys.argv", ["rag_app.py", "What affected X200?"]):
                    module.main()
                assert search_factory.return_value.search.call_args.kwargs["filter"] == (
                    "policyId eq 'OPS-Q2-2026'"
                )
            if path.parent.name.startswith("04"):
                searches = search_factory.return_value.search.call_args_list
                assert len(searches) == 2
                assert searches[-1].kwargs["search_text"] == "rewritten query"
            if path.parent.name.startswith("05"):
                messages = llm.chat.completions.create.call_args.kwargs["messages"]
                assert messages[-1]["role"] == "tool"
                assert "3.2 hours" in messages[-1]["content"]
        llm.chat.completions.create.side_effect = None
        llm.chat.completions.create.return_value = completion("Answer [MAN-X200].")
        visual = load_module(ROOT / "01_basic_rag_diagnose/gradio_rag_app.py")
        search_factory.return_value.reset_mock()
        search_factory.return_value.search.return_value = [evidence]
        answer_text, sources_text, filter_text = visual.run_rag(
            "How is E-4012 resolved?", "alice"
        )
        assert "Answer [MAN-X200]." in answer_text
        assert "MAN-X200" in sources_text
        assert "alice" in filter_text
        assert search_factory.return_value.search.call_args.kwargs["search_text"]

        search_factory.return_value.search.return_value = []
        no_access_answer, no_access_sources, _ = visual.run_rag(
            "Reveal MNA-26-03", "alice"
        )
        assert "No authorized document" in no_access_answer
        assert "None" in no_access_sources

        load_module(ROOT / "06_evaluation_trace_security/evaluate.py").main()
        router = load_module(ROOT / "07_architecture_selection_workshop/choose_architecture.py")
        assert router.choose_rag_pattern("multiple sources") == "multihop_rag"
        router.main()

    # Compile all scripts and ensure they never import another lesson.
    for folder in folders:
        for path in folder.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
            tree = ast.parse(source)
            assert not any(
                isinstance(node, ast.ImportFrom)
                and node.module in {"rag_engine", "rag_patterns", "build_index"}
                for node in ast.walk(tree)
            )
    print(f"Passed: {len(builders)} Azure index builders, {len(apps)} Azure RAG apps, evaluation, and architecture selection.")
    print("Real source files were read; all Azure services were mocked.")


if __name__ == "__main__":
    main()
