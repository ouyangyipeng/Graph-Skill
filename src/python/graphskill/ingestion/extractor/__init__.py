"""
GraphSkill Ingestion Extractor Module.

This module provides topology extraction for skill relationships:
- TopologyExtractor: LLM-based topology inference
- RelationResolver: Resolves conflicts between declared and inferred relations
"""

from graphskill.ingestion.extractor.topology_extractor import (
    TopologyExtractor,
    TopologyInferenceResult,
    InferredRelation,
)
from graphskill.ingestion.extractor.relation_resolver import (
    RelationResolver,
    ResolvedTopology,
    ResolutionStrategy,
)
from graphskill.ingestion.extractor.prompts import (
    SYSTEM_PROMPT,
    build_inference_prompt,
    build_batch_inference_prompt,
)

__all__ = [
    "TopologyExtractor",
    "TopologyInferenceResult",
    "InferredRelation",
    "RelationResolver",
    "ResolvedTopology",
    "ResolutionStrategy",
    "SYSTEM_PROMPT",
    "build_inference_prompt",
    "build_batch_inference_prompt",
]