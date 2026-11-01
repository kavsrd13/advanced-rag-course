import json


def choose_rag_pattern(workload):
    """Select the simplest pattern that satisfies the workload."""
    text = workload.lower()

    if "relationship" in text or "entity" in text or "graph" in text:
        return "graph_rag"
    if "multi-hop" in text or "multiple sources" in text:
        return "multihop_rag"
    if "metadata" in text or "filter" in text or "permission" in text:
        return "hybrid_rag_with_filters"
    return "basic_rag"


def main():
    workloads = [
        "Simple policy question",
        "Need exact codes and metadata filters",
        "Need multi-hop answers across multiple sources",
        "Need relationships between incidents and firmware",
    ]

    decisions = [
        {"workload": workload, "recommended_pattern": choose_rag_pattern(workload)}
        for workload in workloads
    ]
    print(json.dumps(decisions, indent=2))


if __name__ == "__main__":
    main()
