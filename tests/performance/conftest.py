"""
Shared fixtures for performance and load tests.

Provides synthetic n8n workflow generators of configurable size and
benchmarking helpers that measure execution time and peak memory usage.
"""

from __future__ import annotations

import random
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from n8n_to_sfn.engine import TranslationEngine
from n8n_to_sfn.translators.aws_service import AWSServiceTranslator
from n8n_to_sfn.translators.code_node import CodeNodeTranslator
from n8n_to_sfn.translators.database import DatabaseTranslator
from n8n_to_sfn.translators.flow_control import FlowControlTranslator
from n8n_to_sfn.translators.http_request import HttpRequestTranslator
from n8n_to_sfn.translators.picofun import PicoFunTranslator
from n8n_to_sfn.translators.saas.airtable import AirtableTranslator
from n8n_to_sfn.translators.saas.gmail import GmailTranslator
from n8n_to_sfn.translators.saas.google_sheets import GoogleSheetsTranslator
from n8n_to_sfn.translators.saas.notion import NotionTranslator
from n8n_to_sfn.translators.saas.slack import SlackTranslator
from n8n_to_sfn.translators.set_node import SetNodeTranslator
from n8n_to_sfn.translators.triggers import TriggerTranslator
from n8n_to_sfn_packager.packager import Packager
from workflow_analyzer.analyzer import WorkflowAnalyzer

# Deterministic seed for reproducible benchmarks.
_RNG_SEED = 42

# Node-type templates that the pipeline knows how to translate.
_AWS_NODE_TEMPLATES: list[dict[str, Any]] = [
    {
        "type": "n8n-nodes-base.awsDynamoDB",
        "typeVersion": 1,
        "parameters": {
            "resource": "item",
            "operation": "create",
            "tableName": "PerfTable",
            "additionalFields": {},
        },
    },
    {
        "type": "n8n-nodes-base.awsSns",
        "typeVersion": 1,
        "parameters": {
            "resource": "message",
            "operation": "publish",
            "topicArn": "arn:aws:sns:us-east-1:123456789012:PerfTopic",
            "subject": "perf",
            "message": "hello",
        },
    },
    {
        "type": "n8n-nodes-base.awsSqs",
        "typeVersion": 1,
        "parameters": {
            "queue": "https://sqs.us-east-1.amazonaws.com/123456789012/PerfQueue",
            "operation": "sendMessage",
            "message": "hello",
        },
    },
    {
        "type": "n8n-nodes-base.awsLambda",
        "typeVersion": 1,
        "parameters": {
            "functionName": "PerfFunction",
            "payload": "{}",
        },
    },
]


def _make_trigger_node() -> dict[str, Any]:
    """Return a manual-trigger node (always the first node)."""
    return {
        "id": "perf-0000-4000-8000-000000000000",
        "name": "ManualTrigger",
        "type": "n8n-nodes-base.manualTrigger",
        "typeVersion": 1,
        "position": [100, 300],
        "parameters": {},
    }


def _make_node(index: int, template: dict[str, Any]) -> dict[str, Any]:
    """Return a workflow node from *template* at position *index*."""
    return {
        "id": f"perf-{index:04d}-4000-8000-{index:012d}",
        "name": f"Node_{index}",
        "type": template["type"],
        "typeVersion": template["typeVersion"],
        "position": [200 + index * 200, 300],
        "parameters": dict(template["parameters"]),
    }


def generate_workflow(num_nodes: int, *, seed: int = _RNG_SEED) -> dict[str, Any]:
    """
    Generate a synthetic n8n workflow with *num_nodes* total nodes.

    The first node is always a manual trigger.  The remaining nodes are
    randomly chosen AWS-service nodes connected in a linear chain so that
    each node feeds into the next.  Uses a seeded PRNG for deterministic
    output (not used for cryptographic purposes).
    """
    rng = random.Random(seed)  # noqa: S311

    trigger = _make_trigger_node()
    nodes: list[dict[str, Any]] = [trigger]

    for i in range(1, num_nodes):
        template = rng.choice(_AWS_NODE_TEMPLATES)
        nodes.append(_make_node(i, template))

    # Build linear connections: each node connects to the next.
    connections: dict[str, Any] = {}
    for i in range(len(nodes) - 1):
        source_name = nodes[i]["name"]
        target_name = nodes[i + 1]["name"]
        connections[source_name] = {
            "main": [[{"node": target_name, "type": "main", "index": 0}]],
        }

    return {
        "name": f"perf_workflow_{num_nodes}_nodes",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
    }


@dataclass
class BenchmarkResult:
    """Captures timing and memory metrics for a single benchmark run."""

    elapsed_seconds: float
    peak_memory_bytes: int
    result: Any


def run_timed(
    func: Callable[..., object], *args: object, **kwargs: object
) -> BenchmarkResult:
    """
    Execute *func* while measuring wall-clock time and peak memory.

    Uses ``tracemalloc`` to capture peak memory allocated during the call.
    """
    tracemalloc.start()
    # Reset the peak to measure only this call.
    tracemalloc.reset_peak()

    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return BenchmarkResult(
        elapsed_seconds=elapsed,
        peak_memory_bytes=peak,
        result=result,
    )


# ---------------------------------------------------------------------------
# Shared pipeline-component factories (avoid repeating imports everywhere)
# ---------------------------------------------------------------------------


def make_analyzer() -> WorkflowAnalyzer:
    """Create a fresh ``WorkflowAnalyzer`` instance."""
    return WorkflowAnalyzer()


def make_translation_engine() -> TranslationEngine:
    """Create a ``TranslationEngine`` with all registered translators."""
    return TranslationEngine(
        translators=[
            FlowControlTranslator(),
            AWSServiceTranslator(),
            TriggerTranslator(),
            CodeNodeTranslator(),
            DatabaseTranslator(),
            HttpRequestTranslator(),
            SetNodeTranslator(),
            SlackTranslator(),
            GmailTranslator(),
            GoogleSheetsTranslator(),
            NotionTranslator(),
            AirtableTranslator(),
            PicoFunTranslator(),
        ],
    )


def make_packager() -> Packager:
    """Create a fresh ``Packager`` instance."""
    return Packager()


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

# Standard sizes used across performance tests.
WORKFLOW_SIZES = [10, 50, 100, 200]


@pytest.fixture(params=WORKFLOW_SIZES)
def workflow_size(request: pytest.FixtureRequest) -> int:
    """Parametrised fixture yielding each standard workflow size."""
    return request.param
