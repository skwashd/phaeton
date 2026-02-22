"""Main orchestrator for the n8n to Step Functions translation pipeline."""

from __future__ import annotations

import graphlib
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel

from n8n_to_sfn.models.analysis import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)
from n8n_to_sfn.models.asl import PassState, StateMachine
from n8n_to_sfn.translators.base import (
    BaseTranslator,
    LambdaArtifact,
    TranslationContext,
    TranslationResult,
    TriggerArtifact,
)
from n8n_to_sfn.validator import validate_asl

if TYPE_CHECKING:
    pass


class AIAgentProtocol(Protocol):
    """Protocol for AI agent fallback implementations."""

    def translate_node(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate a node using AI agent fallback."""
        ...


class TranslationOutput(BaseModel):
    """Final output of the full translation pipeline."""

    state_machine: StateMachine
    lambda_artifacts: list[LambdaArtifact] = []
    trigger_artifacts: list[TriggerArtifact] = []
    conversion_report: dict[str, Any] = {}
    warnings: list[str] = []


class TranslationEngine:
    """Orchestrates the full n8n-to-Step Functions translation pipeline."""

    def __init__(
        self,
        translators: list[BaseTranslator],
        ai_agent: AIAgentProtocol | None = None,
    ) -> None:
        """Initialize with a list of translators and optional AI agent fallback."""
        self._translators = translators
        self._ai_agent = ai_agent

    def translate(self, analysis: WorkflowAnalysis) -> TranslationOutput:
        """Run the full translation pipeline on an analyzed workflow."""
        ordered_names = self._topological_sort(analysis)
        context = TranslationContext(analysis=analysis)

        all_states: dict[str, Any] = {}
        all_lambdas: list[LambdaArtifact] = []
        all_triggers: list[TriggerArtifact] = []
        all_warnings: list[str] = []
        node_state_names: dict[str, str] = {}

        node_by_name = {cn.node.name: cn for cn in analysis.classified_nodes}

        for node_name in ordered_names:
            cn = node_by_name.get(node_name)
            if cn is None:
                continue

            result = self._translate_node(cn, context)
            if result is None:
                continue

            all_lambdas.extend(result.lambda_artifacts)
            all_triggers.extend(result.trigger_artifacts)
            all_warnings.extend(result.warnings)

            for state_name, state in result.states.items():
                all_states[state_name] = state
                node_state_names[node_name] = state_name

        if not all_states:
            all_states["Empty"] = PassState(end=True)

        self._wire_transitions(all_states, analysis, node_state_names)

        start_at = self._determine_start_at(ordered_names, node_state_names)
        sm = StateMachine(start_at=start_at, states=all_states)

        context.state_machine = sm

        validation_errors = validate_asl(sm)
        if validation_errors:
            all_warnings.extend(
                [f"ASL validation warning: {e}" for e in validation_errors]
            )

        report = self._build_report(analysis, node_state_names, all_warnings)

        return TranslationOutput(
            state_machine=sm,
            lambda_artifacts=all_lambdas,
            trigger_artifacts=all_triggers,
            conversion_report=report,
            warnings=all_warnings,
        )

    def _translate_node(
        self,
        cn: ClassifiedNode,
        context: TranslationContext,
    ) -> TranslationResult | None:
        """Find the right translator for a node and translate it."""
        if cn.classification == NodeClassification.UNSUPPORTED:
            return TranslationResult(
                warnings=[f"Unsupported node skipped: {cn.node.name} ({cn.node.type})"],
            )

        if cn.classification == NodeClassification.TRIGGER:
            for translator in self._translators:
                if translator.can_translate(cn):
                    return translator.translate(cn, context)
            return TranslationResult(
                warnings=[f"No translator for trigger: {cn.node.name}"],
            )

        for translator in self._translators:
            if translator.can_translate(cn):
                return translator.translate(cn, context)

        if self._ai_agent is not None:
            try:
                return self._ai_agent.translate_node(cn, context)
            except NotImplementedError:
                return TranslationResult(
                    warnings=[
                        f"AI agent not implemented for node: {cn.node.name}",
                    ],
                    metadata={"ai_attempted": True},
                )

        return TranslationResult(
            warnings=[f"No translator found for node: {cn.node.name} ({cn.node.type})"],
        )

    def _topological_sort(self, analysis: WorkflowAnalysis) -> list[str]:
        """Topologically sort node names using the dependency graph."""
        graph: dict[str, set[str]] = {}
        all_names = {cn.node.name for cn in analysis.classified_nodes}

        for name in all_names:
            graph[name] = set()

        for edge in analysis.dependency_edges:
            if edge.to_node in all_names and edge.from_node in all_names:
                graph[edge.to_node].add(edge.from_node)

        sorter = graphlib.TopologicalSorter(graph)
        return list(sorter.static_order())

    def _wire_transitions(
        self,
        all_states: dict[str, Any],
        analysis: WorkflowAnalysis,
        node_state_names: dict[str, str],
    ) -> None:
        """Wire up Next transitions between states based on dependency edges."""
        successors: dict[str, list[str]] = {}
        for edge in analysis.dependency_edges:
            if edge.edge_type == "CONNECTION":
                successors.setdefault(edge.from_node, []).append(edge.to_node)

        self._apply_next_transitions(all_states, node_state_names, successors)
        self._apply_end_to_terminal_states(all_states)

    def _apply_next_transitions(
        self,
        all_states: dict[str, Any],
        node_state_names: dict[str, str],
        successors: dict[str, list[str]],
    ) -> None:
        """Set Next on states that have downstream successors."""
        for node_name, state_name in node_state_names.items():
            state = all_states.get(state_name)
            if state is None:
                continue
            nexts = successors.get(node_name, [])
            if not nexts:
                continue
            next_state_names = [
                node_state_names[n] for n in nexts if n in node_state_names
            ]
            if not next_state_names:
                continue
            can_set_next = (
                hasattr(state, "next")
                and state.next is None
                and not getattr(state, "end", False)
                and not hasattr(state, "choices")
            )
            if can_set_next:
                state.next = next_state_names[0]

    @staticmethod
    def _apply_end_to_terminal_states(all_states: dict[str, Any]) -> None:
        """Set End=True on states that have no Next and no End yet."""
        for state in all_states.values():
            has_next = hasattr(state, "next") and state.next is not None
            has_end = hasattr(state, "end") and state.end
            has_choices = hasattr(state, "choices")
            if (
                not has_next
                and not has_end
                and not has_choices
                and hasattr(state, "end")
            ):
                state.end = True

    def _determine_start_at(
        self,
        ordered_names: list[str],
        node_state_names: dict[str, str],
    ) -> str:
        """Determine the StartAt state name."""
        for name in ordered_names:
            if name in node_state_names:
                return node_state_names[name]
        return next(iter(node_state_names.values())) if node_state_names else "Empty"

    def _build_report(
        self,
        analysis: WorkflowAnalysis,
        node_state_names: dict[str, str],
        warnings: list[str],
    ) -> dict[str, Any]:
        """Build the conversion report dict."""
        classification_counts: dict[str, int] = {}
        for cn in analysis.classified_nodes:
            key = cn.classification.value
            classification_counts[key] = classification_counts.get(key, 0) + 1

        return {
            "total_nodes": len(analysis.classified_nodes),
            "translated_nodes": len(node_state_names),
            "classification_breakdown": classification_counts,
            "confidence_score": analysis.confidence_score,
            "warning_count": len(warnings),
        }
