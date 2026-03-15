#!/usr/bin/env python3
"""CDK app entry point for the Phaeton deployment."""

import aws_cdk as cdk

from stacks.ai_agent_stack import AiAgentStack
from stacks.orchestration_stack import OrchestrationStack
from stacks.packager_stack import PackagerStack
from stacks.release_parser_stack import ReleaseParserStack
from stacks.translation_engine_stack import TranslationEngineStack
from stacks.workflow_analyzer_stack import WorkflowAnalyzerStack

app = cdk.App()

release_parser = ReleaseParserStack(app, "PhaetonReleaseParser")
workflow_analyzer = WorkflowAnalyzerStack(app, "PhaetonWorkflowAnalyzer")
ai_agent = AiAgentStack(app, "PhaetonAiAgent")
translation_engine = TranslationEngineStack(
    app,
    "PhaetonTranslationEngine",
    ai_agent_function=ai_agent.function,
)
packager = PackagerStack(app, "PhaetonPackager")

OrchestrationStack(
    app,
    "PhaetonOrchestration",
    analyzer_function=workflow_analyzer.function,
    translator_function=translation_engine.function,
    packager_function=packager.function,
)

app.synth()
