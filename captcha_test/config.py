"""项目配置文件。"""

# ONNX 模型路径
MODEL_PATH = r"D:/taotaoqwq/captcha_model/onnx/captcha_effnet_b3.onnx"

# 模型与输入配置（与训练/导出模型一致）
NUM_CLASSES = 100
IMG_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# 百度 API 配置
AK = "1e3f2dd1c81f2075171a547893391274"
SK = ""
REFERER = "https://example.com/"
API_BASE_URL = "https://example.com/api"
API_TIMEOUT = 10

# 兼容旧字段命名
API_AK = AK
API_SK = SK
API_REFERER = REFERER
