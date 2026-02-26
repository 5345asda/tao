# 验证码数据收集器

穷举式收集百度旋转验证码训练数据。

## 工作原理

1. **步长探测**: 使用 10 个固定探测点快速定位成功角度
2. **边界扩展**: 从成功角度向左右扩展，找到完整有效范围
3. **MD5 去重**: 防止重复收集相同图片
4. **多标签保存**: 兼容 captcha_model 训练格式

## 使用方法

```bash
cd captcha_collector

# 穷举模式（推荐）
python collector.py --mode exhaustive --num 100

# 智能模式（需要模型）
python collector.py --mode smart --num 50

# 指定输出目录
python collector.py --mode exhaustive --num 100 --output /path/to/output
```

## 输出格式

```
data/collected/
├── 20_21_22_23_24_25_26/           # 多标签目录
│   └── 20260226_093015_abc12345.jpg
├── 45_46_47_48_49_50_51/
│   └── 20260226_093016_def67890.jpg
└── .hashes.txt                      # MD5 去重文件
```

## 配置说明

编辑 `config.py`:

| 配置项 | 默认值 | 说明 |
|-------|--------|------|
| PROBE_STEPS | [20,27,34,41,48,55,62,69,76,83] | 探测序列 |
| VERIFY_DELAY | 0.05 | 验证间隔(秒) |
| TARGET_COUNT | 1000 | 目标收集数量 |
| CONTINUOUS_FAIL_LIMIT | 5 | 连续失败阈值 |
| CONTINUOUS_FAIL_PAUSE | 30 | 失败暂停时间(秒) |
| NETWORK_RETRY | 3 | 网络错误重试次数 |

## 文件说明

| 文件 | 说明 |
|------|------|
| config.py | 配置文件 |
| collector.py | 主收集器（ExhaustiveCollector, SmartDataCollector） |
| dedup.py | MD5 去重管理器 |
| baidu_api.py | 百度验证码 API 封装 |
| crypto.py | 请求加密模块 |
| test_collector.py | 单元测试 |
