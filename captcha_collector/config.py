"""数据收集配置文件。"""

import os

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 输出数据目录
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "collected")

# 模型路径（用于辅助预测，可选）
MODEL_PATH = os.path.join(PROJECT_ROOT, "captcha_model", "onnx", "captcha_effnet_b3.onnx")

# 模型配置（与 captcha_test/config.py 保持一致）
NUM_CLASSES = 100
IMG_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# 百度 API 配置
AK = "1e3f2dd1c81f2075171a547893391274"
REFERER = "https://example.com/"
API_TIMEOUT = 10

# 兼容 baidu_api.py 的变量名
API_AK = AK
API_REFERER = REFERER

# 穷举配置
# 步长探测序列 (10个固定点，覆盖 72°-300° 范围)
PROBE_STEPS = [20, 27, 34, 41, 48, 55, 62, 69, 76, 83]

# 请求控制
VERIFY_DELAY = 0.05              # 每次验证后等待时间 (秒)
CONTINUOUS_FAIL_LIMIT = 5        # 连续失败阈值
CONTINUOUS_FAIL_PAUSE = 30       # 连续失败后暂停时间 (秒)
NETWORK_RETRY = 3                # 网络错误重试次数
NETWORK_RETRY_DELAY = 2          # 网络错误重试间隔 (秒)

# 去重文件路径
HASH_FILE = os.path.join(OUTPUT_DIR, ".hashes.txt")

# 收集配置
TARGET_COUNT = 1000  # 目标收集数量
DELAY_BETWEEN_REQUESTS = 0.5  # 请求间隔（秒）
