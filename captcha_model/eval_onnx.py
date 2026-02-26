"""验证 ONNX 模型在数据集上的识别成功率。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from tqdm import tqdm

from dataset import parse_tolerance_labels, IMAGE_EXTENSIONS
from inference import ONNXCaptchaPredictor

# 默认配置
DEFAULT_MODEL = Path(__file__).parent / "onnx" / "captcha_effnet_b3.onnx"
DEFAULT_DATA = Path(__file__).parent.parent / "data" / "collected"


def evaluate(
    predictor: ONNXCaptchaPredictor,
    data_root: Path,
    num_classes: int = 100,
    tolerance_degrees: float = 0.0,
) -> dict:
    """评估模型在数据集上的准确率。

    Args:
        predictor: ONNX 预测器
        data_root: 数据根目录
        num_classes: 分类数
        tolerance_degrees: 额外的角度容差（度）

    Returns:
        统计结果字典
    """
    total = 0
    correct = 0
    errors = []

    # 计算额外容差对应的 class 数量
    tolerance_classes = int(tolerance_degrees / (360.0 / num_classes))

    # 遍历所有标签目录
    label_dirs = sorted([d for d in data_root.iterdir() if d.is_dir()])

    for label_dir in tqdm(label_dirs, desc="评估中", unit="dir"):
        # 解析容差标签
        true_labels = parse_tolerance_labels(label_dir.name, num_classes=num_classes)
        if not true_labels:
            continue

        # 扩展容差范围
        if tolerance_classes > 0:
            expanded_labels = set()
            for label in true_labels:
                for offset in range(-tolerance_classes, tolerance_classes + 1):
                    expanded_labels.add((label + offset) % num_classes)
            true_labels = list(expanded_labels)

        # 遍历目录中的所有图片
        for img_path in label_dir.rglob("*"):
            if not img_path.is_file():
                continue
            if img_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            total += 1
            try:
                result = predictor.predict(str(img_path))
                pred_class = result["class_index"]

                if pred_class in true_labels:
                    correct += 1
                else:
                    if len(errors) < 20:  # 只记录前 20 个错误
                        errors.append({
                            "image": str(img_path),
                            "true_labels": true_labels,
                            "pred_class": pred_class,
                            "pred_angle": result["angle"],
                            "confidence": result["confidence"],
                        })
            except Exception as e:
                if len(errors) < 20:
                    errors.append({
                        "image": str(img_path),
                        "error": str(e),
                    })

    accuracy = correct / total if total > 0 else 0.0
    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="验证 ONNX 模型识别成功率")
    parser.add_argument(
        "--model",
        type=str,
        default=str(DEFAULT_MODEL),
        help="ONNX 模型路径",
    )
    parser.add_argument(
        "--data",
        type=str,
        default=str(DEFAULT_DATA),
        help="数据集目录",
    )
    parser.add_argument(
        "--num_classes",
        type=int,
        default=100,
        help="分类数",
    )
    parser.add_argument(
        "--img_size",
        type=int,
        default=224,
        help="输入图片尺寸",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.0,
        help="额外角度容差（度），如 3.6 表示额外 +/-1 个 class",
    )
    args = parser.parse_args()

    # 检查路径
    model_path = Path(args.model)
    data_path = Path(args.data)

    if not model_path.exists():
        print(f"错误：模型文件不存在: {model_path}")
        sys.exit(1)

    if not data_path.exists():
        print(f"错误：数据目录不存在: {data_path}")
        sys.exit(1)

    print(f"模型: {model_path}")
    print(f"数据: {data_path}")
    print(f"分类数: {args.num_classes}")
    print(f"图片尺寸: {args.img_size}")
    print(f"额外容差: {args.tolerance}°")
    print("-" * 50)

    # 加载模型
    print("加载模型...")
    predictor = ONNXCaptchaPredictor(
        onnx_path=str(model_path),
        img_size=args.img_size,
        num_classes=args.num_classes,
    )

    # 评估
    print("开始评估...")
    results = evaluate(
        predictor=predictor,
        data_root=data_path,
        num_classes=args.num_classes,
        tolerance_degrees=args.tolerance,
    )

    # 输出结果
    print("\n" + "=" * 50)
    print("评估结果")
    print("=" * 50)
    print(f"总图片数: {results['total']}")
    print(f"正确数: {results['correct']}")
    print(f"准确率: {results['accuracy']:.4f} ({results['accuracy']*100:.2f}%)")

    if results["errors"]:
        print(f"\n前 {len(results['errors'])} 个错误样本:")
        for i, err in enumerate(results["errors"], 1):
            if "error" in err:
                print(f"  {i}. {err['image']} - 错误: {err['error']}")
            else:
                print(f"  {i}. {Path(err['image']).name}")
                print(f"     真实标签: {err['true_labels']}")
                print(f"     预测: class={err['pred_class']}, angle={err['pred_angle']:.1f}°, conf={err['confidence']:.4f}")


if __name__ == "__main__":
    main()
