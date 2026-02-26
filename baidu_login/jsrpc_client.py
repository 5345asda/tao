"""百度移动端登录 JSRPC 客户端。"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

DEFAULT_TIMEOUT_SECONDS = 10.0
LOGIN_URL = (
    "https://wappass.baidu.com/passport/?login&tpl=wise&sms=1&regtype=1&u="
    "https%3A%2F%2Fwww.baidu.com%2F&extrajson=%7b%22src%22%3a%22se_000000%22%7d"
    "#/password_login"
)

logger = logging.getLogger(__name__)


class BaiduLoginClientError(RuntimeError):
    """Baidu 登录客户端基础异常。"""


class BaiduLoginTimeoutError(BaiduLoginClientError):
    """等待登录参数或 AES 密钥超时。"""


class BaiduLoginInjectionError(BaiduLoginClientError):
    """JSRPC 注入异常。"""


@dataclass(slots=True)
class EncryptedLoginParams:
    """登录加密参数。"""

    password: str | None = None
    username: str | None = None
    k: str | None = None
    s: str | None = None
    ds: str | None = None
    tk: str | None = None
    sig: str | None = None
    sha_one: str | None = None
    servertime: str | None = None
    fuid: str | None = None
    gid: str | None = None
    session_id: str | None = None
    baidu_id: str | None = None
    raw_body: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_jsrpc(cls, data: dict[str, Any]) -> "EncryptedLoginParams":
        """将 JSRPC 返回结果映射为数据结构。"""
        known_keys = {
            "password",
            "username",
            "k",
            "s",
            "ds",
            "tk",
            "sig",
            "shaOne",
            "servertime",
            "fuid",
            "gid",
            "session_id",
            "baiduId",
            "_rawBody",
        }
        return cls(
            password=data.get("password"),
            username=data.get("username"),
            k=data.get("k"),
            s=data.get("s"),
            ds=data.get("ds"),
            tk=data.get("tk"),
            sig=data.get("sig"),
            sha_one=data.get("shaOne"),
            servertime=data.get("servertime"),
            fuid=data.get("fuid"),
            gid=data.get("gid"),
            session_id=data.get("session_id"),
            baidu_id=data.get("baiduId"),
            raw_body=data.get("_rawBody"),
            extras={k: v for k, v in data.items() if k not in known_keys},
        )


@dataclass(slots=True)
class AESKeyResult:
    """AES 密钥结果。"""

    key: str | None
    available: bool


class BaiduLoginJSRPCClient:
    """通过 Playwright 复用浏览器加密能力的 JSRPC 客户端。"""

    def __init__(
        self,
        login_url: str = LOGIN_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        headless: bool = True,
    ) -> None:
        self._login_url = login_url
        self._timeout_seconds = timeout_seconds
        self._headless = headless

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._started = False

        self._inject_script_path = Path(__file__).resolve().parent / "js" / "inject.js"

    async def __aenter__(self) -> "BaiduLoginJSRPCClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def start(self) -> None:
        """初始化浏览器、注入脚本并打开登录页。"""
        if self._started:
            logger.debug("JSRPC 客户端已初始化，跳过重复启动")
            return

        if not self._inject_script_path.exists():
            raise FileNotFoundError(f"未找到注入脚本: {self._inject_script_path}")

        try:
            logger.info("启动 Playwright 浏览器")
            self._playwright = await async_playwright().start()
            device = self._playwright.devices.get("iPhone 15")
            if device is None:
                raise BaiduLoginClientError("当前 Playwright 版本不包含 iPhone 15 设备描述")

            self._browser = await self._playwright.chromium.launch(headless=self._headless)
            self._context = await self._browser.new_context(**device, locale="zh-CN")

            # 在页面脚本执行前注入 JSRPC Hook。
            inject_script = self._inject_script_path.read_text(encoding="utf-8")
            await self._context.add_init_script(script=inject_script)

            self._page = await self._context.new_page()
            self._page.on("console", self._handle_console)
            self._page.on("pageerror", self._handle_page_error)

            logger.info("打开百度移动端登录页")
            await self._page.goto(self._login_url, wait_until="domcontentloaded")
            await self._wait_jsrpc_ready(self._timeout_seconds)

            self._started = True
            logger.info("JSRPC 客户端初始化完成")
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        """释放浏览器资源。"""
        close_errors: list[Exception] = []

        if self._page is not None:
            try:
                await self._page.close()
            except Exception as exc:
                close_errors.append(exc)
            finally:
                self._page = None

        if self._context is not None:
            try:
                await self._context.close()
            except Exception as exc:
                close_errors.append(exc)
            finally:
                self._context = None

        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as exc:
                close_errors.append(exc)
            finally:
                self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception as exc:
                close_errors.append(exc)
            finally:
                self._playwright = None

        self._started = False

        if close_errors:
            logger.warning("关闭资源时出现异常: %s", close_errors[0])

    async def get_encrypted_params(
        self,
        username: str,
        password: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> EncryptedLoginParams:
        """触发登录并返回捕获到的加密参数。"""
        page = self._require_page()
        timeout_ms = self._to_timeout_ms(timeout_seconds)

        logger.info("触发登录参数加密流程")

        try:
            trigger_result = await page.evaluate(
                """(args) => window.baiduLogin.triggerLogin(args.username, args.password)""",
                {"username": username, "password": password},
            )
        except PlaywrightError as exc:
            logger.exception("触发登录失败")
            raise BaiduLoginClientError(f"触发登录失败: {exc}") from exc

        if isinstance(trigger_result, dict) and trigger_result.get("status") == "error":
            message = str(trigger_result.get("message") or "未知错误")
            raise BaiduLoginClientError(f"页面触发登录失败: {message}")

        try:
            raw_params = await page.evaluate(
                "(timeout) => window.baiduLogin.waitForParams(timeout)",
                timeout_ms,
            )
        except PlaywrightError as exc:
            message = str(exc)
            if "Timeout waiting for login params" in message:
                raise BaiduLoginTimeoutError(
                    f"{timeout_seconds:.2f} 秒内未捕获到加密参数"
                ) from exc
            logger.exception("等待加密参数失败")
            raise BaiduLoginClientError(f"等待加密参数失败: {exc}") from exc

        if not isinstance(raw_params, dict):
            raise BaiduLoginClientError("JSRPC 返回参数格式异常")

        params = EncryptedLoginParams.from_jsrpc(raw_params)
        if not params.username or not params.password:
            raise BaiduLoginClientError("未捕获到核心加密参数 username/password")

        logger.info("已捕获加密参数: username=%s chars, password=%s chars", len(params.username), len(params.password))
        return params

    async def get_aes_key(
        self,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> AESKeyResult:
        """获取页面中 PassMachine 的 AES 密钥。"""
        page = self._require_page()
        timeout_ms = self._to_timeout_ms(timeout_seconds)

        try:
            await page.wait_for_function(
                "() => window.baiduCrypto && typeof window.baiduCrypto.getAESKey === 'function'",
                timeout=timeout_ms,
            )

            # 等待到密钥可用，避免页面脚本尚未完全初始化。
            await page.wait_for_function(
                "() => !!window.baiduCrypto.getAESKey()",
                timeout=timeout_ms,
            )

            key = await page.evaluate("() => window.baiduCrypto.getAESKey()")
        except PlaywrightTimeoutError as exc:
            raise BaiduLoginTimeoutError(f"{timeout_seconds:.2f} 秒内未获取到 AES 密钥") from exc
        except PlaywrightError as exc:
            logger.exception("获取 AES 密钥失败")
            raise BaiduLoginClientError(f"获取 AES 密钥失败: {exc}") from exc

        if key is not None and not isinstance(key, str):
            raise BaiduLoginClientError("AES 密钥格式异常")

        result = AESKeyResult(key=key, available=bool(key))
        logger.info("AES 密钥获取结果: available=%s", result.available)
        return result

    async def _wait_jsrpc_ready(self, timeout_seconds: float) -> None:
        """等待注入 API 可用。"""
        page = self._require_page()
        timeout_ms = self._to_timeout_ms(timeout_seconds)
        try:
            await page.wait_for_function(
                """() => (
                    typeof window.baiduLogin !== 'undefined' &&
                    typeof window.baiduLogin.triggerLogin === 'function' &&
                    typeof window.baiduLogin.waitForParams === 'function' &&
                    typeof window.baiduCrypto !== 'undefined'
                )""",
                timeout=timeout_ms,
            )
        except PlaywrightTimeoutError as exc:
            raise BaiduLoginInjectionError("JSRPC 注入超时，页面未检测到 window.baiduLogin") from exc

    def _require_page(self) -> Page:
        """确保客户端已初始化。"""
        if self._page is None:
            raise BaiduLoginClientError("客户端未初始化，请先调用 start() 或使用 async with")
        return self._page

    @staticmethod
    def _to_timeout_ms(timeout_seconds: float) -> int:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0")
        return int(timeout_seconds * 1000)

    @staticmethod
    def _handle_console(msg: Any) -> None:
        # 仅记录页面级调试日志，避免业务流程被页面日志打断。
        logger.debug("[PAGE:%s] %s", getattr(msg, "type", "log"), msg.text)

    @staticmethod
    def _handle_page_error(error: Any) -> None:
        logger.warning("[PAGE ERROR] %s", error)

