"""验证码训练数据收集器。"""

from __future__ import annotations

import hashlib
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple

# 先添加 captcha_test 目录用于加载模型（放在后面）
sys.path.insert(0, str(Path(__file__).parent))

from baidu_api import BaiduAPIError, BaiduCaptchaAPI
from config import (
    AK,
    API_TIMEOUT,
    DELAY_BETWEEN_REQUESTS,
    HASH_FILE,
    MAX_WORKERS,
    NETWORK_RETRY,
    NETWORK_RETRY_DELAY,
    NUM_CLASSES,
    OUTPUT_DIR,
    PROBE_STEPS,
    REFERER,
    TARGET_COUNT,
    VERIFY_DELAY,
)
from dedup import DedupManager


class ExhaustiveCollector:
    """穷举式数据收集器: 步长探测 + 边界扩展（支持高并发）。"""

    def __init__(self) -> None:
        self.api = BaiduCaptchaAPI(ak=AK, referer=REFERER, timeout=API_TIMEOUT)
        self.output_dir = Path(OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.probe_steps = PROBE_STEPS
        self.verify_delay = VERIFY_DELAY
        self.num_classes = NUM_CLASSES
        self.target_count = TARGET_COUNT

        self.dedup = DedupManager(HASH_FILE)

        # 统计信息（线程安全）
        self.stats: dict[str, int] = {"success": 0, "failed": 0, "duplicate": 0, "total": 0}
        self._stats_lock = threading.Lock()
        self._print_lock = threading.Lock()

    def _get_captcha(self) -> tuple[dict, bytes, str, str]:
        """获取验证码，返回 (init_data, img_bytes, img_url, backstr)。"""
        init_data = self.api.get_init()
        tk = init_data["tk"]

        style_data = self.api.get_style(tk)
        img_url = style_data["img_url"]
        backstr = style_data["backstr"]
        img_bytes = self.api.get_image(img_url)

        return init_data, img_bytes, img_url, backstr

    def _verify_with_retry(self, tk: str, as_token: str, backstr: str, angle: int) -> bool:
        """带重试的验证。"""
        for attempt in range(NETWORK_RETRY):
            try:
                return self.api.verify(tk, as_token, backstr, angle)
            except BaiduAPIError:
                if attempt < NETWORK_RETRY - 1:
                    time.sleep(NETWORK_RETRY_DELAY)
                else:
                    raise

        return False

    def probe_for_success(self) -> tuple[int | None, bytes, str, str, str]:
        """步长探测，找到第一个成功角度。

        Returns:
            (成功角度, 图片字节, tk, as_token, backstr)
            如果全部失败，返回 (None, img_bytes, tk, as_token, backstr)
        """
        init_data, img_bytes, _img_url, backstr = self._get_captcha()
        tk = init_data["tk"]
        as_token = init_data["as"]

        for probe_angle in self.probe_steps:
            try:
                is_success = self._verify_with_retry(tk, as_token, backstr, probe_angle)
                if is_success:
                    return probe_angle, img_bytes, tk, as_token, backstr

                time.sleep(self.verify_delay)

                # 每次验证后获取新验证码继续探测
                init_data, img_bytes, _img_url, backstr = self._get_captcha()
                tk = init_data["tk"]
                as_token = init_data["as"]
            except BaiduAPIError:
                time.sleep(1)
                init_data, img_bytes, _img_url, backstr = self._get_captcha()
                tk = init_data["tk"]
                as_token = init_data["as"]

        return None, img_bytes, tk, as_token, backstr

    def expand_boundaries(self, center: int, tk: str, as_token: str, backstr: str) -> list[int]:
        """从中心角度向左右扩展边界（复用同一个 tk/as/backstr）。"""
        successful_angles: list[int] = [center]

        # 向左扩展
        angle = center - 1
        while angle >= 0:
            try:
                is_success = self._verify_with_retry(tk, as_token, backstr, angle)
                if is_success:
                    successful_angles.append(angle)
                    angle -= 1
                else:
                    break

                time.sleep(self.verify_delay)
            except BaiduAPIError:
                break

        # 向右扩展
        angle = center + 1
        while angle < self.num_classes:
            try:
                is_success = self._verify_with_retry(tk, as_token, backstr, angle)
                if is_success:
                    successful_angles.append(angle)
                    angle += 1
                else:
                    break

                time.sleep(self.verify_delay)
            except BaiduAPIError:
                break

        return sorted(set(successful_angles))

    def _get_label_dir_name(self, labels: list[int]) -> str:
        """将标签列表转换为目录名。"""
        return "_".join(str(label) for label in sorted(labels))

    def save_image(self, img_bytes: bytes, labels: list[int]) -> Path:
        """保存图片到对应标签目录。"""
        dir_name = self._get_label_dir_name(labels)
        label_dir = self.output_dir / dir_name
        label_dir.mkdir(parents=True, exist_ok=True)

        img_hash = self.dedup.compute_hash(img_bytes)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{img_hash[:8]}.jpg"
        filepath = label_dir / filename

        with open(filepath, "wb") as file:
            file.write(img_bytes)

        self.dedup.add(img_bytes)
        return filepath

    def _print_status(
        self,
        index: int,
        probe: int | None,
        angle_range: list[int] | None,
        status: str,
    ) -> None:
        """打印状态信息（线程安全）。"""
        with self._print_lock:
            timestamp = datetime.now().strftime("%H:%M:%S")

            if status == "success" and angle_range:
                left, right = angle_range[0], angle_range[-1]
                print(f"[{timestamp}] #{index:<3d} probe:{probe} OK  range:[{left}-{right}]  [OK]")
            elif status == "failed":
                print(f"[{timestamp}] #{index:<3d} all probes failed              [FAIL]")
            elif status == "duplicate":
                print(f"[{timestamp}] #{index:<3d} probe:{probe} OK  duplicate      [DUP]")

    def _update_stats(self, key: str, delta: int = 1) -> None:
        """更新统计信息（线程安全）。"""
        with self._stats_lock:
            self.stats[key] += delta

    def _process_single(self, task_id: int) -> dict:
        """处理单个收集任务（供线程池调用）。"""
        result: dict[str, object] = {"task_id": task_id, "status": "failed"}

        try:
            # 步长探测
            success_angle, img_bytes, tk, as_token, backstr = self.probe_for_success()
            if success_angle is None:
                return result

            result["probe"] = success_angle

            # 去重检查
            if self.dedup.exists(img_bytes):
                result["status"] = "duplicate"
                return result

            # 边界扩展并保存
            angle_range = self.expand_boundaries(success_angle, tk, as_token, backstr)
            filepath = self.save_image(img_bytes, angle_range)

            result["status"] = "success"
            result["angle_range"] = angle_range
            result["filepath"] = str(filepath)
        except Exception as error:
            result["error"] = str(error)

        return result

    def _print_summary(self) -> None:
        """打印汇总信息。"""
        success = self.stats["success"]
        failed = self.stats["failed"]
        duplicate = self.stats["duplicate"]
        total = self.stats["total"]
        rate = (success / total * 100) if total > 0 else 0
        print(
            f"\n进度: {total} | 成功: {success} | 失败: {failed} | "
            f"重复: {duplicate} | 成功率: {rate:.1f}%"
        )

    def run(self, num_images: int | None = None) -> None:
        """运行收集器（高并发模式）。"""
        target = num_images or self.target_count
        max_workers = MAX_WORKERS

        print("=" * 60)
        print("穷举数据收集器 - 步长探测 + 边界扩展 [高并发模式]")
        print("=" * 60)
        print(f"探测序列: {self.probe_steps}")
        print(f"目标数量: {target}")
        print(f"并发线程: {max_workers}")
        print(f"已去重: {len(self.dedup)} 条")
        print("-" * 60)

        collected = 0
        task_id = 0
        max_attempts = target * 10

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: dict = {}

            # 初始提交一批任务，保持线程池持续忙碌
            for _ in range(max_workers * 2):
                if task_id >= max_attempts:
                    break
                task_id += 1
                future = executor.submit(self._process_single, task_id)
                futures[future] = task_id

            while collected < target and futures:
                done_futures = []
                try:
                    future_iter = as_completed(list(futures.keys()), timeout=0.05)
                    for done_future in future_iter:
                        done_futures.append(done_future)
                except TimeoutError:
                    pass

                if not done_futures:
                    time.sleep(0.01)
                    continue

                for future in done_futures:
                    task_num = futures.pop(future)
                    try:
                        result = future.result()
                        self._update_stats("total")

                        if result["status"] == "success":
                            self._update_stats("success")
                            collected += 1
                            probe = result.get("probe")
                            angle_range = result.get("angle_range")
                            self._print_status(
                                task_num,
                                probe if isinstance(probe, int) else None,
                                angle_range if isinstance(angle_range, list) else None,
                                "success",
                            )
                        elif result["status"] == "duplicate":
                            self._update_stats("duplicate")
                            probe = result.get("probe")
                            self._print_status(
                                task_num,
                                probe if isinstance(probe, int) else None,
                                None,
                                "duplicate",
                            )
                        else:
                            self._update_stats("failed")
                            self._print_status(task_num, None, None, "failed")

                        # 补充新任务
                        if collected < target and task_id < max_attempts:
                            task_id += 1
                            new_future = executor.submit(self._process_single, task_id)
                            futures[new_future] = task_id
                    except Exception as error:
                        print(f"[错误] 任务 {task_num}: {error}")

        self._print_summary()
        print(f"\n数据目录: {self.output_dir}")


class SmartDataCollector:
    """智能数据收集器 - 使用多次请求穷举。"""

    def __init__(self) -> None:
        self.api = BaiduCaptchaAPI(ak=AK, referer=REFERER, timeout=API_TIMEOUT)
        self.output_dir = Path(OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.collected_count = 0

    def _get_image_hash(self, img_bytes: bytes) -> str:
        """计算图片 MD5 哈希。"""
        return hashlib.md5(img_bytes).hexdigest()

    def _get_label_dir_name(self, labels: List[int]) -> str:
        """将标签列表转换为目录名。"""
        return "_".join(str(label) for label in sorted(labels))

    def test_angle(self, img_url: str, backstr: str, class_idx: int) -> bool:
        """为同一张图片测试特定角度。"""
        _ = img_url
        _ = backstr
        try:
            # 获取新的 tk / as
            init_data = self.api.get_init()
            tk = init_data["tk"]
            as_token = init_data["as"]

            style_data = self.api.get_style(tk)
            new_backstr = style_data["backstr"]

            return self.api.verify(tk, as_token, new_backstr, class_idx)
        except BaiduAPIError:
            return False

    def exhaustively_find_labels(
        self,
        img_bytes: bytes,
        img_url: str,
        backstr: str,
    ) -> Tuple[Set[int], bytes]:
        """穷举测试找到所有正确角度。"""
        _ = img_url
        _ = backstr
        passed_labels: Set[int] = set()
        current_img_bytes = img_bytes

        print("  穷举测试: ", end="", flush=True)

        for class_idx in range(NUM_CLASSES):
            try:
                init_data = self.api.get_init()
                tk = init_data["tk"]
                as_token = init_data["as"]

                style_data = self.api.get_style(tk)
                new_img_url = style_data["img_url"]
                new_backstr = style_data["backstr"]

                current_img_bytes = self.api.get_image(new_img_url)
                is_success = self.api.verify(tk, as_token, new_backstr, class_idx)

                if is_success:
                    passed_labels.add(class_idx)
                    print(f"[{class_idx}OK]", end="", flush=True)
                elif class_idx % 10 == 0:
                    print(".", end="", flush=True)

                time.sleep(0.08)
            except BaiduAPIError:
                time.sleep(0.2)

        print()
        return passed_labels, current_img_bytes

    def quick_find_label(self) -> Tuple[Optional[int], bytes, bytes, str]:
        """快速找到一个正确角度（单次请求）。"""
        try:
            init_data = self.api.get_init()
            tk = init_data["tk"]
            as_token = init_data["as"]

            style_data = self.api.get_style(tk)
            img_url = style_data["img_url"]
            backstr = style_data["backstr"]

            img_bytes = self.api.get_image(img_url)
            _ = as_token
            return None, img_bytes, img_url, backstr
        except BaiduAPIError as error:
            raise RuntimeError(f"获取验证码失败: {error}") from error

    def expand_labels_with_tolerance(self, labels: Set[int], tolerance: int = 3) -> List[int]:
        """扩展标签容差范围。"""
        expanded: Set[int] = set()
        for label in labels:
            for offset in range(-tolerance, tolerance + 1):
                new_label = label + offset
                if 0 <= new_label < NUM_CLASSES:
                    expanded.add(new_label)
        return sorted(expanded)

    def save_image(self, img_bytes: bytes, labels: List[int]) -> Path:
        """保存图片到对应标签目录。"""
        dir_name = self._get_label_dir_name(labels)
        label_dir = self.output_dir / dir_name
        label_dir.mkdir(parents=True, exist_ok=True)

        img_hash = self._get_image_hash(img_bytes)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{img_hash[:8]}.jpg"
        filepath = label_dir / filename

        with open(filepath, "wb") as file:
            file.write(img_bytes)

        return filepath

    def run_exhaustive(self, num_images: int = 10) -> None:
        """穷举模式: 收集指定数量图片。"""
        print("=" * 70)
        print("穷举模式 - 每张图片测试所有角度")
        print("=" * 70)
        print(f"目标图片数: {num_images}")
        print(f"预计请求次数: ~{num_images * 100}")
        print("-" * 70)

        collected = 0
        total_labels_found: List[int] = []

        while collected < num_images:
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{timestamp}] 图片 #{collected + 1}")

                passed_labels, final_img_bytes = self.exhaustively_find_labels(b"", "", "")

                if passed_labels:
                    expanded = self.expand_labels_with_tolerance(passed_labels)
                    filepath = self.save_image(final_img_bytes, expanded)

                    angles = [label * 3.6 for label in passed_labels]
                    angle_str = ", ".join(f"{angle:.1f}deg" for angle in angles)

                    print(f"  [OK] 保存成功: {sorted(passed_labels)} | 角度: {angle_str}")
                    print(f"  文件: {filepath.name}")

                    total_labels_found.extend(passed_labels)
                    collected += 1
                else:
                    print("  [X] 未找到正确角度")
            except Exception as error:
                print(f"  [X] 错误: {error}")
                time.sleep(1)

        print("\n" + "=" * 70)
        print(f"收集完成: {collected} 张图片")
        print(f"数据目录: {OUTPUT_DIR}")

        if total_labels_found:
            from collections import Counter

            label_counts = Counter(total_labels_found)
            print("\n标签分布 (Top 10):")
            for label, count in label_counts.most_common(10):
                angle = label * 3.6
                print(f"  类别 {label:2d} ({angle:5.1f}deg): {count} 次")

    def run_smart(self, num_images: int = 100) -> None:
        """智能模式: 快速收集。"""
        print("=" * 70)
        print("智能模式 - 使用模型预测辅助")
        print("=" * 70)
        print(f"目标图片数: {num_images}")
        print("-" * 70)

        try:
            captcha_test_path = str(Path(__file__).parent.parent / "captcha_test")
            if captcha_test_path not in sys.path:
                sys.path.insert(0, captcha_test_path)
            from model import CaptchaModel

            model = CaptchaModel()
            use_model = True
            print("[OK] 模型加载成功")
        except Exception as error:
            use_model = False
            print(f"[X] 模型加载失败: {error}")
            print("  将使用纯穷举模式")

        print("-" * 70)

        collected = 0
        attempts = 0
        max_attempts = num_images * 5

        while collected < num_images and attempts < max_attempts:
            attempts += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            try:
                init_data = self.api.get_init()
                tk = init_data["tk"]
                as_token = init_data["as"]

                style_data = self.api.get_style(tk)
                img_url = style_data["img_url"]
                backstr = style_data["backstr"]

                img_bytes = self.api.get_image(img_url)

                if use_model:
                    result = model.predict_from_bytes(img_bytes)
                    pred_idx = result["class_index"]
                    confidence = result["confidence"]

                    is_success = self.api.verify(tk, as_token, backstr, pred_idx)

                    if is_success:
                        expanded = self.expand_labels_with_tolerance({pred_idx})
                        self.save_image(img_bytes, expanded)

                        angle = pred_idx * 3.6
                        print(
                            f"[{timestamp}] #{collected + 1:3d} [OK] "
                            f"pred:{pred_idx} ({angle:.1f}deg) conf:{confidence:.2f}"
                        )
                        collected += 1
                    else:
                        print(f"[{timestamp}] #{attempts:3d} [X] pred:{pred_idx} conf:{confidence:.2f}")
                else:
                    print(f"[{timestamp}] #{attempts:3d} 跳过（无模型）")

                time.sleep(DELAY_BETWEEN_REQUESTS)
            except Exception as error:
                print(f"[{timestamp}] #{attempts:3d} [X] error: {error}")
                time.sleep(1)

        print("\n" + "=" * 70)
        print(f"收集完成: {collected}/{num_images} 张图片")
        print(f"数据目录: {OUTPUT_DIR}")


def main() -> None:
    """主函数。"""
    import argparse

    parser = argparse.ArgumentParser(description="验证码训练数据收集器")
    parser.add_argument(
        "--mode",
        choices=["exhaustive", "smart"],
        default="exhaustive",
        help="收集模式: exhaustive=步长探测+边界扩展, smart=模型辅助",
    )
    parser.add_argument("--num", type=int, default=50, help="目标收集数量")
    parser.add_argument("--output", type=str, default=None, help="输出目录")

    args = parser.parse_args()

    if args.output:
        global OUTPUT_DIR
        OUTPUT_DIR = args.output

    if args.mode == "exhaustive":
        collector = ExhaustiveCollector()
        collector.run(num_images=args.num)
    else:
        collector = SmartDataCollector()
        collector.run_smart(num_images=args.num)


if __name__ == "__main__":
    main()
