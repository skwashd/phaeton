"""Main orchestrator for the n8n to Step Functions translation pipeline."""

from __future__ import annotations

import graphlib
from typing import TYPE_CHECKING, Any, Protocol

from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)
from pydantic import BaseModel

from n8n_to_sfn.models.asl import ParallelState, PassState, StateMachine
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
        merge_metadata: dict[str, dict[str, Any]] = {}

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

            if result.metadata.get("merge_node"):
                merge_metadata[node_name] = result.metadata

            for state_name, state in result.states.items():
                all_states[state_name] = state
                node_state_names[node_name] = state_name

        if not all_states:
            all_states["Empty"] = PassState(end=True)

        self._apply_parallel_for_merges(
            all_states, analysis, node_state_names, merge_metadata, all_warnings
        )

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

    def _apply_parallel_for_merges(
        self,
        all_states: dict[str, Any],
        analysis: WorkflowAnalysis,
        node_state_names: dict[str, str],
        merge_metadata: dict[str, dict[str, Any]],
        warnings: list[str],
    ) -> None:
        """Replace fork-to-merge regions with Parallel states.

        For each Merge node detected during translation, walk backwards along
        CONNECTION edges to find the common fork point and collect branch
        states.  The fork-to-merge region is then replaced with a single
        ``ParallelState`` whose branches contain the intermediate states.
        """
        if not merge_metadata:
            return

        predecessors, successors = self._build_adjacency(analysis)

        for merge_name, meta in merge_metadata.items():
            incoming = predecessors.get(merge_name, [])
            if len(incoming) < 2:
                warnings.append(
                    f"Merge node '{merge_name}': expected >=2 incoming branches, "
                    f"found {len(incoming)}.  Skipping Parallel wrapping."
                )
                continue

            fork_node = self._find_fork_point(
                merge_name, incoming, predecessors
            )
            if fork_node is None:
                warnings.append(
                    f"Merge node '{merge_name}': could not determine common "
                    "fork point.  Skipping Parallel wrapping."
                )
                continue

            branches, branch_state_names = self._build_parallel_branches(
                fork_node, merge_name, successors, node_state_names, all_states
            )

            if not branches:
                warnings.append(
                    f"Merge node '{merge_name}': no valid branches found.  "
                    "Skipping Parallel wrapping."
                )
                continue

            self._install_parallel_state(
                merge_name, fork_node, meta, branches,
                branch_state_names, all_states, node_state_names,
                successors,
            )

    def _build_parallel_branches(
        self,
        fork_node: str,
        merge_name: str,
        successors: dict[str, list[str]],
        node_state_names: dict[str, str],
        all_states: dict[str, Any],
    ) -> tuple[list[StateMachine], set[str]]:
        """Build branch StateMachines for each path from fork to merge."""
        branches: list[StateMachine] = []
        branch_state_names: set[str] = set()

        for branch_start in successors.get(fork_node, []):
            chain = self._collect_branch_chain(
                branch_start, merge_name, successors
            )
            if not chain:
                continue

            branch_states: dict[str, Any] = {}
            for name in chain:
                state_name = node_state_names.get(name, name)
                if state_name in all_states:
                    branch_states[state_name] = all_states[state_name]
                    branch_state_names.add(state_name)

            if not branch_states:
                continue

            first_state_name = node_state_names.get(chain[0], chain[0])
            last_state_name = node_state_names.get(chain[-1], chain[-1])
            last_state = branch_states.get(last_state_name)
            if last_state is not None and hasattr(last_state, "next"):
                last_state.next = None
                last_state.end = True

            branches.append(
                StateMachine(
                    start_at=first_state_name,
                    states=branch_states,
                    query_language=None,
                )
            )

        return branches, branch_state_names

    def _install_parallel_state(
        self,
        merge_name: str,
        fork_node: str,
        meta: dict[str, Any],
        branches: list[StateMachine],
        branch_state_names: set[str],
        all_states: dict[str, Any],
        node_state_names: dict[str, str],
        successors: dict[str, list[str]],
    ) -> None:
        """Replace the fork-to-merge region with a Parallel state."""
        merge_mode = meta.get("merge_mode", "append")
        parallel_name = node_state_names.get(merge_name, merge_name)

        parallel_state = ParallelState(
            branches=branches,
            comment=f"Parallel merge ({merge_mode}): {merge_name}",
        )

        # Remove branch states from the top-level state machine
        for name in branch_state_names:
            all_states.pop(name, None)

        # Replace the merge placeholder with the Parallel state
        all_states.pop(parallel_name, None)

        # The Parallel state takes the fork node's name in the state
        # machine so existing inbound transitions still work.
        fork_state_name = node_state_names.get(fork_node, fork_node)
        all_states.pop(fork_state_name, None)
        all_states[fork_state_name] = parallel_state

        # Update node_state_names so the merge node maps to the fork
        # state name (the Parallel state) for downstream wiring.
        node_state_names[merge_name] = fork_state_name

        # Remove fork's successors from node_state_names so wiring
        # doesn't attempt to set Next on removed states.
        for branch_start in successors.get(fork_node, []):
            chain = self._collect_branch_chain(
                branch_start, merge_name, successors
            )
            for name in chain:
                sn = node_state_names.get(name)
                if sn and sn in branch_state_names:
                    node_state_names.pop(name, None)

    @staticmethod
    def _build_adjacency(
        analysis: WorkflowAnalysis,
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Build predecessor and successor maps from CONNECTION edges."""
        predecessors: dict[str, list[str]] = {}
        successors: dict[str, list[str]] = {}
        for edge in analysis.dependency_edges:
            if edge.edge_type == "CONNECTION":
                predecessors.setdefault(edge.to_node, []).append(edge.from_node)
                successors.setdefault(edge.from_node, []).append(edge.to_node)
        return predecessors, successors

    @staticmethod
    def _find_fork_point(
        merge_name: str,
        incoming: list[str],
        predecessors: dict[str, list[str]],
    ) -> str | None:
        """Walk backwards from each incoming branch to find the common fork point.

        Returns the first common ancestor node of all incoming branches, or
        ``None`` if no common ancestor is found within a reasonable depth.
        """
        max_depth = 50

        def _ancestors(start: str) -> list[str]:
            """Return the ancestor chain from *start* going backwards."""
            chain: list[str] = [start]
            current = start
            for _ in range(max_depth):
                preds = predecessors.get(current, [])
                if not preds:
                    break
                current = preds[0]
                chain.append(current)
            return chain

        ancestor_chains = [_ancestors(node) for node in incoming]

        # Find the first node that appears in all chains
        first_chain_set = set(ancestor_chains[0])
        for ancestor in ancestor_chains[0]:
            if (
                ancestor in first_chain_set
                and all(ancestor in set(chain) for chain in ancestor_chains[1:])
            ):
                return ancestor
        return None

    @staticmethod
    def _collect_branch_chain(
        start: str,
        merge_name: str,
        successors: dict[str, list[str]],
    ) -> list[str]:
        """Collect a linear chain of nodes from *start* to just before *merge_name*."""
        chain: list[str] = []
        current = start
        visited: set[str] = set()
        max_depth = 100
        for _ in range(max_depth):
            if current == merge_name:
                break
            if current in visited:
                break
            visited.add(current)
            chain.append(current)
            nexts = successors.get(current, [])
            if not nexts:
                break
            current = nexts[0]
        return chain

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
