"""百度登录 Flask 代理服务。"""

from __future__ import annotations

import asyncio
import atexit
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import asdict, dataclass
import logging
import threading
from typing import Any, ClassVar

from flask import Flask, jsonify, request
import httpx

try:
    from .jsrpc_client import (
        DEFAULT_TIMEOUT_SECONDS,
        LOGIN_URL,
        BaiduLoginClientError,
        BaiduLoginInjectionError,
        BaiduLoginJSRPCClient,
        BaiduLoginTimeoutError,
        EncryptedLoginParams,
    )
except ImportError:  # pragma: no cover - 兼容直接运行脚本
    from jsrpc_client import (  # type: ignore[no-redef]
        DEFAULT_TIMEOUT_SECONDS,
        LOGIN_URL,
        BaiduLoginClientError,
        BaiduLoginInjectionError,
        BaiduLoginJSRPCClient,
        BaiduLoginTimeoutError,
        EncryptedLoginParams,
    )


BAIDU_LOGIN_ENDPOINT = "https://wappass.baidu.com/wp/api/login"
DEFAULT_HTTP_TIMEOUT_SECONDS = 15.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BaseResponse:
    """统一响应基类。"""

    status: str

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化字典。"""
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


@dataclass(slots=True)
class EncryptResponse(BaseResponse):
    """加密参数响应。"""

    params: dict[str, Any]
    login_response: dict[str, Any] | None = None


@dataclass(slots=True)
class AESKeyResponse(BaseResponse):
    """AES 密钥响应。"""

    key: str


@dataclass(slots=True)
class HealthResponse(BaseResponse):
    """健康检查响应。"""


@dataclass(slots=True)
class ErrorResponse(BaseResponse):
    """错误响应。"""

    error: str
    message: str
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class EncryptRequest:
    """加密接口请求参数。"""

    username: str
    password: str
    forward_login: bool = False


class APIError(Exception):
    """API 业务异常。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        error_code: str = "bad_request",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details


class JSRPCClientSingleton:
    """JSRPC 客户端单例，内部维护独立事件循环线程。"""

    _instance: ClassVar["JSRPCClientSingleton | None"] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, *, headless: bool, timeout_seconds: float) -> None:
        self._headless = headless
        self._timeout_seconds = timeout_seconds

        self._client = BaiduLoginJSRPCClient(
            timeout_seconds=timeout_seconds,
            headless=headless,
        )

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = False

        self._startup_lock = threading.Lock()
        self._request_lock = threading.Lock()

    @classmethod
    def get_instance(
        cls,
        *,
        headless: bool,
        timeout_seconds: float,
    ) -> "JSRPCClientSingleton":
        """获取单例。"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(headless=headless, timeout_seconds=timeout_seconds)
        return cls._instance

    def get_encrypted_params(
        self,
        username: str,
        password: str,
        *,
        timeout_seconds: float,
    ) -> EncryptedLoginParams:
        """同步获取加密参数。"""
        self._ensure_started()
        with self._request_lock:
            return self._run_coroutine(
                self._client.get_encrypted_params(
                    username=username,
                    password=password,
                    timeout_seconds=timeout_seconds,
                ),
                timeout=timeout_seconds + 5.0,
            )

    def get_aes_key(self, *, timeout_seconds: float) -> str | None:
        """同步获取 AES 密钥。"""
        self._ensure_started()
        with self._request_lock:
            result = self._run_coroutine(
                self._client.get_aes_key(timeout_seconds=timeout_seconds),
                timeout=timeout_seconds + 5.0,
            )
            return result.key

    def close(self) -> None:
        """关闭单例中的浏览器与事件循环资源。"""
        with self._startup_lock:
            if self._loop is None:
                return

            if self._started:
                try:
                    self._run_coroutine(self._client.close(), timeout=10.0)
                except Exception:
                    logger.exception("关闭 JSRPC 客户端失败")
                finally:
                    self._started = False

            if self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)

            if self._thread is not None:
                self._thread.join(timeout=5.0)

            self._thread = None
            self._loop = None

    def _ensure_started(self) -> None:
        """懒加载初始化浏览器客户端。"""
        self._ensure_loop()
        if self._started:
            return

        with self._startup_lock:
            if self._started:
                return
            logger.info("初始化 JSRPC 单例客户端")
            self._run_coroutine(self._client.start(), timeout=60.0)
            self._started = True

    def _ensure_loop(self) -> None:
        """确保后台事件循环线程可用。"""
        if self._loop is not None and self._thread is not None and self._thread.is_alive():
            return

        with self._startup_lock:
            if self._loop is not None and self._thread is not None and self._thread.is_alive():
                return

            ready_event = threading.Event()
            init_error: list[BaseException] = []

            def _loop_runner() -> None:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    self._loop = loop
                    ready_event.set()
                    loop.run_forever()
                    loop.close()
                except BaseException as exc:  # pragma: no cover - 极端线程启动失败
                    init_error.append(exc)
                    ready_event.set()

            self._thread = threading.Thread(target=_loop_runner, name="baidu-jsrpc-loop", daemon=True)
            self._thread.start()
            ready_event.wait(timeout=5.0)

            if init_error:
                raise RuntimeError("后台事件循环启动失败") from init_error[0]
            if self._loop is None:
                raise RuntimeError("后台事件循环未初始化")

    def _run_coroutine(self, coroutine: Any, *, timeout: float) -> Any:
        """在线程安全上下文执行协程并同步返回结果。"""
        if self._loop is None:
            raise RuntimeError("事件循环未就绪")

        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError as exc:
            future.cancel()
            raise BaiduLoginTimeoutError(f"操作超时: {timeout:.2f}s") from exc


def _parse_encrypt_request(payload: Any) -> EncryptRequest:
    """解析并校验 /api/encrypt 请求体。"""
    if not isinstance(payload, dict):
        raise APIError("请求体必须为 JSON 对象", status_code=400, error_code="invalid_json")

    username = payload.get("username")
    password = payload.get("password")
    forward_login = payload.get("forward_login", False)

    if not isinstance(username, str) or not username.strip():
        raise APIError("字段 username 不能为空", status_code=400, error_code="invalid_username")
    if not isinstance(password, str) or not password:
        raise APIError("字段 password 不能为空", status_code=400, error_code="invalid_password")
    if not isinstance(forward_login, bool):
        raise APIError(
            "字段 forward_login 必须为布尔值",
            status_code=400,
            error_code="invalid_forward_login",
        )

    return EncryptRequest(
        username=username.strip(),
        password=password,
        forward_login=forward_login,
    )


def _encrypted_params_to_dict(params: EncryptedLoginParams) -> dict[str, Any]:
    """转换加密参数对象为接口响应数据。"""
    data: dict[str, Any] = {
        "password": params.password,
        "username": params.username,
        "k": params.k,
        "s": params.s,
        "ds": params.ds,
        "tk": params.tk,
        "sig": params.sig,
        "shaOne": params.sha_one,
        "servertime": params.servertime,
        "fuid": params.fuid,
        "gid": params.gid,
        "session_id": params.session_id,
        "baiduId": params.baidu_id,
    }
    data.update(params.extras)
    return {key: value for key, value in data.items() if value is not None}


def _build_login_form_data(params_dict: dict[str, Any]) -> dict[str, str]:
    """构造提交给百度登录接口的表单数据。"""
    return {key: str(value) for key, value in params_dict.items() if value is not None}


def _send_login_request(
    *,
    endpoint: str,
    params_dict: dict[str, Any],
    timeout_seconds: float,
    user_agent: str,
    referer: str,
) -> dict[str, Any]:
    """使用 httpx 向百度登录接口发送请求。"""
    headers = {
        "User-Agent": user_agent,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": referer,
    }
    form_data = _build_login_form_data(params_dict)

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.post(endpoint, data=form_data, headers=headers)
    except httpx.HTTPError as exc:
        raise APIError(
            f"转发登录请求失败: {exc}",
            status_code=502,
            error_code="baidu_request_failed",
        ) from exc

    content_type = response.headers.get("content-type", "")
    body: Any
    if "application/json" in content_type.lower():
        try:
            body = response.json()
        except ValueError:
            body = response.text
    else:
        body = response.text

    return {
        "status_code": response.status_code,
        "headers": {"content-type": content_type},
        "body": body,
    }


def _setup_logging(app: Flask) -> None:
    """初始化日志配置。"""
    level_name = str(app.config.get("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    app.logger.setLevel(level)


def _get_client_manager(app: Flask) -> JSRPCClientSingleton:
    """从 Flask 扩展中获取 JSRPC 单例管理器。"""
    manager = app.extensions.get("jsrpc_manager")
    if isinstance(manager, JSRPCClientSingleton):
        return manager

    manager = JSRPCClientSingleton.get_instance(
        headless=bool(app.config["PLAYWRIGHT_HEADLESS"]),
        timeout_seconds=float(app.config["JSRPC_TIMEOUT_SECONDS"]),
    )
    app.extensions["jsrpc_manager"] = manager
    return manager


def create_app(config: dict[str, Any] | None = None) -> Flask:
    """Flask 应用工厂。"""
    app = Flask(__name__)
    app.config.from_mapping(
        JSRPC_TIMEOUT_SECONDS=DEFAULT_TIMEOUT_SECONDS,
        PLAYWRIGHT_HEADLESS=True,
        HTTP_TIMEOUT_SECONDS=DEFAULT_HTTP_TIMEOUT_SECONDS,
        BAIDU_LOGIN_ENDPOINT=BAIDU_LOGIN_ENDPOINT,
        BAIDU_USER_AGENT=DEFAULT_USER_AGENT,
        BAIDU_REFERER=LOGIN_URL,
        LOG_LEVEL="INFO",
    )
    if config:
        app.config.update(config)

    _setup_logging(app)

    @app.get("/health")
    def health() -> tuple[Any, int]:
        """健康检查接口。"""
        resp = HealthResponse(status="ok")
        return jsonify(resp.to_dict()), 200

    @app.get("/api/aes-key")
    def get_aes_key() -> tuple[Any, int]:
        """获取页面 AES 密钥。"""
        manager = _get_client_manager(app)
        key = manager.get_aes_key(timeout_seconds=float(app.config["JSRPC_TIMEOUT_SECONDS"]))
        if not key:
            raise APIError(
                "AES 密钥暂不可用，请稍后重试",
                status_code=503,
                error_code="aes_key_unavailable",
            )

        resp = AESKeyResponse(status="success", key=key)
        return jsonify(resp.to_dict()), 200

    @app.post("/api/encrypt")
    def encrypt() -> tuple[Any, int]:
        """获取加密参数，可选转发登录请求。"""
        req = _parse_encrypt_request(request.get_json(silent=True))
        manager = _get_client_manager(app)

        params_obj = manager.get_encrypted_params(
            username=req.username,
            password=req.password,
            timeout_seconds=float(app.config["JSRPC_TIMEOUT_SECONDS"]),
        )
        params_dict = _encrypted_params_to_dict(params_obj)

        login_response: dict[str, Any] | None = None
        if req.forward_login:
            login_response = _send_login_request(
                endpoint=str(app.config["BAIDU_LOGIN_ENDPOINT"]),
                params_dict=params_dict,
                timeout_seconds=float(app.config["HTTP_TIMEOUT_SECONDS"]),
                user_agent=str(app.config["BAIDU_USER_AGENT"]),
                referer=str(app.config["BAIDU_REFERER"]),
            )

        resp = EncryptResponse(
            status="success",
            params=params_dict,
            login_response=login_response,
        )
        return jsonify(resp.to_dict()), 200

    @app.errorhandler(APIError)
    def handle_api_error(error: APIError) -> tuple[Any, int]:
        """业务异常响应。"""
        app.logger.warning("APIError: %s", error.message)
        resp = ErrorResponse(
            status="error",
            error=error.error_code,
            message=error.message,
            details=error.details,
        )
        return jsonify(resp.to_dict()), error.status_code

    @app.errorhandler(BaiduLoginTimeoutError)
    def handle_timeout(error: BaiduLoginTimeoutError) -> tuple[Any, int]:
        """JSRPC 超时响应。"""
        app.logger.warning("JSRPC timeout: %s", error)
        resp = ErrorResponse(
            status="error",
            error="jsrpc_timeout",
            message=str(error),
        )
        return jsonify(resp.to_dict()), 504

    @app.errorhandler(BaiduLoginInjectionError)
    def handle_injection_error(error: BaiduLoginInjectionError) -> tuple[Any, int]:
        """注入异常响应。"""
        app.logger.error("JSRPC injection error: %s", error)
        resp = ErrorResponse(
            status="error",
            error="jsrpc_injection_failed",
            message=str(error),
        )
        return jsonify(resp.to_dict()), 502

    @app.errorhandler(BaiduLoginClientError)
    def handle_client_error(error: BaiduLoginClientError) -> tuple[Any, int]:
        """客户端异常响应。"""
        app.logger.error("JSRPC client error: %s", error)
        resp = ErrorResponse(
            status="error",
            error="jsrpc_client_error",
            message=str(error),
        )
        return jsonify(resp.to_dict()), 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> tuple[Any, int]:
        """兜底异常响应。"""
        app.logger.exception("Unexpected error: %s", error)
        resp = ErrorResponse(
            status="error",
            error="internal_error",
            message="服务内部错误",
        )
        return jsonify(resp.to_dict()), 500

    return app


def _cleanup_singleton() -> None:
    """进程退出时清理单例资源。"""
    singleton = JSRPCClientSingleton._instance
    if singleton is not None:
        singleton.close()


atexit.register(_cleanup_singleton)

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
