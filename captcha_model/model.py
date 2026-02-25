"""模型定义。"""

from efficientnet_pytorch import EfficientNet
from torch import nn


def create_model(num_classes: int = 100, dropout: float = 0.3) -> EfficientNet:
    """创建 EfficientNet-B3 并替换分类头。"""
    model = EfficientNet.from_pretrained("efficientnet-b3")
    in_features = model._fc.in_features
    # 使用 Dropout + Linear 作为新的分类层
    model._fc = nn.Sequential(nn.Dropout(p=dropout), nn.Linear(in_features, num_classes))
    return model
