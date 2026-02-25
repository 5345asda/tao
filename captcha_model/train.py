"""训练脚本: EfficientNet-B3 旋转验证码识别。"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Dict, Optional

import torch
from torch import nn
from torch.cuda.amp import GradScaler, autocast
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

import config
from dataset import create_dataloaders
from model import create_model
from utils import AverageMeter, accuracy_topk, angle_error, set_seed


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="训练百度旋转验证码识别模型")
    parser.add_argument("--data_root", type=str, default=config.DATA_ROOT)
    parser.add_argument("--batch_size", type=int, default=config.BATCH_SIZE)
    parser.add_argument("--num_epochs", type=int, default=config.NUM_EPOCHS)
    parser.add_argument("--learning_rate", type=float, default=config.LEARNING_RATE)
    parser.add_argument("--weight_decay", type=float, default=config.WEIGHT_DECAY)
    parser.add_argument("--num_classes", type=int, default=config.NUM_CLASSES)
    parser.add_argument("--img_size", type=int, default=config.IMG_SIZE)
    parser.add_argument("--device", type=str, default=config.DEVICE)
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--num_workers", type=int, default=config.NUM_WORKERS)
    parser.add_argument("--checkpoint_dir", type=str, default=config.CHECKPOINT_DIR)
    parser.add_argument("--log_dir", type=str, default=config.LOG_DIR)
    parser.add_argument("--resume", type=str, default="", help="断点恢复的 checkpoint 路径")
    parser.add_argument("--early_stop_patience", type=int, default=5)
    return parser.parse_args()


def resolve_device(device_name: str) -> torch.device:
    """根据环境解析设备。"""
    if device_name.startswith("cuda") and not torch.cuda.is_available():
        print("[警告] 未检测到 CUDA，自动切换到 CPU。")
        return torch.device("cpu")
    return torch.device(device_name)


def run_one_epoch(
    model: nn.Module,
    loader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    device: torch.device,
    num_classes: int,
    epoch: int,
    total_epochs: int,
    train_mode: bool,
    optimizer: Optional[torch.optim.Optimizer] = None,
    scaler: Optional[GradScaler] = None,
) -> Dict[str, float]:
    """执行一个 epoch（训练或验证/测试）。"""
    if train_mode and optimizer is None:
        raise ValueError("训练模式下必须提供 optimizer")

    model.train(mode=train_mode)
    loss_meter = AverageMeter()
    top1_meter = AverageMeter()
    top3_meter = AverageMeter()
    angle_meter = AverageMeter()
    use_amp = scaler is not None and device.type == "cuda"

    desc = f"{'Train' if train_mode else 'Eval '} [{epoch + 1}/{total_epochs}]"
    pbar = tqdm(loader, desc=desc, ncols=130)
    for images, targets in pbar:
        images = images.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        batch_size = images.size(0)

        with torch.set_grad_enabled(train_mode):
            if train_mode:
                optimizer.zero_grad(set_to_none=True)

            with autocast(enabled=use_amp):
                logits = model(images)
                loss = criterion(logits, targets)

            if train_mode:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

        top1, top3 = accuracy_topk(logits.detach(), targets, topk=(1, 3))
        batch_angle = angle_error(logits.detach(), targets, num_classes=num_classes)

        loss_meter.update(loss.item(), n=batch_size)
        top1_meter.update(top1, n=batch_size)
        top3_meter.update(top3, n=batch_size)
        if not math.isnan(batch_angle):
            angle_meter.update(batch_angle, n=batch_size)

        pbar.set_postfix(
            loss=f"{loss_meter.avg:.4f}",
            top1=f"{top1_meter.avg:.2f}",
            top3=f"{top3_meter.avg:.2f}",
            angle=f"{angle_meter.avg:.2f}",
        )

    return {
        "loss": loss_meter.avg,
        "top1": top1_meter.avg,
        "top3": top3_meter.avg,
        "angle_error": angle_meter.avg,
    }


def save_checkpoint(state: dict, ckpt_path: Path) -> None:
    """保存 checkpoint。"""
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(state, str(ckpt_path))


def load_checkpoint(
    ckpt_path: Path,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: CosineAnnealingLR,
    scaler: GradScaler,
    device: torch.device,
) -> Dict[str, float]:
    """从 checkpoint 恢复训练状态。"""
    checkpoint = torch.load(str(ckpt_path), map_location=device)
    if "model_state_dict" not in checkpoint:
        # 兼容仅保存 state_dict 的场景
        model.load_state_dict(checkpoint)
        return {"start_epoch": 0, "best_top1": 0.0, "no_improve_epochs": 0}

    model.load_state_dict(checkpoint["model_state_dict"])
    if "optimizer_state_dict" in checkpoint:
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    if "scheduler_state_dict" in checkpoint:
        scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
    if "scaler_state_dict" in checkpoint:
        scaler.load_state_dict(checkpoint["scaler_state_dict"])

    start_epoch = int(checkpoint.get("epoch", -1)) + 1
    best_top1 = float(checkpoint.get("best_top1", 0.0))
    no_improve_epochs = int(checkpoint.get("no_improve_epochs", 0))
    return {
        "start_epoch": start_epoch,
        "best_top1": best_top1,
        "no_improve_epochs": no_improve_epochs,
    }


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    device = resolve_device(args.device)

    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    train_loader, val_loader, test_loader = create_dataloaders(
        data_root=args.data_root,
        batch_size=args.batch_size,
        img_size=args.img_size,
        num_classes=args.num_classes,
        num_workers=args.num_workers,
        seed=args.seed,
    )
    print(
        f"数据集切分完成: train={len(train_loader.dataset)}, "
        f"val={len(val_loader.dataset)}, test={len(test_loader.dataset)}"
    )

    model = create_model(num_classes=args.num_classes, dropout=0.3).to(device)
    criterion = nn.MultiLabelSoftMarginLoss()
    optimizer = AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=max(1, args.num_epochs))
    scaler = GradScaler(enabled=device.type == "cuda")
    writer = SummaryWriter(log_dir=str(log_dir))

    latest_ckpt_path = checkpoint_dir / "latest_checkpoint.pth"
    best_ckpt_path = checkpoint_dir / "best_checkpoint.pth"
    best_model_path = checkpoint_dir / "best_model.pth"

    start_epoch = 0
    best_top1 = 0.0
    no_improve_epochs = 0

    if args.resume:
        resume_path = Path(args.resume)
        if not resume_path.exists():
            raise FileNotFoundError(f"恢复 checkpoint 不存在: {resume_path}")
        resume_info = load_checkpoint(
            ckpt_path=resume_path,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            scaler=scaler,
            device=device,
        )
        start_epoch = resume_info["start_epoch"]
        best_top1 = resume_info["best_top1"]
        no_improve_epochs = resume_info["no_improve_epochs"]
        print(
            f"已恢复训练: start_epoch={start_epoch}, "
            f"best_top1={best_top1:.2f}, no_improve={no_improve_epochs}"
        )

    for epoch in range(start_epoch, args.num_epochs):
        train_metrics = run_one_epoch(
            model=model,
            loader=train_loader,
            criterion=criterion,
            device=device,
            num_classes=args.num_classes,
            epoch=epoch,
            total_epochs=args.num_epochs,
            train_mode=True,
            optimizer=optimizer,
            scaler=scaler,
        )

        val_metrics = run_one_epoch(
            model=model,
            loader=val_loader,
            criterion=criterion,
            device=device,
            num_classes=args.num_classes,
            epoch=epoch,
            total_epochs=args.num_epochs,
            train_mode=False,
            optimizer=None,
            scaler=scaler,
        )
        scheduler.step()
        current_lr = optimizer.param_groups[0]["lr"]

        writer.add_scalar("Train/Loss", train_metrics["loss"], epoch)
        writer.add_scalar("Train/Top1", train_metrics["top1"], epoch)
        writer.add_scalar("Train/Top3", train_metrics["top3"], epoch)
        writer.add_scalar("Train/AngleError", train_metrics["angle_error"], epoch)
        writer.add_scalar("Val/Loss", val_metrics["loss"], epoch)
        writer.add_scalar("Val/Top1", val_metrics["top1"], epoch)
        writer.add_scalar("Val/Top3", val_metrics["top3"], epoch)
        writer.add_scalar("Val/AngleError", val_metrics["angle_error"], epoch)
        writer.add_scalar("LR", current_lr, epoch)

        state = {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "scaler_state_dict": scaler.state_dict(),
            "best_top1": best_top1,
            "no_improve_epochs": no_improve_epochs,
            "args": vars(args),
        }
        save_checkpoint(state, latest_ckpt_path)

        improved = val_metrics["top1"] > best_top1
        if improved:
            best_top1 = val_metrics["top1"]
            no_improve_epochs = 0
            state["best_top1"] = best_top1
            state["no_improve_epochs"] = no_improve_epochs
            save_checkpoint(state, best_ckpt_path)
            torch.save(model.state_dict(), str(best_model_path))
        else:
            no_improve_epochs += 1

        print(
            f"[Epoch {epoch + 1}/{args.num_epochs}] "
            f"train_loss={train_metrics['loss']:.4f} val_loss={val_metrics['loss']:.4f} "
            f"val_top1={val_metrics['top1']:.2f} val_top3={val_metrics['top3']:.2f} "
            f"val_angle={val_metrics['angle_error']:.2f} lr={current_lr:.6f}"
        )

        if no_improve_epochs >= args.early_stop_patience:
            print(f"触发早停: 连续 {args.early_stop_patience} 个 epoch 验证集未提升。")
            break

    # 使用最佳模型进行测试集评估
    if best_ckpt_path.exists():
        best_state = torch.load(str(best_ckpt_path), map_location=device)
        model.load_state_dict(best_state["model_state_dict"])
        print(f"已加载最佳模型进行测试，best_top1={best_state.get('best_top1', 0.0):.2f}")

    test_metrics = run_one_epoch(
        model=model,
        loader=test_loader,
        criterion=criterion,
        device=device,
        num_classes=args.num_classes,
        epoch=0,
        total_epochs=1,
        train_mode=False,
        optimizer=None,
        scaler=scaler,
    )
    writer.add_scalar("Test/Loss", test_metrics["loss"], 0)
    writer.add_scalar("Test/Top1", test_metrics["top1"], 0)
    writer.add_scalar("Test/Top3", test_metrics["top3"], 0)
    writer.add_scalar("Test/AngleError", test_metrics["angle_error"], 0)
    writer.flush()
    writer.close()

    print(
        f"测试集结果: loss={test_metrics['loss']:.4f}, "
        f"top1={test_metrics['top1']:.2f}, top3={test_metrics['top3']:.2f}, "
        f"angle_error={test_metrics['angle_error']:.2f}"
    )
    print(f"最佳模型路径: {best_model_path}")


if __name__ == "__main__":
    main()
