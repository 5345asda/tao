"""训练工具函数。"""

from __future__ import annotations

import random
from typing import Sequence, Tuple

import numpy as np
import torch


def set_seed(seed: int = 42) -> None:
    """设置随机种子，确保实验可复现。"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


class AverageMeter:
    """记录并计算平均值。"""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.val = 0.0
        self.avg = 0.0
        self.sum = 0.0
        self.count = 0

    def update(self, val: float, n: int = 1) -> None:
        self.val = float(val)
        self.sum += float(val) * n
        self.count += n
        self.avg = self.sum / self.count if self.count > 0 else 0.0


def accuracy_topk(
    logits: torch.Tensor,
    targets: torch.Tensor,
    topk: Sequence[int] = (1, 3),
) -> Tuple[float, ...]:
    """计算多标签容差场景下 top-k 准确率。"""
    with torch.no_grad():
        maxk = max(topk)
        _, pred = logits.topk(maxk, dim=1, largest=True, sorted=True)
        target_mask = targets > 0.5

        results = []
        for k in topk:
            pred_k = pred[:, :k]
            hit = target_mask.gather(dim=1, index=pred_k).any(dim=1).float()
            results.append(float(hit.mean().item() * 100.0))
        return tuple(results)


def angle_error(
    preds_or_logits: torch.Tensor,
    targets: torch.Tensor,
    num_classes: int = 100,
) -> float:
    """计算平均角度误差(度)。"""
    with torch.no_grad():
        if preds_or_logits.ndim == 2:
            pred_indices = preds_or_logits.argmax(dim=1)
        else:
            pred_indices = preds_or_logits.long().view(-1)

        target_mask = targets > 0.5
        errors_deg = []
        step_deg = 360.0 / float(num_classes)

        for i in range(pred_indices.shape[0]):
            valid_labels = torch.nonzero(target_mask[i], as_tuple=False).flatten()
            if valid_labels.numel() == 0:
                continue
            pred_label = pred_indices[i].item()
            diff = torch.abs(valid_labels - pred_label)
            circular_diff = torch.minimum(diff, num_classes - diff)
            min_steps = circular_diff.min().item()
            errors_deg.append(min_steps * step_deg)

        if not errors_deg:
            return float("nan")
        return float(np.mean(errors_deg))
