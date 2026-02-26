"""百度登录处理器。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
import inspect
import json
import logging
import time
from typing import Any, Awaitable, Callable, Literal, Mapping

import httpx

try:
    from .jsrpc_client import (
        DEFAULT_TIMEOUT_SECONDS,
        LOGIN_URL,
        BaiduLoginClientError,
        BaiduLoginJSRPCClient,
        EncryptedLoginParams,
    )
except ImportError:  # pragma: no cover - 兼容脚本直跑
    from jsrpc_client import (  # type: ignore[no-redef]
        DEFAULT_TIMEOUT_SECONDS,
        LOGIN_URL,
        BaiduLoginClientError,
        BaiduLoginJSRPCClient,
        EncryptedLoginParams,
    )


BAIDU_ANTI_REPLAY_ENDPOINT = "https://wappass.baidu.com/wp/api/security/antireplaytoken"
BAIDU_LOGIN_ENDPOINT = "https://wappass.baidu.com/wp/api/login"
DEFAULT_HTTP_TIMEOUT_SECONDS = 15.0
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
CAPTCHA_HINT_CODES = {"6", "120021", "500002", "500018", "401023"}

logger = logging.getLogger(__name__)


class BaiduLoginHandlerError(RuntimeError):
    """登录处理器基础异常。"""


class BaiduLoginRequestError(BaiduLoginHandlerError):
    """网络请求异常。"""


@dataclass(slots=True)
class RetryPolicy:
    """重试策略。"""

    max_attempts: int = 3
    backoff_seconds: float = 0.5
    max_backoff_seconds: float = 4.0

    def validate(self) -> None:
        """校验重试参数。"""
        if self.max_attempts <= 0:
            raise ValueError("max_attempts 必须大于 0")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds 不能小于 0")
        if self.max_backoff_seconds <= 0:
            raise ValueError("max_backoff_seconds 必须大于 0")


@dataclass(slots=True)
class AntiReplayToken:
    """防重放令牌。"""

    token: str | None = None
    servertime: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CaptchaChallenge:
    """验证码挑战信息。"""

    vcodestr: str | None = None
    code_string: str | None = None
    captcha_url: str | None = None
    prompt: str | None = None
    error_code: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CaptchaSolution:
    """验证码回调返回结果。"""

    verifycode: str
    vcodestr: str | None = None
    extras: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class LoginResult:
    """登录结果。"""

    status: Literal["success", "failed", "captcha_required", "error"]
    message: str
    success: bool
    bduss: str | None = None
    error_code: str | None = None
    response: Any = None
    captcha_challenge: CaptchaChallenge | None = None


@dataclass(slots=True)
class _ResponseAnalysis:
    """内部响应分析结果。"""

    status: Literal["success", "failed", "captcha_required"]
    message: str
    error_code: str | None
    bduss: str | None
    captcha_challenge: CaptchaChallenge | None


CaptchaCallback = Callable[
    [CaptchaChallenge],
    Awaitable[CaptchaSolution | Mapping[str, Any] | str | None]
    | CaptchaSolution
    | Mapping[str, Any]
    | str
    | None,
]


class BaiduLoginHandler:
    """百度登录处理器（异步）。"""

    def __init__(
        self,
        jsrpc_client: BaiduLoginJSRPCClient | None = None,
        *,
        login_url: str = LOGIN_URL,
        anti_replay_endpoint: str = BAIDU_ANTI_REPLAY_ENDPOINT,
        login_endpoint: str = BAIDU_LOGIN_ENDPOINT,
        user_agent: str = DEFAULT_USER_AGENT,
        referer: str | None = None,
        timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
        jsrpc_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        retry_policy: RetryPolicy | None = None,
        headless: bool = True,
    ) -> None:
        self._login_url = login_url
        self._anti_replay_endpoint = anti_replay_endpoint
        self._login_endpoint = login_endpoint
        self._user_agent = user_agent
        self._referer = referer or login_url
        self._timeout_seconds = timeout_seconds
        self._jsrpc_timeout_seconds = jsrpc_timeout_seconds

        self._retry_policy = retry_policy or RetryPolicy()
        self._retry_policy.validate()

        self._owns_jsrpc = jsrpc_client is None
        self._jsrpc_client = jsrpc_client or BaiduLoginJSRPCClient(
            login_url=login_url,
            timeout_seconds=jsrpc_timeout_seconds,
            headless=headless,
        )

        self._http_client: httpx.AsyncClient | None = None
        self._started = False

    async def __aenter__(self) -> "BaiduLoginHandler":
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    async def start(self) -> None:
        """初始化 HTTP 客户端和 JSRPC 客户端。"""
        if self._started:
            return

        self._http_client = httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
        )

        try:
            await self._jsrpc_client.start()
        except Exception:
            await self._safe_close_http_client()
            raise

        self._started = True

    async def close(self) -> None:
        """释放资源。"""
        await self._safe_close_http_client()

        if self._owns_jsrpc:
            await self._jsrpc_client.close()
        self._started = False

    async def login(
        self,
        username: str,
        password: str,
        *,
        captcha_callback: CaptchaCallback | None = None,
        max_captcha_attempts: int = 2,
        extra_form_data: Mapping[str, Any] | None = None,
    ) -> LoginResult:
        """
        执行登录流程。

        流程:
        1. 使用 JSRPC 触发并获取加密参数
        2. 请求 antireplaytoken
        3. 发送 /wp/api/login
        4. 根据结果处理成功、失败、验证码分支
        """
        if not username.strip():
            return LoginResult(
                status="error",
                message="username 不能为空",
                success=False,
                error_code="invalid_username",
            )
        if not password:
            return LoginResult(
                status="error",
                message="password 不能为空",
                success=False,
                error_code="invalid_password",
            )
        if max_captcha_attempts <= 0:
            return LoginResult(
                status="error",
                message="max_captcha_attempts 必须大于 0",
                success=False,
                error_code="invalid_captcha_attempts",
            )

        await self.start()
        try:
            encrypted_params = await self._jsrpc_client.get_encrypted_params(
                username=username.strip(),
                password=password,
                timeout_seconds=self._jsrpc_timeout_seconds,
            )
            anti_replay = await self._fetch_antireplay_token(encrypted_params)

            form_data = self._build_login_form_data(
                encrypted_params=encrypted_params,
                anti_replay=anti_replay,
                extra_form_data=extra_form_data,
            )

            response = await self._send_login_request(form_data)
            payload = self._decode_response_body(response)
            analysis = self._analyze_login_response(response=response, payload=payload)

            if analysis.status == "success":
                return LoginResult(
                    status="success",
                    message=analysis.message,
                    success=True,
                    bduss=analysis.bduss,
                    response=payload,
                )

            if analysis.status == "failed":
                return LoginResult(
                    status="failed",
                    message=analysis.message,
                    success=False,
                    error_code=analysis.error_code,
                    response=payload,
                )

            # 验证码分支：若无回调则直接返回挑战信息。
            challenge = analysis.captcha_challenge
            if challenge is None:
                challenge = CaptchaChallenge(prompt="需要验证码", raw={})

            if captcha_callback is None:
                return LoginResult(
                    status="captcha_required",
                    message=analysis.message,
                    success=False,
                    error_code=analysis.error_code,
                    response=payload,
                    captcha_challenge=challenge,
                )

            for attempt in range(1, max_captcha_attempts + 1):
                solution = await self._invoke_captcha_callback(captcha_callback, challenge)
                if solution is None:
                    return LoginResult(
                        status="captcha_required",
                        message="验证码回调未返回有效结果",
                        success=False,
                        error_code="captcha_callback_empty",
                        response=payload,
                        captcha_challenge=challenge,
                    )

                form_with_captcha = self._merge_captcha_solution(
                    base_form_data=form_data,
                    challenge=challenge,
                    solution=solution,
                )
                response = await self._send_login_request(form_with_captcha)
                payload = self._decode_response_body(response)
                analysis = self._analyze_login_response(response=response, payload=payload)

                if analysis.status == "success":
                    return LoginResult(
                        status="success",
                        message=analysis.message,
                        success=True,
                        bduss=analysis.bduss,
                        response=payload,
                    )
                if analysis.status == "failed":
                    return LoginResult(
                        status="failed",
                        message=analysis.message,
                        success=False,
                        error_code=analysis.error_code,
                        response=payload,
                    )

                challenge = analysis.captcha_challenge or challenge
                logger.info("验证码仍未通过，准备第 %s 次重试", attempt + 1)

            return LoginResult(
                status="captcha_required",
                message="验证码重试次数耗尽",
                success=False,
                error_code="captcha_attempts_exhausted",
                response=payload,
                captcha_challenge=challenge,
            )
        except BaiduLoginClientError as exc:
            logger.exception("JSRPC 处理失败")
            return LoginResult(
                status="error",
                message=f"JSRPC 处理失败: {exc}",
                success=False,
                error_code="jsrpc_error",
            )
        except BaiduLoginHandlerError as exc:
            logger.exception("登录处理失败")
            return LoginResult(
                status="error",
                message=str(exc),
                success=False,
                error_code="handler_error",
            )
        except Exception as exc:  # pragma: no cover - 兜底保护
            logger.exception("登录流程出现未预期异常")
            return LoginResult(
                status="error",
                message=f"未预期异常: {exc}",
                success=False,
                error_code="unexpected_error",
            )

    async def _fetch_antireplay_token(self, params: EncryptedLoginParams) -> AntiReplayToken:
        """请求防重放 token。"""
        response = await self._request_with_retry(
            method="GET",
            url=self._anti_replay_endpoint,
            params={
                "baiduId": params.baidu_id or "",
                "tpl": str(params.extras.get("tpl", "wise")),
                "tt": str(self._now_ms()),
            },
            headers=self._build_common_headers(),
        )

        if response.status_code >= 400:
            raise BaiduLoginRequestError(
                f"获取 antireplaytoken 失败，HTTP {response.status_code}"
            )

        payload = self._decode_response_body(response)
        if not isinstance(payload, dict):
            raise BaiduLoginRequestError("antireplaytoken 响应非 JSON 对象")

        errno = self._safe_str(
            self._find_first_value(payload, {"errno", "errNo", "err_no", "code"})
        )
        if errno not in (None, "", "0", "success"):
            message = self._safe_str(
                self._find_first_value(payload, {"msg", "errmsg", "message", "errMsg"})
            ) or "未知错误"
            raise BaiduLoginRequestError(f"antireplaytoken 返回错误: {errno}, {message}")

        token = self._safe_str(
            self._find_first_value(payload, {"antireplaytoken", "token", "tk"})
        )
        servertime = self._safe_str(
            self._find_first_value(payload, {"servertime", "serverTime", "server_time"})
        )

        return AntiReplayToken(token=token, servertime=servertime, raw=payload)

    async def _send_login_request(self, form_data: Mapping[str, str]) -> httpx.Response:
        """提交登录请求。"""
        return await self._request_with_retry(
            method="POST",
            url=self._login_endpoint,
            data=dict(form_data),
            headers={
                **self._build_common_headers(),
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": "https://wappass.baidu.com",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

    async def _request_with_retry(
        self,
        *,
        method: str,
        url: str,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """带指数退避的统一请求方法。"""
        if self._http_client is None:
            raise BaiduLoginHandlerError("HTTP 客户端未初始化")

        last_error: Exception | None = None
        for attempt in range(1, self._retry_policy.max_attempts + 1):
            try:
                response = await self._http_client.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    headers=headers,
                )
            except httpx.RequestError as exc:
                last_error = exc
                logger.warning(
                    "请求异常，第 %s/%s 次: %s %s -> %s",
                    attempt,
                    self._retry_policy.max_attempts,
                    method,
                    url,
                    exc,
                )
                if attempt >= self._retry_policy.max_attempts:
                    break
                await asyncio.sleep(self._retry_delay(attempt))
                continue

            if (
                response.status_code in RETRYABLE_HTTP_STATUS
                and attempt < self._retry_policy.max_attempts
            ):
                logger.warning(
                    "请求返回可重试状态码，第 %s/%s 次: %s %s -> %s",
                    attempt,
                    self._retry_policy.max_attempts,
                    method,
                    url,
                    response.status_code,
                )
                await asyncio.sleep(self._retry_delay(attempt))
                continue

            return response

        raise BaiduLoginRequestError(
            f"请求失败，已达到最大重试次数: {method} {url}, error={last_error}"
        )

    def _build_login_form_data(
        self,
        *,
        encrypted_params: EncryptedLoginParams,
        anti_replay: AntiReplayToken,
        extra_form_data: Mapping[str, Any] | None,
    ) -> dict[str, str]:
        """构造登录表单参数。"""
        form_data: dict[str, Any] = {
            "password": encrypted_params.password,
            "username": encrypted_params.username,
            "k": encrypted_params.k,
            "s": encrypted_params.s,
            "ds": encrypted_params.ds,
            "tk": encrypted_params.tk,
            "sig": encrypted_params.sig,
            "shaOne": encrypted_params.sha_one,
            "servertime": encrypted_params.servertime,
            "fuid": encrypted_params.fuid,
            "gid": encrypted_params.gid,
            "session_id": encrypted_params.session_id,
            "baiduId": encrypted_params.baidu_id,
        }
        form_data.update(encrypted_params.extras)

        # 仅在缺失时补充 antireplay 数据，避免破坏已有签名参数。
        if anti_replay.token:
            form_data.setdefault("token", anti_replay.token)
            form_data.setdefault("antireplaytoken", anti_replay.token)
        if anti_replay.servertime:
            form_data.setdefault("servertime", anti_replay.servertime)

        if extra_form_data:
            form_data.update(extra_form_data)

        return {
            key: str(value)
            for key, value in form_data.items()
            if value is not None and str(value) != ""
        }

    def _analyze_login_response(
        self,
        *,
        response: httpx.Response,
        payload: Any,
    ) -> _ResponseAnalysis:
        """识别登录响应状态。"""
        bduss = self._extract_bduss(response=response, payload=payload)

        # 优先识别验证码分支，避免误判为普通失败。
        if self._is_captcha_required(payload):
            challenge = self._extract_captcha_challenge(payload)
            return _ResponseAnalysis(
                status="captcha_required",
                message=self._extract_message(payload) or "需要验证码",
                error_code=self._extract_error_code(payload),
                bduss=bduss,
                captcha_challenge=challenge,
            )

        if bduss:
            return _ResponseAnalysis(
                status="success",
                message="登录成功",
                error_code=None,
                bduss=bduss,
                captcha_challenge=None,
            )

        if self._is_success_payload(payload):
            return _ResponseAnalysis(
                status="success",
                message=self._extract_message(payload) or "登录成功",
                error_code=None,
                bduss=None,
                captcha_challenge=None,
            )

        return _ResponseAnalysis(
            status="failed",
            message=self._extract_message(payload) or f"登录失败，HTTP {response.status_code}",
            error_code=self._extract_error_code(payload),
            bduss=None,
            captcha_challenge=None,
        )

    async def _invoke_captcha_callback(
        self,
        callback: CaptchaCallback,
        challenge: CaptchaChallenge,
    ) -> CaptchaSolution | None:
        """执行验证码回调并标准化返回值。"""
        raw = callback(challenge)
        if inspect.isawaitable(raw):
            raw = await raw

        if raw is None:
            return None

        if isinstance(raw, CaptchaSolution):
            if not raw.verifycode:
                return None
            return raw

        if isinstance(raw, str):
            code = raw.strip()
            if not code:
                return None
            return CaptchaSolution(
                verifycode=code,
                vcodestr=challenge.vcodestr or challenge.code_string,
            )

        if isinstance(raw, Mapping):
            verifycode = str(raw.get("verifycode") or raw.get("code") or "").strip()
            if not verifycode:
                return None
            vcodestr = raw.get("vcodestr") or raw.get("code_string") or challenge.vcodestr
            extras = {
                str(k): str(v)
                for k, v in raw.items()
                if k not in {"verifycode", "code", "vcodestr", "code_string"} and v is not None
            }
            return CaptchaSolution(
                verifycode=verifycode,
                vcodestr=str(vcodestr) if vcodestr else None,
                extras=extras,
            )

        raise BaiduLoginHandlerError("验证码回调返回类型不受支持")

    def _merge_captcha_solution(
        self,
        *,
        base_form_data: Mapping[str, str],
        challenge: CaptchaChallenge,
        solution: CaptchaSolution,
    ) -> dict[str, str]:
        """合并验证码参数。"""
        form_data = dict(base_form_data)
        form_data["verifycode"] = solution.verifycode

        code_str = solution.vcodestr or challenge.vcodestr or challenge.code_string
        if code_str:
            form_data["vcodestr"] = code_str
            form_data["codeString"] = code_str

        for key, value in solution.extras.items():
            if value:
                form_data[key] = value
        return form_data

    def _decode_response_body(self, response: httpx.Response) -> Any:
        """解析响应体，优先 JSON。"""
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            try:
                return response.json()
            except ValueError:
                return response.text

        text = response.text
        if not text:
            return {}
        try:
            return json.loads(text)
        except ValueError:
            return text

    def _build_common_headers(self) -> dict[str, str]:
        """构建公共请求头。"""
        return {
            "User-Agent": self._user_agent,
            "Referer": self._referer,
            "Accept": "application/json, text/plain, */*",
        }

    async def _safe_close_http_client(self) -> None:
        """安全关闭 HTTP 客户端。"""
        if self._http_client is not None:
            try:
                await self._http_client.aclose()
            finally:
                self._http_client = None

    def _retry_delay(self, attempt: int) -> float:
        """计算指数退避时长。"""
        delay = self._retry_policy.backoff_seconds * (2 ** (attempt - 1))
        return min(delay, self._retry_policy.max_backoff_seconds)

    def _extract_bduss(self, *, response: httpx.Response, payload: Any) -> str | None:
        """提取 BDUSS。"""
        cookie_bduss = response.cookies.get("BDUSS")
        if cookie_bduss:
            return cookie_bduss

        set_cookie_items = response.headers.get_list("set-cookie")
        for set_cookie in set_cookie_items:
            jar = SimpleCookie()
            jar.load(set_cookie)
            if "BDUSS" in jar:
                return jar["BDUSS"].value

        if isinstance(payload, dict):
            value = self._find_first_value(payload, {"BDUSS", "bduss", "bdus"})
            if value is not None:
                value_str = str(value).strip()
                if value_str:
                    return value_str
        return None

    def _is_success_payload(self, payload: Any) -> bool:
        """根据响应 JSON 判断是否成功。"""
        if not isinstance(payload, dict):
            return False

        errno = self._safe_str(
            self._find_first_value(payload, {"errno", "errNo", "err_no", "code", "no"})
        )
        if errno in {"0", "success", "ok"}:
            return True

        err_info = payload.get("errInfo")
        if isinstance(err_info, dict):
            no = self._safe_str(err_info.get("no"))
            if no in {"0", "success", "ok"}:
                return True
        return False

    def _is_captcha_required(self, payload: Any) -> bool:
        """判断是否进入验证码流程。"""
        if isinstance(payload, dict):
            if self._find_first_value(
                payload,
                {"vcodestr", "verifycode", "codeString", "codestring", "captcha", "captchaUrl"},
            ):
                return True

            error_code = self._extract_error_code(payload)
            if error_code in CAPTCHA_HINT_CODES:
                return True

            message = (self._extract_message(payload) or "").lower()
            if "验证码" in message or "captcha" in message:
                return True

        if isinstance(payload, str):
            text = payload.lower()
            return "验证码" in payload or "captcha" in text
        return False

    def _extract_captcha_challenge(self, payload: Any) -> CaptchaChallenge:
        """提取验证码挑战字段。"""
        if not isinstance(payload, dict):
            return CaptchaChallenge(prompt="需要验证码", raw={})

        vcodestr = self._safe_str(self._find_first_value(payload, {"vcodestr"}))
        code_string = self._safe_str(
            self._find_first_value(payload, {"codeString", "codestring", "code_string"})
        )
        captcha_url = self._safe_str(
            self._find_first_value(payload, {"captchaUrl", "captcha_url", "img", "imgUrl"})
        )
        message = self._extract_message(payload) or "需要验证码"

        return CaptchaChallenge(
            vcodestr=vcodestr,
            code_string=code_string,
            captcha_url=captcha_url,
            prompt=message,
            error_code=self._extract_error_code(payload),
            raw=payload,
        )

    def _extract_message(self, payload: Any) -> str | None:
        """提取错误/提示消息。"""
        if not isinstance(payload, dict):
            return str(payload) if isinstance(payload, str) and payload else None

        msg = self._find_first_value(
            payload,
            {"msg", "errmsg", "errMsg", "message", "tips", "error_msg", "errorMsg"},
        )
        if msg is not None:
            text = str(msg).strip()
            if text:
                return text

        err_info = payload.get("errInfo")
        if isinstance(err_info, dict):
            info_msg = err_info.get("msg") or err_info.get("message")
            if info_msg:
                return str(info_msg)
        return None

    def _extract_error_code(self, payload: Any) -> str | None:
        """提取错误码。"""
        if not isinstance(payload, dict):
            return None

        code = self._find_first_value(
            payload,
            {"errno", "errNo", "err_no", "code", "error", "error_code"},
        )
        if code is not None:
            return str(code)

        err_info = payload.get("errInfo")
        if isinstance(err_info, dict) and err_info.get("no") is not None:
            return str(err_info.get("no"))
        return None

    @classmethod
    def _find_first_value(cls, payload: Any, keys: set[str]) -> Any:
        """在任意嵌套结构里按 key 查找第一个非空值。"""
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
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)


__all__ = [
    "AntiReplayToken",
    "BaiduLoginHandler",
    "BaiduLoginHandlerError",
    "BaiduLoginRequestError",
    "CaptchaChallenge",
    "CaptchaSolution",
    "LoginResult",
    "RetryPolicy",
]
