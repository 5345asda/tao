"""导出 ONNX 并校验一致性。"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch

import config
from model import create_model


def parse_args() -> argparse.Namespace:
    """解析导出参数。"""
    parser = argparse.ArgumentParser(description="导出 EfficientNet-B3 到 ONNX")
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=str(Path(config.CHECKPOINT_DIR) / "best_model.pth"),
        help="最佳模型权重路径",
    )
    parser.add_argument(
        "--onnx_path",
        type=str,
        default=str(Path(config.ONNX_DIR) / "captcha_effnet_b3.onnx"),
        help="导出的 ONNX 文件路径",
    )
    parser.add_argument("--img_size", type=int, default=config.IMG_SIZE)
    parser.add_argument("--num_classes", type=int, default=config.NUM_CLASSES)
    parser.add_argument("--device", type=str, default="cpu")
    return parser.parse_args()


def load_state_dict(ckpt_path: Path, device: torch.device) -> dict:
    """加载 checkpoint 并提取 state_dict。"""
    checkpoint = torch.load(str(ckpt_path), map_location=device)
    if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        return checkpoint["model_state_dict"]
    return checkpoint


def main() -> None:
    args = parse_args()
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    ckpt_path = Path(args.checkpoint)
    onnx_path = Path(args.onnx_path)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)

    if not ckpt_path.exists():
        raise FileNotFoundError(f"checkpoint 不存在: {ckpt_path}")

    model = create_model(num_classes=args.num_classes, dropout=0.3).to(device)
    state_dict = load_state_dict(ckpt_path=ckpt_path, device=device)
    model.load_state_dict(state_dict)
    model.eval()

    dummy_input = torch.randn(1, 3, args.img_size, args.img_size, device=device)
    with torch.no_grad():
        torch_out = model(dummy_input).cpu().numpy()

    torch.onnx.export(
        model,
        dummy_input,
        str(onnx_path),
        export_params=True,
        opset_version=11,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={"input": {0: "batch_size"}, "logits": {0: "batch_size"}},
    )
    print(f"ONNX 导出完成: {onnx_path}")

    # 使用 onnxruntime 校验输出一致性
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    ort_out = session.run(None, {"input": dummy_input.cpu().numpy().astype(np.float32)})[0]
    max_abs_diff = float(np.max(np.abs(torch_out - ort_out)))
    is_close = np.allclose(torch_out, ort_out, rtol=1e-3, atol=1e-4)
    print(f"ONNX 校验: is_close={is_close}, max_abs_diff={max_abs_diff:.6f}")
    if not is_close:
        raise RuntimeError("ONNX 导出校验失败，PyTorch 与 ONNX 推理结果差异过大。")


if __name__ == "__main__":
    main()
