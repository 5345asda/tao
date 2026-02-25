"""百度旋转验证码模型测试主程序。"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock

from baidu_api import BaiduCaptchaAPI
from config import NUM_CLASSES
from model import CaptchaModel

# 统计锁
stats_lock = Lock()
total_count = 0
success_count = 0


def run_single_test(api: BaiduCaptchaAPI, model: CaptchaModel, test_id: int) -> bool:
    """执行单次测试。

    Args:
        api: 百度 API 实例
        model: 模型实例
        test_id: 测试编号

    Returns:
        验证是否成功
    """
    global total_count, success_count

    try:
        # 1. 初始化获取 tk, as
        init_data = api.get_init()
        tk = init_data["tk"]
        as_token = init_data["as"]

        # 2. 获取验证码图片
        style_data = api.get_style(tk)
        img_url = style_data["img_url"]
        backstr = style_data["backstr"]

        # 3. 下载图片
        img_bytes = api.get_image(img_url)

        # 4. 模型预测
        result = model.predict_from_bytes(img_bytes)
        angle = result["angle"]
        class_idx = result["class_index"]
        confidence = result["confidence"]

        # 5. 验证
        is_success = api.verify(tk, as_token, backstr, class_idx)

        # 6. 更新统计
        with stats_lock:
            total_count += 1
            if is_success:
                success_count += 1

        # 7. 打印结果
        timestamp = datetime.now().strftime("%H:%M:%S")
        status = "[OK] 成功" if is_success else "[X] 失败"
        print(f"[{timestamp}] 预测: {angle:.1f} (idx:{class_idx}) | 验证: {status} | 置信度: {confidence:.2f}")

        return is_success

    except Exception as e:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] 测试 #{test_id} 异常: {e}")
        return False


def main():
    """主函数。"""
    print("=" * 60)
    print("Baidu Rotate Captcha Model Test")
    print("=" * 60)
    print(f"Num Classes: {NUM_CLASSES} (each class {360/NUM_CLASSES:.1f} deg)")
    print("Press Ctrl+C to stop")
    print("-" * 60)

    # 初始化
    model = CaptchaModel()
    api = BaiduCaptchaAPI()

    # 线程数
    num_threads = 5

    try:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            test_id = 0
            futures = []

            while True:
                test_id += 1
                future = executor.submit(run_single_test, api, model, test_id)
                futures.append(future)

                # 清理已完成的 future
                futures = [f for f in futures if not f.done()]

                # 稍微控制一下速度
                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n" + "-" * 60)
        print("测试已停止")
        print("-" * 60)

    finally:
        # 打印统计
        if total_count > 0:
            rate = success_count / total_count * 100
            print(f"统计: 成功 {success_count}/{total_count} ({rate:.1f}%)")


if __name__ == "__main__":
    main()
