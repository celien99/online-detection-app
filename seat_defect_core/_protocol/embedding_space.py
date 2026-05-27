from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingSpaceContract:
    """Representation standard — all modules reference this, not implementations.

    This is the "law" that all embedding producers and consumers must obey.
    It does NOT define HOW to produce embeddings, only WHAT they must look like.
    """

    dim: int = 384
    norm: str = "l2"
    similarity: str = "cosine"
    target_geometry: str = "dinov2_vits14"
    schema_version: str = "1.0.0"

    def validate(self, vector: list[float]) -> bool:
        """Check if a vector satisfies this contract."""
        if len(vector) != self.dim:
            return False
        if self.norm == "l2":
            import math

            norm_val = math.sqrt(sum(v * v for v in vector))
            if abs(norm_val - 1.0) > 0.01:
                return False
        return True


@dataclass
class UnifiedEmbedding:
    """A concrete vector satisfying EmbeddingSpaceContract."""

    vector: list[float]  # 384-dim, L2 normalized
    contract_version: str  # "1.0.0"
    source: str  # "efficientad_projected" | "dinov2"

    def __post_init__(self):
        assert len(self.vector) == 384, f"Expected 384-dim, got {len(self.vector)}"
