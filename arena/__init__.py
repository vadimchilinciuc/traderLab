"""Arena: orchestratore delle repliche, verbale, risk officer, regressione."""

from arena.config import (
    DEFAULT_MODEL_STRING,
    DEFAULT_REPLICA_IDS,
    ArenaConfig,
    ContextFiles,
    all_tool_schemas,
    all_tool_schemas_sha,
    build_freeze_manifest,
    load_context,
)
from arena.llm_client import (
    AnthropicTraderClient,
    BudgetExceeded,
    CallBudget,
    LLMResponse,
    MockLLM,
)
from arena.regression import (
    SAMPLES_PER_SNAPSHOT,
    Baseline,
    BehavioralRegressionSuite,
    DecisionSnapshotRef,
    DriftReport,
    DriftThresholds,
    DriftVerdict,
    ThresholdDerivation,
    ThresholdRuleChanged,
    ThresholdsNotSet,
    threshold_rule_fingerprint,
    thresholds_from_baseline,
)
from arena.risk_officer import PortfolioState, RiskConfig, RiskOfficer
from arena.runner import AssetOutcome, DailyRunner, DailyRunResult
from arena.shadow_fill import compute_shadow_fill
from arena.verbale import (
    SUBMIT_DECISION_SCHEMA,
    MalformedReason,
    ParsedVerbale,
    parse_verbale,
)

__all__ = [
    "DEFAULT_MODEL_STRING",
    "DEFAULT_REPLICA_IDS",
    "SAMPLES_PER_SNAPSHOT",
    "SUBMIT_DECISION_SCHEMA",
    "AnthropicTraderClient",
    "ArenaConfig",
    "AssetOutcome",
    "Baseline",
    "BehavioralRegressionSuite",
    "DecisionSnapshotRef",
    "DriftReport",
    "DriftThresholds",
    "DriftVerdict",
    "ThresholdDerivation",
    "ThresholdRuleChanged",
    "ThresholdsNotSet",
    "threshold_rule_fingerprint",
    "thresholds_from_baseline",
    "BudgetExceeded",
    "CallBudget",
    "ContextFiles",
    "DailyRunResult",
    "DailyRunner",
    "LLMResponse",
    "MalformedReason",
    "MockLLM",
    "ParsedVerbale",
    "PortfolioState",
    "RiskConfig",
    "RiskOfficer",
    "all_tool_schemas",
    "all_tool_schemas_sha",
    "build_freeze_manifest",
    "compute_shadow_fill",
    "load_context",
    "parse_verbale",
]
