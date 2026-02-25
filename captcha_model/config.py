"""训练配置文件。"""

# 训练配置
DATA_ROOT = r"D:\javatao\tao\data\img-ocr\trainnew"
BATCH_SIZE = 64
NUM_EPOCHS = 50
LEARNING_RATE = 3e-4
WEIGHT_DECAY = 1e-4
NUM_CLASSES = 100
IMG_SIZE = 224
DEVICE = "cuda"
SEED = 42
NUM_WORKERS = 4  # 设置页面文件后可改为 4 或 8

# 输出目录配置
CHECKPOINT_DIR = "checkpoints"
LOG_DIR = "logs"
ONNX_DIR = "onnx"
