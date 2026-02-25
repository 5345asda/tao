"""验证码角度预测模型封装。"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Dict, Union

import numpy as np
import onnxruntime as ort
from PIL import Image
from torchvision import transforms

from config import IMG_SIZE, IMAGENET_MEAN, IMAGENET_STD, MODEL_PATH, NUM_CLASSES


def stable_softmax(x: np.ndarray) -> np.ndarray:
    """数值稳定的 softmax。"""
    x = x - np.max(x)
    exp_x = np.exp(x)
    return exp_x / np.sum(exp_x)


class CaptchaModel:
    """基于 ONNXRuntime 的验证码角度预测器。"""

    def __init__(
        self,
        model_path: str = MODEL_PATH,
        img_size: int = IMG_SIZE,
        num_classes: int = NUM_CLASSES,
    ) -> None:
        model_file = Path(model_path)
        if not model_file.exists():
            raise FileNotFoundError(f"ONNX 模型不存在: {model_path}")

        available = ort.get_available_providers()
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        providers = [p for p in providers if p in available]
        if not providers:
            providers = ["CPUExecutionProvider"]

        self.session = ort.InferenceSession(str(model_file), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.num_classes = int(num_classes)
        self.transform = transforms.Compose(
            [
                transforms.Resize((img_size, img_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ]
        )

    def _predict_from_image(self, image: Image.Image) -> Dict[str, float]:
        """对已打开图片执行一次预测。"""
        image = image.convert("RGB")
        tensor = self.transform(image).unsqueeze(0)
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

    def predict_from_bytes(self, img_data: bytes) -> Dict[str, float]:
        """从图片字节数据预测类别、角度与置信度。"""
        with Image.open(BytesIO(img_data)) as image:
            return self._predict_from_image(image)

    def predict(self, image: Union[str, Path]) -> Dict[str, float]:
        """从图片路径预测类别、角度与置信度。"""
        with Image.open(image) as img:
            return self._predict_from_image(img)


# 为兼容参考实现命名提供别名
ONNXCaptchaPredictor = CaptchaModel
