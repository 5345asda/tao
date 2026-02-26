"""百度登录验证码处理器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Any
from urllib.parse import quote

import httpx

try:
    from .login_handler import CaptchaChallenge, CaptchaSolution
except ImportError:  # pragma: no cover - 兼容脚本直跑
    from login_handler import CaptchaChallenge, CaptchaSolution  # type: ignore[no-redef]


DEFAULT_MODEL_PATH = "captcha_model/onnx/captcha_effnet_b3.onnx"
DEFAULT_REFERER = "https://wappass.baidu.com/"
DEFAULT_IMAGE_URL_TEMPLATE = "https://wappass.baidu.com/cgi-bin/genimage?{code_string}"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

class CaptchaSolverError(RuntimeError):
    """验证码求解基础异常。"""


class CaptchaChallengeError(CaptchaSolverError):
    """验证码挑战数据异常。"""


class CaptchaDownloadError(CaptchaSolverError):
    """验证码下载异常。"""


class CaptchaPredictError(CaptchaSolverError):
    """验证码预测异常。"""


@dataclass(slots=True)
class CaptchaSolverConfig:
    """验证码处理器配置。"""

    model_path: str = DEFAULT_MODEL_PATH
    referer: str = DEFAULT_REFERER
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    user_agent: str = DEFAULT_USER_AGENT
    image_url_template: str = DEFAULT_IMAGE_URL_TEMPLATE
    cookie_header: str | None = None
    cookies: dict[str, str] = field(default_factory=dict)
    extra_headers: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        """校验配置参数。"""
        if not self.model_path.strip():
            raise ValueError("model_path 不能为空")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0")
        if "{code_string}" not in self.image_url_template:
            raise ValueError("image_url_template 必须包含 {code_string}")


@dataclass(slots=True)
class CaptchaPrediction:
    """模型预测结果。"""

    class_index: int
    angle: float
    confidence: float


class BaiduCaptchaSolver:
    """百度验证码处理器（异步）。"""

    def __init__(
        self,
        config: CaptchaSolverConfig | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or CaptchaSolverConfig()
        self._config.validate()

        self._owns_http_client = http_client is None
        self._http_client = http_client
        self._model = self._build_model(self._config.model_path)

    async def __aenter__(self) -> "BaiduCaptchaSolver":
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def __call__(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """允许实例直接作为 login_handler 的 captcha_callback。"""
        return await self.solve(challenge)

    async def start(self) -> None:
        """初始化异步 HTTP 客户端。"""
        if self._http_client is not None:
            return
        self._http_client = httpx.AsyncClient(
            timeout=self._config.timeout_seconds,
            follow_redirects=True,
        )

    async def close(self) -> None:
        """释放资源。"""
        if self._owns_http_client and self._http_client is not None:
            try:
                await self._http_client.aclose()
            finally:
                self._http_client = None

    async def solve(self, challenge: CaptchaChallenge) -> CaptchaSolution:
        """求解验证码并返回登录处理器可直接使用的结果。"""
        captcha_url = self._resolve_captcha_url(challenge)
        image_bytes = await self._download_captcha_image(captcha_url)
        prediction = self.predict_from_bytes(image_bytes)

        code_str = challenge.vcodestr or challenge.code_string
        return CaptchaSolution(
            verifycode=str(prediction.class_index),
            vcodestr=code_str,
        )

    def predict_from_bytes(self, image_bytes: bytes) -> CaptchaPrediction:
        """从图片字节执行 ONNX 预测。"""
        if not image_bytes:
            raise CaptchaPredictError("图片字节为空，无法预测")

        try:
            raw = self._model.predict_from_bytes(image_bytes)
        except Exception as exc:
            raise CaptchaPredictError(f"模型预测失败: {exc}") from exc

        try:
            class_index = int(raw["class_index"])
            angle = float(raw["angle"])
            confidence = float(raw["confidence"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CaptchaPredictError(f"模型输出格式异常: {raw}") from exc

        return CaptchaPrediction(
            class_index=class_index,
            angle=angle,
            confidence=confidence,
        )

    def set_cookie_header(self, cookie_header: str | None) -> None:
        """设置 Cookie 请求头。"""
        self._config.cookie_header = cookie_header

    def update_cookies(self, cookies: dict[str, str]) -> None:
        """更新 Cookie 字典。"""
        self._config.cookies.update(cookies)

    async def _download_captcha_image(self, captcha_url: str) -> bytes:
        """下载验证码图片。"""
        await self.start()
        if self._http_client is None:  # pragma: no cover - 理论不可达
            raise CaptchaDownloadError("HTTP 客户端未初始化")

        request_kwargs: dict[str, Any] = {
            "headers": self._build_request_headers(),
        }
        if self._config.cookies:
            request_kwargs["cookies"] = self._config.cookies

        try:
            response = await self._http_client.get(captcha_url, **request_kwargs)
        except httpx.HTTPError as exc:
            raise CaptchaDownloadError(f"下载验证码失败: {captcha_url}, error={exc}") from exc

        if response.status_code >= 400:
            raise CaptchaDownloadError(
                f"下载验证码失败: HTTP {response.status_code}, url={captcha_url}"
            )
        if not response.content:
            raise CaptchaDownloadError(f"验证码内容为空: {captcha_url}")
        return response.content

    def _resolve_captcha_url(self, challenge: CaptchaChallenge) -> str:
        """从挑战信息中解析验证码图片地址。"""
        if not isinstance(challenge, CaptchaChallenge):
            raise CaptchaChallengeError("challenge 类型错误，必须是 CaptchaChallenge")

        # 优先使用明确的图片 URL。
        url = self._safe_str(challenge.captcha_url)
        if url:
            return self._normalize_captcha_url(url)

        raw_url = self._safe_str(
            self._find_first_value(
                challenge.raw,
                {"captchaUrl", "captcha_url", "img", "imgUrl", "image", "url"},
            )
        )
        if raw_url:
            return self._normalize_captcha_url(raw_url)

        token = self._safe_str(challenge.code_string) or self._safe_str(challenge.vcodestr)
        if not token:
            raise CaptchaChallengeError("挑战中缺少 captcha_url 和 code_string")

        if token.startswith("http://") or token.startswith("https://"):
            return token

        return self._config.image_url_template.format(code_string=quote(token, safe=""))

    def _normalize_captcha_url(self, url: str) -> str:
        """规范化图片地址，兼容相对路径。"""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("/"):
            return f"https://wappass.baidu.com{url}"
        return url

    def _build_request_headers(self) -> dict[str, str]:
        """构建验证码下载请求头。"""
        headers: dict[str, str] = {
            "User-Agent": self._config.user_agent,
            "Referer": self._config.referer,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        if self._config.cookie_header:
            headers["Cookie"] = self._config.cookie_header
        if self._config.extra_headers:
            headers.update(self._config.extra_headers)
        return headers

    @staticmethod
    def _find_first_value(payload: Any, keys: set[str]) -> Any:
        """在任意嵌套结构里查找首个非空字段。"""
        queue: list[Any] = [payload]
        while queue:
            node = queue.pop(0)
            if isinstance(node, dict):
                for key in keys:
                    if key in node and node[key] not in (None, ""):
                        return node[key]
                queue.extend(node.values())
            elif isinstance(node, list):
                queue.extend(node)
        return None

    @staticmethod
    def _safe_str(value: Any) -> str | None:
        """安全转字符串。"""
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _build_model(model_path: str) -> Any:
        """构建 CaptchaModel，兼容包内导入与脚本直跑。"""
        model_file = Path(model_path)
        if not model_file.exists():
            raise CaptchaPredictError(f"ONNX 模型不存在: {model_path}")

        try:
            from captcha_test.model import CaptchaModel  # type: ignore

            return CaptchaModel(model_path=model_path)
        except Exception:
            # captcha_test/model.py 使用了相对目录导入，这里补充路径兼容脚本场景。
            captcha_test_dir = Path(__file__).resolve().parent.parent / "captcha_test"
            if str(captcha_test_dir) not in sys.path:
                sys.path.insert(0, str(captcha_test_dir))
            try:
                from model import CaptchaModel  # type: ignore

                return CaptchaModel(model_path=model_path)
            except Exception as exc:
                raise CaptchaPredictError(f"初始化 CaptchaModel 失败: {exc}") from exc


def build_captcha_callback(
    *,
    model_path: str = DEFAULT_MODEL_PATH,
    referer: str = DEFAULT_REFERER,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    cookie_header: str | None = None,
    cookies: dict[str, str] | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> BaiduCaptchaSolver:
    """创建可直接传入 login_handler 的验证码求解器。"""
    config = CaptchaSolverConfig(
        model_path=model_path,
        referer=referer,
        timeout_seconds=timeout_seconds,
        cookie_header=cookie_header,
        cookies=cookies or {},
    )
    return BaiduCaptchaSolver(config=config, http_client=http_client)


__all__ = [
    "BaiduCaptchaSolver",
    "CaptchaChallengeError",
    "CaptchaDownloadError",
    "CaptchaPredictError",
    "CaptchaPrediction",
    "CaptchaSolverConfig",
    "CaptchaSolverError",
    "build_captcha_callback",
]
