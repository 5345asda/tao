"""百度验证码 API 封装。"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, Optional

import requests

from config import API_AK, API_REFERER, API_TIMEOUT
from crypto import encrypt_angle


class BaiduAPIError(Exception):
    """百度验证码 API 调用异常。"""


class BaiduCaptchaAPI:
    """百度验证码 API 客户端。"""

    INIT_URL = "https://passport.baidu.com/cap/init"
    STYLE_URL = "https://passport.baidu.com/cap/style"
    VERIFY_URL = "https://passport.baidu.com/cap/log"

    def __init__(
        self,
        ak: str = API_AK,
        referer: str = API_REFERER,
        ver: str = "1.0.0",
        timeout: int = API_TIMEOUT,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not ak:
            raise ValueError("ak 不能为空。")
        if not referer:
            raise ValueError("referer 不能为空。")

        self.ak = ak
        self.referer = referer
        self.ver = ver
        self.timeout = timeout
        self.session: requests.Session = session or requests.Session()
        self.session.headers.update(
            {
                "Referer": self.referer,
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
            }
        )

    def _post_json(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """发送 POST 请求并返回 JSON。"""
        try:
            resp = self.session.post(url, data=data, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise BaiduAPIError(f"请求失败: {url}, 错误: {exc}") from exc

        try:
            payload = resp.json()
        except ValueError as exc:
            raise BaiduAPIError(f"响应不是有效 JSON: {url}") from exc

        if not isinstance(payload, dict):
            raise BaiduAPIError(f"响应 JSON 类型异常: {url}, 实际类型: {type(payload).__name__}")
        return payload

    def _find_first_value(self, payload: Any, keys: Iterable[str]) -> Optional[str]:
        """在任意嵌套结构中查找首个匹配字段。"""
        key_set = {k for k in keys}
        queue = [payload]
        while queue:
            node = queue.pop(0)
            if isinstance(node, dict):
                for k in key_set:
                    if k in node and node[k] not in (None, ""):
                        return str(node[k])
                queue.extend(node.values())
            elif isinstance(node, list):
                queue.extend(node)
        return None

    def get_init(self) -> Dict[str, str]:
        """初始化验证码会话，返回 tk 和 as。"""
        data = {
            "ak": self.ak,
            "ver": self.ver,
            "refer": self.referer,
            "_": int(time.time() * 1000),
        }
        payload = self._post_json(self.INIT_URL, data)

        tk = self._find_first_value(payload, ("tk",))
        as_token = self._find_first_value(payload, ("as", "asToken", "as_token"))
        if not tk or not as_token:
            raise BaiduAPIError(f"init 响应缺少 tk/as 字段: {payload}")
        return {"tk": tk, "as": as_token}

    def get_style(self, tk: str) -> Dict[str, str]:
        """获取验证码样式与图片地址。"""
        if not tk:
            raise ValueError("tk 不能为空。")

        data = {
            "ak": self.ak,
            "ver": self.ver,
            "tk": tk,
            "typeid": "spin-0",
            "isios": "0",
        }
        payload = self._post_json(self.STYLE_URL, data)

        # 解析嵌套结构: data.captchalist[0].source.back.path
        backstr = self._find_first_value(payload, ("backstr",))
        img_url = None

        # 尝试从 captchalist 中提取图片 URL
        data_obj = payload.get("data", payload)
        captchalist = data_obj.get("captchalist", [])
        if captchalist and isinstance(captchalist, list):
            first_item = captchalist[0]
            source = first_item.get("source", {})
            back = source.get("back", {})
            img_url = back.get("path")

        if not img_url or not backstr:
            raise BaiduAPIError(f"style 响应缺少 img_url/backstr 字段: {payload}")
        return {"img_url": img_url, "backstr": backstr}

    def get_image(self, img_url: str) -> bytes:
        """下载验证码图片字节。"""
        if not img_url:
            raise ValueError("img_url 不能为空。")
        try:
            resp = self.session.get(img_url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise BaiduAPIError(f"下载图片失败: {img_url}, 错误: {exc}") from exc

        if not resp.content:
            raise BaiduAPIError(f"图片内容为空: {img_url}")
        return resp.content

    def verify(self, tk: str, as_token: str, backstr: str, angle: int) -> bool:
        """提交验证码验证结果，成功返回 True。"""
        if not tk:
            raise ValueError("tk 不能为空。")
        if not as_token:
            raise ValueError("as_token 不能为空。")
        if not backstr:
            raise ValueError("backstr 不能为空。")
        if not isinstance(angle, int):
            raise ValueError("angle 必须为 int 类型。")

        try:
            fs_value = encrypt_angle(angle=angle, as_token=as_token, backstr=backstr)
        except Exception as exc:
            raise BaiduAPIError(f"加密 fs 参数失败: {exc}") from exc

        data = {
            "tk": tk,
            "as": as_token,
            "fs": fs_value,
            "ak": self.ak,
            "ver": self.ver,
            "cv": "submit",
            "typeid": "spin-0",
        }
        payload = self._post_json(self.VERIFY_URL, data)
        op = self._find_first_value(payload, ("op",))
        return op == "1"
