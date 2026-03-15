# ADR-004: AWS Strands Agents for AI Agent Service

**Status:** Accepted
**Date:** 2025-06-01

## Context

The deterministic translation engine handles known n8n node types through a plugin-based translator system (`BaseTranslator` subclasses). However, new or uncommon node types, complex expressions, and edge cases may not have dedicated translators. The pipeline needs a fallback mechanism that can attempt reasonable ASL translations for unsupported nodes rather than failing or producing empty stubs.

Several approaches were considered:
- **Custom LLM integration** — directly calling an LLM API (e.g., Bedrock `invoke_model`) with handcrafted prompts.
- **LangChain or similar framework** — using a general-purpose LLM orchestration framework.
- **AWS Strands Agents** — using AWS's purpose-built agent framework with native Bedrock integration.

## Decision

Use the AWS Strands Agents framework (`strands-agents`) with an AWS Bedrock LLM backend for the AI agent fallback service. The agent is implemented as a standalone component (`ai-agent/`) and integrated into the Translation Engine via the `AIAgentProtocol` abstract protocol.

Key design choices:
- The agent is invoked only when all deterministic translators decline a node (return `False` from `can_translate()`).
- A system prompt constrains the agent's output to valid ASL JSON, JSONata for data transformations, and SSM parameter references for credentials.
- The agent exposes two operations: `translate_node()` for full node translation and `translate_expression()` for individual expression conversion.
- Each response includes a `Confidence` level (HIGH, MEDIUM, LOW) so downstream consumers can flag uncertain translations.

## Consequences

### Positive
- Strands Agents provides native AWS Bedrock integration, avoiding the complexity of managing LLM API calls, retries, and token limits directly.
- The `AIAgentProtocol` abstraction keeps the agent pluggable — the Translation Engine does not depend on Strands directly, only on the protocol interface.
- The confidence scoring lets the Packager flag AI-generated states in the migration checklist, prompting human review.

### Negative
- The Strands Agents framework is relatively new, with a smaller ecosystem and less community support than alternatives like LangChain.
- AI-generated ASL may contain subtle errors (invalid state references, incorrect JSONata syntax) that pass JSON Schema validation but fail at runtime.
- The agent adds latency and cost to the translation pipeline for any workflow containing unsupported nodes.

### Neutral
- The agent is deployed as a separate service (Lambda or AgentCore), keeping the deterministic Translation Engine lightweight and independently deployable.
- The `strands-agents-builder` dependency is used for agent construction utilities but is not required at runtime for the core Translation Engine.
