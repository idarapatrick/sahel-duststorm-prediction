"""Three-head daily-resolution extension of the shared dual encoder."""

import torch
from torch import nn


class DailyMultiHorizonHeads(nn.Module):
    """Attach to the shared cross-modal embedding, not raw features."""

    def __init__(self, embedding_dim: int, dropout: float = 0.2):
        super().__init__()
        self.heads = nn.ModuleDict({
            name: nn.Sequential(
                nn.LayerNorm(embedding_dim),
                nn.Dropout(dropout),
                nn.Linear(embedding_dim, 1),
            )
            for name in ("day_0", "day_1", "day_2")
        })

    def forward(self, shared_embedding: torch.Tensor) -> dict[str, torch.Tensor]:
        return {
            name: head(shared_embedding).squeeze(-1)
            for name, head in self.heads.items()
        }


def masked_three_head_loss(logits, targets, valid_mask, criterion):
    """Average only real daily labels; missing MODIS days contribute no loss."""
    losses = []
    for index, name in enumerate(("day_0", "day_1", "day_2")):
        mask = valid_mask[:, index]
        if mask.any():
            losses.append(criterion(logits[name][mask], targets[mask, index]))
    if not losses:
        raise ValueError("Batch contains no valid daily horizon labels")
    return torch.stack(losses).mean()
