#!/usr/bin/env python3
"""CDK app entry point for the Phaeton deployment."""

import aws_cdk as cdk

from stacks.orchestration_stack import OrchestrationStack
from stacks.packager_stack import PackagerStack
from stacks.release_parser_stack import ReleaseParserStack
from stacks.translation_engine_stack import TranslationEngineStack
from stacks.workflow_analyzer_stack import WorkflowAnalyzerStack

app = cdk.App()

release_parser = ReleaseParserStack(app, "PhaetonReleaseParser")
workflow_analyzer = WorkflowAnalyzerStack(app, "PhaetonWorkflowAnalyzer")
translation_engine = TranslationEngineStack(app, "PhaetonTranslationEngine")
packager = PackagerStack(app, "PhaetonPackager")

OrchestrationStack(
    app,
    "PhaetonOrchestration",
    analyzer_function=workflow_analyzer.function,
    translator_function=translation_engine.function,
    packager_function=packager.function,
)

app.synth()
