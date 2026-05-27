from __future__ import annotations

from .canonical_proposal import CanonicalPatchProposal
from .embedding_space import EmbeddingSpaceContract, UnifiedEmbedding
from .entities import (
    AnomalyContext,
    BoundingBox,
    EfficientADFeatures,
    FilterResult,
    ImageRef,
    PatchProposal,
    ProposalMetadata,
    ROIContext,
)
from .serialization import (
    proposal_from_dict,
    proposal_to_dict,
    proposals_from_json,
    proposals_to_json,
)
from .types import FeatureRef, IsolationKeyStr, ProposalId

__all__ = [
    "AnomalyContext",
    "BoundingBox",
    "CanonicalPatchProposal",
    "EfficientADFeatures",
    "EmbeddingSpaceContract",
    "FeatureRef",
    "FilterResult",
    "ImageRef",
    "IsolationKeyStr",
    "PatchProposal",
    "ProposalId",
    "ProposalMetadata",
    "ROIContext",
    "UnifiedEmbedding",
    "proposal_from_dict",
    "proposal_to_dict",
    "proposals_from_json",
    "proposals_to_json",
]
