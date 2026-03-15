"""Data-driven registry of known n8n node types per classification category."""

from phaeton_models.analyzer import NodeCategory

FLOW_CONTROL_TYPES: set[str] = {
    "n8n-nodes-base.if",
    "n8n-nodes-base.switch",
    "n8n-nodes-base.merge",
    "n8n-nodes-base.splitInBatches",
    "n8n-nodes-base.set",
    "n8n-nodes-base.noOp",
    "n8n-nodes-base.wait",
    "n8n-nodes-base.filter",
    "n8n-nodes-base.limit",
    "n8n-nodes-base.removeDuplicates",
    "n8n-nodes-base.aggregate",
    "n8n-nodes-base.splitOut",
    "n8n-nodes-base.summarize",
    "n8n-nodes-base.stopAndError",
    "n8n-nodes-base.executeWorkflow",
}

AWS_NATIVE_TYPES: set[str] = {
    "n8n-nodes-base.awsS3",
    "n8n-nodes-base.awsDynamoDB",
    "n8n-nodes-base.awsSqs",
    "n8n-nodes-base.awsSns",
    "n8n-nodes-base.awsSes",
    "n8n-nodes-base.awsLambda",
    "n8n-nodes-base.awsEventBridge",
    "n8n-nodes-base.awsTextract",
    "n8n-nodes-base.awsComprehend",
    "n8n-nodes-base.awsRekognition",
    "n8n-nodes-base.emailSend",  # generic SMTP node mapped to SES
}

TRIGGER_TYPES: set[str] = {
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.formTrigger",
    "n8n-nodes-base.errorTrigger",
    "n8n-nodes-base.executeWorkflowTrigger",
}

CODE_TYPE = "n8n-nodes-base.code"
HTTP_REQUEST_TYPE = "n8n-nodes-base.httpRequest"

# Translation strategies by category
TRANSLATION_STRATEGIES: dict[NodeCategory, str] = {
    NodeCategory.FLOW_CONTROL: "Deterministic mapping to ASL flow-control states (Choice, Map, Pass, Wait, etc.)",
    NodeCategory.TRIGGER: "Map to EventBridge rule, API Gateway, or Step Functions invocation trigger",
    NodeCategory.AWS_NATIVE: "Direct SDK integration via ASL Task state with AWS service resource ARN",
    NodeCategory.PICOFUN_API: "Generate PicoFun API client; invoke via Lambda Task state",
    NodeCategory.GRAPHQL_API: "Generate GraphQL client; invoke via Lambda Task state",
    NodeCategory.CODE_JS: "Lift-and-shift JavaScript to Lambda function",
    NodeCategory.CODE_PYTHON: "Lift-and-shift Python to Lambda function",
    NodeCategory.UNSUPPORTED: "No automated translation available; requires manual intervention",
}


class NodeRegistry:
    """Registry of known node types per classification category."""

    def __init__(self) -> None:
        """Initialize with default node type sets."""
        self.flow_control_types = set(FLOW_CONTROL_TYPES)
        self.aws_native_types = set(AWS_NATIVE_TYPES)
        self.trigger_types = set(TRIGGER_TYPES)

    def is_flow_control(self, node_type: str) -> bool:
        """Check if a node type is a flow control node."""
        return node_type in self.flow_control_types

    def is_aws_native(self, node_type: str) -> bool:
        """Check if a node type is an AWS native service node."""
        return node_type in self.aws_native_types

    def is_trigger(self, node_type: str) -> bool:
        """Check if a node type is a trigger node."""
        if node_type in self.trigger_types:
            return True
        return node_type.endswith("Trigger")

    def is_code(self, node_type: str) -> bool:
        """Check if a node type is a code node."""
        return node_type == CODE_TYPE

    def is_http_request(self, node_type: str) -> bool:
        """Check if a node type is an HTTP Request node."""
        return node_type == HTTP_REQUEST_TYPE

    def is_n8n_base(self, node_type: str) -> bool:
        """Check if a node type is from the n8n-nodes-base package."""
        return node_type.startswith("n8n-nodes-base.")
