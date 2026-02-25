"""ONNX 推理脚本。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import numpy as np
import onnxruntime as ort
from PIL import Image
from torchvision import transforms

import config

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def stable_softmax(x: np.ndarray) -> np.ndarray:
    """数值稳定的 softmax。"""
    x = x - np.max(x)
    exp_x = np.exp(x)
    return exp_x / np.sum(exp_x)


class ONNXCaptchaPredictor:
    """基于 ONNXRuntime 的验证码角度预测器。"""

    def __init__(self, onnx_path: str, img_size: int = 224, num_classes: int = 100) -> None:
        model_path = Path(onnx_path)
        if not model_path.exists():
            raise FileNotFoundError(f"ONNX 模型不存在: {onnx_path}")

        available = ort.get_available_providers()
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        providers = [p for p in providers if p in available]
        if not providers:
            providers = ["CPUExecutionProvider"]

        self.session = ort.InferenceSession(str(model_path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.num_classes = num_classes
        self.transform = transforms.Compose(
            [
                transforms.Resize((img_size, img_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ]
        )

    def preprocess(self, image_path: str) -> np.ndarray:
        """读取并预处理图片。"""
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            tensor = self.transform(img).unsqueeze(0)
        return tensor.numpy().astype(np.float32)

    def predict_from_bytes(self, img_data: bytes) -> Dict[str, float]:
        """从字节数据预测角度

        Args:
            img_data: 图片二进制数据

        Returns:
            {"class_index": int, "angle": float, "confidence": float}
        """
        from io import BytesIO

        with Image.open(BytesIO(img_data)) as img:
            img = img.convert("RGB")
            tensor = self.transform(img).unsqueeze(0)
        input_tensor = tensor.numpy().astype(np.float32)
        logits = self.session.run(None, {self.input_name: input_tensor})[0][0]
        probs = stable_softmax(logits)
        pred_idx = int(np.argmax(probs))
        confidence = float(probs[pred_idx])
        angle = pred_idx * (360.0 / float(self.num_classes))
        return {
            "class_index": pred_idx,
            "angle": angle,
            "confidence": confidence,
        }

    def predict(self, image_path: str) -> Dict[str, float]:
        """返回预测角度与置信度。"""
        input_tensor = self.preprocess(image_path)
        logits = self.session.run(None, {self.input_name: input_tensor})[0][0]

        probs = stable_softmax(logits)
        pred_idx = int(np.argmax(probs))
        confidence = float(probs[pred_idx])
        angle = pred_idx * (360.0 / float(self.num_classes))
        return {
            "class_index": pred_idx,
            "angle": angle,
            "confidence": confidence,
        }


def parse_args() -> argparse.Namespace:
    """解析推理参数。"""
    parser = argparse.ArgumentParser(description="ONNX 百度旋转验证码推理")
    parser.add_argument(
        "--model",
        type=str,
        default=str(Path(config.ONNX_DIR) / "captcha_effnet_b3.onnx"),
        help="ONNX 模型路径",
    )
    parser.add_argument("--image", type=str, required=True, help="待预测图片路径")
    parser.add_argument("--img_size", type=int, default=config.IMG_SIZE)
    parser.add_argument("--num_classes", type=int, default=config.NUM_CLASSES)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predictor = ONNXCaptchaPredictor(
        onnx_path=args.model,
        img_size=args.img_size,
        num_classes=args.num_classes,
    )
    result = predictor.predict(args.image)
    print(f"预测类: {result['class_index']}")
    print(f"预测角度: {result['angle']:.2f}°")
    print(f"置信度: {result['confidence']:.4f}")


if __name__ == "__main__":
    main()
