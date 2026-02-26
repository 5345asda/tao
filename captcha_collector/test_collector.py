"""收集器单元测试。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from config import CONTINUOUS_FAIL_LIMIT, PROBE_STEPS, VERIFY_DELAY
from dedup import DedupManager


class TestDedupManager:
    """测试去重管理器。"""

    def test_compute_hash(self) -> None:
        """测试哈希计算。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            hash_file = os.path.join(tmpdir, ".hashes.txt")
            dm = DedupManager(hash_file)

            data = b"test_data"
            h1 = dm.compute_hash(data)
            h2 = dm.compute_hash(data)

            assert h1 == h2
            assert len(h1) == 32  # MD5 hex 长度

    def test_exists_false_initially(self) -> None:
        """测试初始不存在。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            hash_file = os.path.join(tmpdir, ".hashes.txt")
            dm = DedupManager(hash_file)

            assert not dm.exists(b"test_data")

    def test_add_and_exists(self) -> None:
        """测试添加后存在。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            hash_file = os.path.join(tmpdir, ".hashes.txt")
            dm = DedupManager(hash_file)

            data = b"test_data"
            dm.add(data)

            assert dm.exists(data)
            assert len(dm) == 1

    def test_persistence(self) -> None:
        """测试持久化。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            hash_file = os.path.join(tmpdir, ".hashes.txt")

            # 第一次写入
            dm1 = DedupManager(hash_file)
            dm1.add(b"data1")
            dm1.add(b"data2")

            # 重新加载
            dm2 = DedupManager(hash_file)
            assert dm2.exists(b"data1")
            assert dm2.exists(b"data2")
            assert len(dm2) == 2


class TestConfig:
    """测试配置。"""

    def test_probe_steps_count(self) -> None:
        """测试探测点数量。"""
        assert len(PROBE_STEPS) == 10

    def test_probe_steps_range(self) -> None:
        """测试探测点范围。"""
        assert all(0 <= s < 100 for s in PROBE_STEPS)

    def test_verify_delay_positive(self) -> None:
        """测试验证延迟为正。"""
        assert VERIFY_DELAY > 0

    def test_fail_limit_positive(self) -> None:
        """测试失败阈值为正。"""
        assert CONTINUOUS_FAIL_LIMIT > 0


if __name__ == "__main__":
    # 无 pytest 环境时手动运行测试
    import traceback

    test_dedup = TestDedupManager()
    test_config = TestConfig()

    tests = [
        ("test_compute_hash", test_dedup.test_compute_hash),
        ("test_exists_false_initially", test_dedup.test_exists_false_initially),
        ("test_add_and_exists", test_dedup.test_add_and_exists),
        ("test_persistence", test_dedup.test_persistence),
        ("test_probe_steps_count", test_config.test_probe_steps_count),
        ("test_probe_steps_range", test_config.test_probe_steps_range),
        ("test_verify_delay_positive", test_config.test_verify_delay_positive),
        ("test_fail_limit_positive", test_config.test_fail_limit_positive),
    ]

    passed = 0
    failed = 0
    for name, test_func in tests:
        try:
            test_func()
            print(f"[PASS] {name}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\nResult: {passed} passed, {failed} failed")
