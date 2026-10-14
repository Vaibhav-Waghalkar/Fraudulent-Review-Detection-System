"""
Phase 4: Export FusionHead + frozen DistilBERT to ONNX.

The ONNX model accepts:
  - input_ids       (int64)
  - attention_mask  (int64)
  - velocity        (float32)

And outputs a probability score (float32, shape [batch, 2]).
"""
import os
import sys
from pathlib import Path

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import argparse
import pickle

import numpy as np
import torch
import torch.nn as nn
from transformers import DistilBertModel

from ml.model import FusionHead, FraudDetector

DEVICE = torch.device("cpu")  # Export on CPU for portability


class FusionONNXWrapper(nn.Module):
    """
    Wraps DistilBERT + FusionHead into a single forward pass for ONNX export.
    """

    def __init__(self, bert: DistilBertModel, fusion: FusionHead):
        super().__init__()
        self.bert = bert
        self.fusion = fusion

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        velocity: torch.Tensor,
    ) -> torch.Tensor:
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls = outputs.last_hidden_state[:, 0, :]  # (B, 768)
        if velocity.dim() == 1:
            velocity = velocity.unsqueeze(1)
        combined = torch.cat([cls, velocity.float()], dim=1)  # (B, 769)
        logits = self.fusion(combined)
        return torch.softmax(logits, dim=1)  # (B, 2)


def export(
    model_dir: str = "models",
    output_path: str = "models/fusion_model.onnx",
) -> None:
    Path(model_dir).mkdir(exist_ok=True)

    # Load components
    bert = DistilBertModel.from_pretrained("distilbert-base-uncased")
    fusion = FusionHead(input_dim=769)

    # Load trained weights
    detector_ckpt = os.path.join(model_dir, "fraud_detector_best.pt")
    fusion_ckpt = os.path.join(model_dir, "fusion_head_best.pt")

    if os.path.exists(detector_ckpt):
        # Extract bert weights from FraudDetector
        detector_state = torch.load(detector_ckpt, map_location=DEVICE)
        bert_state = {
            k.replace("bert.", ""): v
            for k, v in detector_state.items()
            if k.startswith("bert.")
        }
        bert.load_state_dict(bert_state)
        print(f"Loaded BERT weights from {detector_ckpt}")
    else:
        print(f"WARNING: {detector_ckpt} not found. Using pretrained weights.")

    if os.path.exists(fusion_ckpt):
        fusion.load_state_dict(torch.load(fusion_ckpt, map_location=DEVICE))
        print(f"Loaded FusionHead weights from {fusion_ckpt}")
    else:
        print(f"WARNING: {fusion_ckpt} not found. Using random weights.")

    wrapper = FusionONNXWrapper(bert, fusion).to(DEVICE)
    wrapper.eval()

    # Dummy inputs (batch size 1)
    dummy_input_ids = torch.randint(0, 1000, (1, 128), dtype=torch.int64)
    dummy_attention_mask = torch.ones(1, 128, dtype=torch.int64)
    dummy_velocity = torch.tensor([0.5], dtype=torch.float32)

    print(f"Exporting ONNX model to {output_path}...")
    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            (dummy_input_ids, dummy_attention_mask, dummy_velocity),
            output_path,
            input_names=["input_ids", "attention_mask", "velocity"],
            output_names=["probabilities"],
            dynamic_axes={
                "input_ids": {0: "batch_size", 1: "sequence_length"},
                "attention_mask": {0: "batch_size", 1: "sequence_length"},
                "velocity": {0: "batch_size"},
                "probabilities": {0: "batch_size"},
            },
            opset_version=14,
            do_constant_folding=True,
        )
    print(f"Exported: {output_path}")

    # Verify output parity
    verify_parity(wrapper, output_path)


def verify_parity(
    torch_model: nn.Module,
    onnx_path: str,
    atol: float = 1e-4,
) -> None:
    import onnxruntime as ort

    print("\nVerifying output parity (PyTorch vs ONNX)...")
    session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

    # Test with batch sizes 1 and 4
    for batch_size in [1, 4]:
        input_ids = torch.randint(0, 1000, (batch_size, 64), dtype=torch.int64)
        attention_mask = torch.ones(batch_size, 64, dtype=torch.int64)
        velocity = torch.randn(batch_size, dtype=torch.float32)

        with torch.no_grad():
            pt_out = torch_model(input_ids, attention_mask, velocity).numpy()

        onnx_out = session.run(
            None,
            {
                "input_ids": input_ids.numpy(),
                "attention_mask": attention_mask.numpy(),
                "velocity": velocity.numpy(),
            },
        )[0]

        max_diff = np.abs(pt_out - onnx_out).max()
        status = "PASS" if max_diff < atol else "FAIL"
        print(f"  batch_size={batch_size}: max_diff={max_diff:.2e}  [{status}]")

    print("Parity check complete.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_dir", default="models")
    parser.add_argument("--output", default="models/fusion_model.onnx")
    args = parser.parse_args()
    export(model_dir=args.model_dir, output_path=args.output)
