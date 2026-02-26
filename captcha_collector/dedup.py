"""去重管理器 - 基于 MD5 哈希的去重逻辑。"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Set


class DedupManager:
    """MD5 哈希去重管理器（线程安全）。"""

    def __init__(self, hash_file: str | Path) -> None:
        self.hash_file = Path(hash_file)
        self._hashes: Set[str] = set()
        self._lock = threading.Lock()  # 线程锁
        self._load_hashes()

    def _load_hashes(self) -> None:
        """从文件加载已有哈希。"""
        if self.hash_file.exists():
            with open(self.hash_file, "r", encoding="utf-8") as f:
                with self._lock:
                    self._hashes = set(line.strip() for line in f if line.strip())

    def compute_hash(self, data: bytes) -> str:
        """计算数据的 MD5 哈希。"""
        return hashlib.md5(data).hexdigest()

    def exists(self, data: bytes) -> bool:
        """检查数据是否已存在（线程安全）。"""
        hash_value = self.compute_hash(data)
        with self._lock:
            return hash_value in self._hashes

    def add(self, data: bytes) -> str:
        """添加数据哈希，返回哈希值（线程安全）。"""
        hash_value = self.compute_hash(data)
        with self._lock:
            if hash_value in self._hashes:
                return hash_value  # 已存在，不重复添加
            self._hashes.add(hash_value)
            # 追加写入文件
            self.hash_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.hash_file, "a", encoding="utf-8") as f:
                f.write(f"{hash_value}\n")
        return hash_value

    def __len__(self) -> int:
        with self._lock:
            return len(self._hashes)
