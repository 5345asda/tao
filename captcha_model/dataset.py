"""数据集与数据加载逻辑。"""

from __future__ import annotations

import random
from pathlib import Path
from typing import List, Sequence, Tuple

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def parse_tolerance_labels(dir_name: str, num_classes: int = 100) -> List[int]:
    """解析目录名中的容差标签。示例: '14_15_16_17_18_19_20' -> [14, 15, ..., 20]"""
    labels: List[int] = []
    for token in dir_name.split("_"):
        token = token.strip()
        if not token:
            continue
        if not token.isdigit():
            continue
        label = int(token)
        if 0 <= label < num_classes:
            labels.append(label)
    return sorted(set(labels))


def labels_to_multihot(labels: Sequence[int], num_classes: int = 100) -> torch.Tensor:
    """将标签列表转为多标签 one-hot 向量。"""
    target = torch.zeros(num_classes, dtype=torch.float32)
    if labels:
        target[list(labels)] = 1.0
    return target


def build_transforms(img_size: int = 224, train: bool = True) -> transforms.Compose:
    """构建训练/验证推理变换。"""
    transform_list = [transforms.Resize((img_size, img_size))]
    if train:
        # 训练增强: 颜色抖动
        transform_list.append(
            transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.2, hue=0.05)
        )
    transform_list.extend(
        [
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )
    if train:
        # 随机擦除放在 ToTensor 后
        transform_list.append(
            transforms.RandomErasing(
                p=0.25,
                scale=(0.02, 0.12),
                ratio=(0.3, 3.3),
                value="random",
            )
        )
    return transforms.Compose(transform_list)


def scan_samples(data_root: str, num_classes: int = 100) -> List[Tuple[str, List[int]]]:
    """扫描数据目录，返回 (图片路径, 容差标签列表)。"""
    root = Path(data_root)
    if not root.exists():
        raise FileNotFoundError(f"数据目录不存在: {data_root}")

    samples: List[Tuple[str, List[int]]] = []
    for label_dir in sorted(root.iterdir()):
        if not label_dir.is_dir():
            continue
        labels = parse_tolerance_labels(label_dir.name, num_classes=num_classes)
        if not labels:
            continue

        for file_path in label_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            samples.append((str(file_path), labels))
    return samples


def split_samples(
    samples: Sequence[Tuple[str, List[int]]],
    seed: int = 42,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
) -> Tuple[List[Tuple[str, List[int]]], List[Tuple[str, List[int]]], List[Tuple[str, List[int]]]]:
    """按 80/10/10 比例切分数据。"""
    total = len(samples)
    if total == 0:
        return [], [], []

    indices = list(range(total))
    rng = random.Random(seed)
    rng.shuffle(indices)

    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)

    train_samples = [samples[i] for i in indices[:train_end]]
    val_samples = [samples[i] for i in indices[train_end:val_end]]
    test_samples = [samples[i] for i in indices[val_end:]]
    return train_samples, val_samples, test_samples


class CaptchaDataset(Dataset):
    """百度旋转验证码数据集。"""

    def __init__(
        self,
        samples: Sequence[Tuple[str, List[int]]],
        img_size: int = 224,
        num_classes: int = 100,
        train: bool = True,
    ) -> None:
        self.samples = list(samples)
        self.num_classes = num_classes
        self.transform = build_transforms(img_size=img_size, train=train)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> Tuple[torch.Tensor, torch.Tensor]:
        img_path, tolerance_labels = self.samples[index]
        with Image.open(img_path) as img:
            img = img.convert("RGB")
            image_tensor = self.transform(img)

        target = labels_to_multihot(tolerance_labels, num_classes=self.num_classes)
        return image_tensor, target


def create_dataloaders(
    data_root: str,
    batch_size: int = 64,
    img_size: int = 224,
    num_classes: int = 100,
    num_workers: int = 8,
    seed: int = 42,
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """创建 train/val/test 三个 DataLoader。"""
    samples = scan_samples(data_root=data_root, num_classes=num_classes)
    train_samples, val_samples, test_samples = split_samples(samples=samples, seed=seed)

    if len(train_samples) == 0 or len(val_samples) == 0:
        raise RuntimeError("切分后的训练或验证集为空，请检查数据目录结构与标签目录命名。")

    train_dataset = CaptchaDataset(
        samples=train_samples,
        img_size=img_size,
        num_classes=num_classes,
        train=True,
    )
    val_dataset = CaptchaDataset(
        samples=val_samples,
        img_size=img_size,
        num_classes=num_classes,
        train=False,
    )
    test_dataset = CaptchaDataset(
        samples=test_samples,
        img_size=img_size,
        num_classes=num_classes,
        train=False,
    )

    common_kwargs = {
        "batch_size": batch_size,
        "num_workers": num_workers,
        "pin_memory": torch.cuda.is_available(),
        "persistent_workers": num_workers > 0,
    }

    train_loader = DataLoader(train_dataset, shuffle=True, drop_last=False, **common_kwargs)
    val_loader = DataLoader(val_dataset, shuffle=False, drop_last=False, **common_kwargs)
    test_loader = DataLoader(test_dataset, shuffle=False, drop_last=False, **common_kwargs)
    return train_loader, val_loader, test_loader
