"""
Phase 3: Model definitions.

1. FraudDetector  -- DistilBERT + velocity -> dropout -> linear (class-weighted loss)
2. FusionHead     -- MLP head trained on top of frozen embeddings + velocity (after SMOTE)
"""
import torch
import torch.nn as nn
from transformers import DistilBertModel


class FraudDetector(nn.Module):
    """
    Full fine-tuned model.
    input_ids + attention_mask -> DistilBERT -> [CLS] (768)
    concat with velocity (1) -> dropout -> linear -> 2 logits
    """

    def __init__(self, dropout_p: float = 0.3):
        super().__init__()
        self.bert = DistilBertModel.from_pretrained("distilbert-base-uncased")
        hidden = 768 + 1  # [CLS] + velocity scalar
        self.dropout = nn.Dropout(dropout_p)
        self.classifier = nn.Linear(hidden, 2)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        velocity: torch.Tensor,
    ) -> torch.Tensor:
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls = outputs.last_hidden_state[:, 0, :]  # (B, 768)
        # velocity shape: (B,) -> (B, 1)
        if velocity.dim() == 1:
            velocity = velocity.unsqueeze(1)
        combined = torch.cat([cls, velocity.float()], dim=1)  # (B, 769)
        return self.classifier(self.dropout(combined))


class FusionHead(nn.Module):
    """
    Lightweight MLP fusion head trained on top of frozen embeddings.
    Input: embedding (768) + velocity (1) = 769 dims
    """

    def __init__(self, input_dim: int = 769, hidden_dim: int = 256, dropout_p: float = 0.3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout_p),
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout_p),
            nn.Linear(64, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)
