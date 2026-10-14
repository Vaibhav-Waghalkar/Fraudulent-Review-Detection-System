"""
Phase 4: INT8 dynamic quantization of the ONNX model.
"""
import os
import argparse
from pathlib import Path


def quantize(
    input_path: str = "models/fusion_model.onnx",
    output_path: str = "models/fusion_model_quantized.onnx",
) -> None:
    from onnxruntime.quantization import quantize_dynamic, QuantType

    print(f"Quantizing {input_path} -> {output_path}")
    quantize_dynamic(
        model_input=input_path,
        model_output=output_path,
        weight_type=QuantType.QInt8,
    )

    size_before = os.path.getsize(input_path) / 1e6
    size_after = os.path.getsize(output_path) / 1e6
    print(f"Model size: {size_before:.1f} MB -> {size_after:.1f} MB  "
          f"({(1 - size_after/size_before)*100:.1f}% reduction)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="models/fusion_model.onnx")
    parser.add_argument("--output", default="models/fusion_model_quantized.onnx")
    args = parser.parse_args()
    quantize(input_path=args.input, output_path=args.output)
