"""
Priority node registry and classification module.

Defines the core priority node sets (flow control, AWS services, top-50 by
usage) and provides functions for classifying nodes into translation strategy
categories and generating coverage reports.
"""

from __future__ import annotations

from n8n_release_parser.models import (
    NodeApiMapping,
    NodeCatalog,
    NodeClassification,
    NodeTypeEntry,
)

# ---------------------------------------------------------------------------
# Priority node registries
# ---------------------------------------------------------------------------

CORE_FLOW_CONTROL_NODES: set[str] = {
    "n8n-nodes-base.if",
    "n8n-nodes-base.switch",
    "n8n-nodes-base.merge",
    "n8n-nodes-base.splitInBatches",
    "n8n-nodes-base.set",
    "n8n-nodes-base.code",
    "n8n-nodes-base.function",
    "n8n-nodes-base.noOp",
    "n8n-nodes-base.wait",
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.executeWorkflow",
    "n8n-nodes-base.respondToWebhook",
    "n8n-nodes-base.errorTrigger",
}

AWS_SERVICE_NODES: set[str] = {
    "n8n-nodes-base.awsS3",
    "n8n-nodes-base.awsDynamoDB",  # or awsDynamoDb
    "n8n-nodes-base.awsSqs",
    "n8n-nodes-base.awsSns",
    "n8n-nodes-base.awsSes",
    "n8n-nodes-base.awsLambda",
    "n8n-nodes-base.awsEventBridge",  # or similar
    "n8n-nodes-base.awsSecretsManager",  # or similar
    "n8n-nodes-base.awsTextract",
    "n8n-nodes-base.awsComprehend",
    "n8n-nodes-base.awsRekognition",
    "n8n-nodes-base.awsStepFunctions",  # or similar
    "n8n-nodes-base.awsCloudWatch",  # or similar
    "n8n-nodes-base.awsKinesis",  # or similar
    "n8n-nodes-base.emailSend",  # generic SMTP node mapped to SES
}

TOP_50_NODES: list[str] = [
    "n8n-nodes-base.code",
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.set",
    "n8n-nodes-base.if",
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.noOp",
    "n8n-nodes-base.merge",
    "n8n-nodes-base.splitInBatches",
    "n8n-nodes-base.switch",
    "n8n-nodes-base.formTrigger",
    "n8n-nodes-base.wait",
    "n8n-nodes-base.respondToWebhook",
    "n8n-nodes-base.dataTable",
    "n8n-nodes-base.splitOut",
    "n8n-nodes-base.filter",
    "n8n-nodes-base.extractFromFile",
    "n8n-nodes-base.aggregate",
    "n8n-nodes-base.readWriteFile",
    "n8n-nodes-base.executeWorkflow",
    "n8n-nodes-base.supabase",
    "n8n-nodes-base.convertToFile",
    "n8n-nodes-base.executeWorkflowTrigger",
    "n8n-nodes-base.airtable",
    "n8n-nodes-base.httpRequestTool",
    "n8n-nodes-base.whatsApp",
    "n8n-nodes-base.whatsAppTrigger",
    "n8n-nodes-base.emailSend",
    "n8n-nodes-base.limit",
    "n8n-nodes-base.slack",
    "n8n-nodes-base.rssFeedRead",
    "n8n-nodes-base.html",
    "n8n-nodes-base.form",
    "n8n-nodes-base.discord",
    "n8n-nodes-base.emailReadImap",
    "n8n-nodes-base.youTube",
    "n8n-nodes-base.executeCommand",
    "n8n-nodes-base.dateTime",
    "n8n-nodes-base.summarize",
    "n8n-nodes-base.executionData",
    "n8n-nodes-base.errorTrigger",
    "n8n-nodes-base.stopAndError",
    "n8n-nodes-base.facebookGraphApi",
    "n8n-nodes-base.aiTransform",
    "n8n-nodes-base.removeDuplicates",
    "n8n-nodes-base.slackTrigger",
    "n8n-nodes-base.markdown",
    "n8n-nodes-base.supabaseTool",
    "n8n-nodes-base.rssFeedReadTrigger",
]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


_CODE_NODE_TYPES: set[str] = {
    "n8n-nodes-base.code",
    "n8n-nodes-base.function",
}


def _is_trigger_node(node: NodeTypeEntry) -> bool:
    """Return True if the node is a trigger based on group or name suffix."""
    return any(g.lower() == "trigger" for g in node.group) or node.node_type.endswith(
        "Trigger"
    )


def _classify_code_node(node: NodeTypeEntry) -> NodeClassification:
    """Return CODE_PYTHON or CODE_JS based on the node's language parameter."""
    for param in node.parameters:
        if param.name in {"language", "mode"} and param.default == "python":
            return NodeClassification.CODE_PYTHON
    return NodeClassification.CODE_JS


def _has_graphql_defaults(node: NodeTypeEntry) -> bool:
    """Return True if request_defaults reference a GraphQL endpoint."""
    if node.request_defaults is None:
        return False
    return any(
        isinstance(v, str) and "graphql" in v.lower()
        for v in node.request_defaults.values()
    )


def classify_node(
    node: NodeTypeEntry,
    api_mapping: NodeApiMapping | None,
) -> NodeClassification:
    """
    Classify a node into a translation strategy category.

    Priority order:
    1. AWS_SERVICE_NODES -> AWS_NATIVE
    2. CORE_FLOW_CONTROL_NODES -> FLOW_CONTROL (or TRIGGER for trigger nodes)
    3. Code node (JS mode) -> CODE_JS
    4. Code node (Python mode) -> CODE_PYTHON
    5. Has api_mapping -> PICOFUN_API
    6. Targets GraphQL endpoint -> GRAPHQL_API
    7. Otherwise -> UNSUPPORTED
    """
    if node.node_type in AWS_SERVICE_NODES:
        return NodeClassification.AWS_NATIVE

    if node.node_type in _CODE_NODE_TYPES:
        return _classify_code_node(node)

    if node.node_type in CORE_FLOW_CONTROL_NODES:
        return (
            NodeClassification.TRIGGER
            if _is_trigger_node(node)
            else NodeClassification.FLOW_CONTROL
        )

    if api_mapping is not None:
        return NodeClassification.PICOFUN_API

    if _has_graphql_defaults(node):
        return NodeClassification.GRAPHQL_API

    return NodeClassification.UNSUPPORTED


# ---------------------------------------------------------------------------
# Priority helpers
# ---------------------------------------------------------------------------


def is_priority_node(node_type: str) -> bool:
    """Check if a node type is in any priority group."""
    return (
        node_type in CORE_FLOW_CONTROL_NODES
        or node_type in AWS_SERVICE_NODES
        or node_type in TOP_50_NODES
    )


def priority_coverage_report(
    catalog: NodeCatalog,
    mappings: list[NodeApiMapping],
) -> dict[str, object]:
    """
    Generate coverage report for priority nodes.

    Returns dict with:
    - total_priority_nodes: count in catalog
    - mapped_priority_nodes: count with API mappings
    - missing_mappings: list of priority node types without mappings
    - breakdown: dict with counts per priority group
    """
    catalog_types = {entry.node_type for entry in catalog.entries}
    mapped_types = {m.node_type for m in mappings}

    # Priority nodes present in the catalog
    priority_in_catalog = {nt for nt in catalog_types if is_priority_node(nt)}
    mapped_priority = priority_in_catalog & mapped_types
    missing = sorted(priority_in_catalog - mapped_types)

    # Breakdown by group
    breakdown: dict[str, int] = {
        "core_flow_control": len(priority_in_catalog & CORE_FLOW_CONTROL_NODES),
        "aws_service": len(priority_in_catalog & AWS_SERVICE_NODES),
        "top_50": len(priority_in_catalog & set(TOP_50_NODES)),
    }

    return {
        "total_priority_nodes": len(priority_in_catalog),
        "mapped_priority_nodes": len(mapped_priority),
        "missing_mappings": missing,
        "breakdown": breakdown,
    }
