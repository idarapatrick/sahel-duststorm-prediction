"""Reproducible dual-encoder architectures used in SahelWatch experiments."""

from __future__ import annotations

from typing import Literal

import torch
from torch import nn

ATMOSPHERIC_FEATURES = 7
SURFACE_FEATURES = 7


class FocalLoss(nn.Module):
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        loss = nn.functional.binary_cross_entropy_with_logits(
            logits, targets, reduction="none"
        )
        probabilities = torch.sigmoid(logits)
        target_probability = probabilities * targets + (1 - probabilities) * (1 - targets)
        target_alpha = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        return (target_alpha * (1 - target_probability) ** self.gamma * loss).mean()


class CrossModalAttention(nn.Module):
    def __init__(self, embedding_dim: int = 256, heads: int = 8, dropout: float = 0.1):
        super().__init__()
        if embedding_dim % heads:
            raise ValueError("embedding_dim must be divisible by heads")
        self.surface_to_atmosphere = nn.MultiheadAttention(
            embedding_dim, heads, dropout=dropout, batch_first=True
        )
        self.atmosphere_to_surface = nn.MultiheadAttention(
            embedding_dim, heads, dropout=dropout, batch_first=True
        )
        self.surface_norm = nn.LayerNorm(embedding_dim)
        self.atmosphere_norm = nn.LayerNorm(embedding_dim)

    def forward(
        self, surface: torch.Tensor, atmosphere: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        surface_token = surface.unsqueeze(1)
        atmosphere_token = atmosphere.unsqueeze(1)
        surface_update, _ = self.surface_to_atmosphere(
            surface_token, atmosphere_token, atmosphere_token
        )
        atmosphere_update, _ = self.atmosphere_to_surface(
            atmosphere_token, surface_token, surface_token
        )
        return (
            self.surface_norm(surface_update.squeeze(1) + surface),
            self.atmosphere_norm(atmosphere_update.squeeze(1) + atmosphere),
        )


class CNNEncoder(nn.Module):
    def __init__(self, input_channels: int = ATMOSPHERIC_FEATURES, embedding_dim: int = 256, dropout: float = 0.24):
        super().__init__()
        self.network = nn.Sequential(
            nn.Conv1d(input_channels, 64, kernel_size=7, padding=3),
            nn.ReLU(),
            nn.BatchNorm1d(64),
            nn.Dropout(dropout),
            nn.Conv1d(64, 128, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(dropout),
            nn.Conv1d(128, embedding_dim, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.norm = nn.LayerNorm(embedding_dim)

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        return self.norm(self.network(sequence.transpose(1, 2)).squeeze(-1))


class RecurrentEncoder(nn.Module):
    def __init__(
        self,
        kind: Literal["lstm", "gru"],
        input_dim: int = ATMOSPHERIC_FEATURES,
        embedding_dim: int = 256,
        hidden_dim: int = 128,
        layers: int = 2,
        dropout: float = 0.24,
    ):
        super().__init__()
        recurrent_class = nn.LSTM if kind == "lstm" else nn.GRU
        self.kind = kind
        self.recurrent = recurrent_class(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if layers > 1 else 0.0,
        )
        self.projection = nn.Linear(hidden_dim * 2, embedding_dim)
        self.norm = nn.LayerNorm(embedding_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        result = self.recurrent(sequence)
        hidden = result[1][0] if self.kind == "lstm" else result[1]
        bidirectional = torch.cat([hidden[-2], hidden[-1]], dim=-1)
        return self.norm(self.projection(self.dropout(bidirectional)))


class SurfaceEncoder(nn.Module):
    def __init__(self, input_dim: int = SURFACE_FEATURES, embedding_dim: int = 256, dropout: float = 0.24):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, embedding_dim),
            nn.LayerNorm(embedding_dim),
        )

    def forward(self, surface: torch.Tensor) -> torch.Tensor:
        return self.network(surface)


class PredictionHead(nn.Module):
    def __init__(self, input_dim: int = 512, dropout: float = 0.54):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 1),
        )

    def forward(self, embedding: torch.Tensor) -> torch.Tensor:
        return self.network(embedding).squeeze(-1)


class DustModel(nn.Module):
    """Configurable atmospheric and surface dual encoder.

    Input shapes are ``(batch, 72, 7)`` for atmospheric sequences and
    ``(batch, 7)`` for surface vectors. The forward pass returns one logit per
    sample. A probability is obtained with ``torch.sigmoid``.
    """

    def __init__(
        self,
        encoder: Literal["cnn", "lstm", "gru"] = "lstm",
        fusion: Literal["concat", "attention"] = "attention",
        embedding_dim: int = 256,
        dropout: float = 0.24,
        heads: int = 8,
    ):
        super().__init__()
        if encoder == "cnn":
            self.atmospheric_encoder = CNNEncoder(
                embedding_dim=embedding_dim, dropout=dropout
            )
        elif encoder in {"lstm", "gru"}:
            self.atmospheric_encoder = RecurrentEncoder(
                encoder, embedding_dim=embedding_dim, dropout=dropout
            )
        else:
            raise ValueError(f"Unsupported encoder: {encoder}")
        if fusion not in {"concat", "attention"}:
            raise ValueError(f"Unsupported fusion: {fusion}")

        self.surface_encoder = SurfaceEncoder(
            embedding_dim=embedding_dim, dropout=dropout
        )
        self.fusion = fusion
        self.cross_attention = (
            CrossModalAttention(embedding_dim, heads)
            if fusion == "attention"
            else None
        )
        self.head = PredictionHead(embedding_dim * 2)

    def forward(self, atmosphere: torch.Tensor, surface: torch.Tensor) -> torch.Tensor:
        atmospheric_embedding = self.atmospheric_encoder(atmosphere)
        surface_embedding = self.surface_encoder(surface)
        if self.cross_attention is not None:
            surface_embedding, atmospheric_embedding = self.cross_attention(
                surface_embedding, atmospheric_embedding
            )
        fused = torch.cat([surface_embedding, atmospheric_embedding], dim=-1)
        return self.head(fused)


def build_best_reported_model() -> DustModel:
    """Construct the LSTM and cross-modal-attention experiment configuration."""
    return DustModel(
        encoder="lstm",
        fusion="attention",
        embedding_dim=256,
        dropout=0.24,
        heads=8,
    )
