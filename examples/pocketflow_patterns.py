"""
Examples demonstrating PocketFlow pattern alignment improvements.

This module shows how the new chaining and branching syntax follows
PocketFlow documentation patterns.
"""

from typing import Any

from utils.node import Flow, Node


class ExampleQueryNode(Node):
    """Example node that queries data."""

    def __init__(self):
        super().__init__()

    def prep(self, shared: dict[str, Any]) -> str:
        return shared.get("query", "")

    def exec(self, prep_result: str) -> dict[str, Any]:
        # Simulate query execution
        return {"results": [f"result_{i}" for i in range(3)], "query": prep_result}

    def post(
        self, shared: dict[str, Any], prep_result: str, exec_result: dict[str, Any]
    ) -> str | None:
        shared["query_results"] = exec_result
        return self.get_next_node_id()


class ExampleProcessNode(Node):
    """Example node that processes data."""

    def __init__(self):
        super().__init__()

    def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
        return shared.get("query_results", {})

    def exec(self, prep_result: dict[str, Any]) -> dict[str, Any]:
        # Simulate processing
        results = prep_result.get("results", [])
        processed = [f"processed_{item}" for item in results]
        return {"processed_results": processed}

    def post(
        self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: dict[str, Any]
    ) -> str | None:
        shared["processed_data"] = exec_result
        return self.get_next_node_id()


class ExampleReviewNode(Node):
    """Example node that reviews data and makes decisions."""

    def __init__(self):
        super().__init__()

    def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
        return shared.get("processed_data", {})

    def exec(self, prep_result: dict[str, Any]) -> str:
        # Simulate review decision
        results = prep_result.get("processed_results", [])
        if len(results) > 2:
            return "approved"
        elif len(results) > 0:
            return "needs_revision"
        else:
            return "rejected"

    def post(
        self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: str
    ) -> str | None:
        shared["decision"] = exec_result
        return self.get_next_node_id(exec_result)


class ExampleApprovalNode(Node):
    """Example node for approved results."""

    def __init__(self):
        super().__init__()

    def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
        return shared

    def exec(self, prep_result: dict[str, Any]) -> str:
        return "Results approved and finalized"

    def post(
        self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: str
    ) -> str | None:
        shared["final_result"] = exec_result
        return self.get_next_node_id()


class ExampleRevisionNode(Node):
    """Example node for revision."""

    def __init__(self):
        super().__init__()

    def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
        return shared

    def exec(self, prep_result: dict[str, Any]) -> str:
        return "Results revised"

    def post(
        self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: str
    ) -> str | None:
        shared["revision_result"] = exec_result
        return self.get_next_node_id()


class ExampleRejectionNode(Node):
    """Example node for rejected results."""

    def __init__(self):
        super().__init__()

    def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
        return shared

    def exec(self, prep_result: dict[str, Any]) -> str:
        return "Results rejected"

    def post(
        self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: str
    ) -> str | None:
        shared["final_result"] = exec_result
        return self.get_next_node_id()


def example_simple_chaining():
    """
    Example of simple node chaining using >> operator.

    This follows the PocketFlow documentation pattern:
    node_a >> node_b
    flow = Flow(start=node_a)
    """

    # Create nodes
    query_node = ExampleQueryNode()
    process_node = ExampleProcessNode()

    # Use new chaining syntax following PocketFlow documentation
    query_node >> process_node

    # Create flow with automatic node registration
    flow = Flow(start=query_node)

    # Run the flow
    shared = {"query": "example query"}
    result = flow.run(shared)

    return result


def example_branching_pattern():
    """
    Example of branching pattern using - operator.

    This follows the PocketFlow documentation pattern:
    review - "approved" >> approval
    review - "needs_revision" >> revision
    review - "rejected" >> rejection
    """

    # Create nodes
    query_node = ExampleQueryNode()
    process_node = ExampleProcessNode()
    review_node = ExampleReviewNode()
    approval_node = ExampleApprovalNode()
    revision_node = ExampleRevisionNode()
    rejection_node = ExampleRejectionNode()

    # Create the flow with chaining and branching
    # First, chain the initial processing
    query_node >> process_node >> review_node

    # Then add branching logic following PocketFlow patterns
    review_node - "approved" >> approval_node
    review_node - "needs_revision" >> revision_node
    review_node - "rejected" >> rejection_node

    # Revision loops back to review
    revision_node >> review_node

    # Create flow with automatic node registration
    flow = Flow(start=query_node)

    # Test different scenarios
    scenarios = [
        {"query": "big query", "expected": "approved"},
        {"query": "small", "expected": "needs_revision"},
        {"query": "", "expected": "rejected"},
    ]

    for scenario in scenarios:
        shared = {"query": scenario["query"]}
        flow.run(shared)

    return scenarios


def example_complex_workflow():
    """
    Example of a complex workflow combining chaining and branching.
    """

    # Create nodes for a document processing workflow
    class LoadDocumentNode(Node):
        def __init__(self):
            super().__init__()

        def prep(self, shared: dict[str, Any]) -> str:
            return shared.get("document_path", "")

        def exec(self, prep_result: str) -> dict[str, Any]:
            # Simulate document loading
            return {
                "content": f"Document content from {prep_result}",
                "size": len(prep_result) * 100,
            }

        def post(
            self, shared: dict[str, Any], prep_result: str, exec_result: dict[str, Any]
        ) -> str | None:
            shared["document"] = exec_result
            return self.get_next_node_id()

    class ValidateDocumentNode(Node):
        def __init__(self):
            super().__init__()

        def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
            return shared.get("document", {})

        def exec(self, prep_result: dict[str, Any]) -> str:
            size = prep_result.get("size", 0)
            if size > 1000:
                return "large_document"
            elif size > 100:
                return "medium_document"
            else:
                return "small_document"

        def post(
            self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: str
        ) -> str | None:
            shared["document_type"] = exec_result
            return self.get_next_node_id(exec_result)

    class ProcessLargeDocumentNode(Node):
        def __init__(self):
            super().__init__()

        def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
            return shared.get("document", {})

        def exec(self, prep_result: dict[str, Any]) -> str:
            return "Large document processed with special handling"

        def post(
            self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: str
        ) -> str | None:
            shared["processing_result"] = exec_result
            return self.get_next_node_id()

    class ProcessMediumDocumentNode(Node):
        def __init__(self):
            super().__init__()

        def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
            return shared.get("document", {})

        def exec(self, prep_result: dict[str, Any]) -> str:
            return "Medium document processed normally"

        def post(
            self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: str
        ) -> str | None:
            shared["processing_result"] = exec_result
            return self.get_next_node_id()

    class ProcessSmallDocumentNode(Node):
        def __init__(self):
            super().__init__()

        def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
            return shared.get("document", {})

        def exec(self, prep_result: dict[str, Any]) -> str:
            return "Small document processed quickly"

        def post(
            self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: str
        ) -> str | None:
            shared["processing_result"] = exec_result
            return self.get_next_node_id()

    # Create nodes
    load_node = LoadDocumentNode()
    validate_node = ValidateDocumentNode()
    process_large_node = ProcessLargeDocumentNode()
    process_medium_node = ProcessMediumDocumentNode()
    process_small_node = ProcessSmallDocumentNode()

    # Create workflow with chaining and branching
    load_node >> validate_node

    # Branch based on document type
    validate_node - "large_document" >> process_large_node
    validate_node - "medium_document" >> process_medium_node
    validate_node - "small_document" >> process_small_node

    # Create flow
    flow = Flow(start=load_node)

    # Test with different document types
    test_cases = [
        {"document_path": "large_document.pdf", "expected": "large"},
        {"document_path": "medium.docx", "expected": "medium"},
        {"document_path": "small.txt", "expected": "small"},
    ]

    for test_case in test_cases:
        shared = {"document_path": test_case["document_path"]}
        flow.run(shared)

    return test_cases


if __name__ == "__main__":
    """
    Run examples to demonstrate PocketFlow pattern alignment.
    """

    # Run examples
    example_simple_chaining()
    example_branching_pattern()
    example_complex_workflow()
