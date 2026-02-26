"""百度登录完整使用示例。

演示如何使用 JSRPC 客户端 + 验证码识别 + 登录处理器完成自动化登录。
"""

import asyncio
import logging

from baidu_login import (
    BaiduCaptchaSolver,
    BaiduLoginHandler,
    BaiduLoginJSRPCClient,
    CaptchaSolverConfig,
    LoginResult,
    build_captcha_callback,
)

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """完整登录流程示例。"""
    # 配置
    username = "your_username"
    password = "your_password"

    # 1. 初始化 JSRPC 客户端（获取加密参数）
    jsrpc_client = BaiduLoginJSRPCClient(headless=False)

    # 2. 初始化验证码处理器
    captcha_solver = BaiduCaptchaSolver(
        config=CaptchaSolverConfig(
            model_path="captcha_model/onnx/captcha_effnet_b3.onnx",
            referer="https://wappass.baidu.com/",
        )
    )

    # 3. 构建验证码回调
    captcha_callback = build_captcha_callback(
        solver=captcha_solver,
        referer="https://wappass.baidu.com/",
    )

    # 4. 初始化登录处理器
    handler = BaiduLoginHandler(
        jsrpc_client=jsrpc_client,
        captcha_callback=captcha_callback,
    )

    try:
        # 5. 执行登录
        print(f"正在登录: {username}")
        result = await handler.login(username, password)

        # 6. 处理结果
        if result.success:
            print(f"登录成功！")
            print(f"BDUSS: {result.bduss}")
            print(f"重定向URL: {result.redirect_url}")
        elif result.captcha_required:
            print("需要验证码")
            print(f"验证码信息: {result.captcha_challenge}")
        else:
            print(f"登录失败: {result.error_message}")

    finally:
        await captcha_solver.close()


async def simple_example() -> None:
    """简化示例：仅获取加密参数。"""
    async with BaiduLoginJSRPCClient(headless=False) as client:
        # 获取 AES 密钥
        aes_result = await client.get_aes_key()
        print(f"AES 密钥: {aes_result.key}")

        # 获取加密参数
        params = await client.get_encrypted_params("test_user", "test_password")
        print(f"密码长度: {len(params.password)} 字符")
        print(f"用户名长度: {len(params.username)} 字符")
        print(f"签名: {params.sig[:30]}...")


if __name__ == "__main__":
    # 运行简化示例
    asyncio.run(simple_example())

    # 运行完整登录示例（需要真实账号）
    # asyncio.run(main())
