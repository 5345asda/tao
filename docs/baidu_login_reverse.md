# 百度移动端登录接口逆向分析报告

## 一、概述

**目标**: 分析百度移动端登录页面 (`wappass.baidu.com`) 的加密算法和登录流程

**分析方法**: Chrome DevTools MCP + 网络请求监控 + JS Hook

**分析日期**: 2026-02-26

---

## 二、目标 URL

```
https://wappass.baidu.com/passport/?login&tpl=wise&sms=1&regtype=1&u=https%3A%2F%2Fwww.baidu.com%2F&extrajson=%7b%22src%22%3a%22se_000000%22%7d#/password_login
```

**移动端 UA**:
```
Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1
```

---

## 三、关键 JS 文件

| 文件 | 用途 |
|------|------|
| `vendor.c7ed8022.js` | 核心库（含加密函数） |
| `app.e51d2958.js` | 应用逻辑 |
| `password_login.65271740.js` | 密码登录模块 |
| `fingerprint.js` | 设备指纹 |
| `mkd_v2.js` | 风控 SDK |
| `bundle.js` (hercules) | 通用认证模块 |

---

## 四、核心 API 接口

### 4.1 登录配置
```
POST https://wappass.baidu.com/v8/sdkconfig/loginconfig
```

### 4.2 账号检查
```
POST https://wappass.baidu.com/v3/login/api/check

Request Body (JSON):
{
  "tpl": "wise",
  "gid": "A9F8E4C-9536-4F26-B539-BB7E6E31A2E7",
  "session_id": "...",
  "account": "BASE64_ENCODED_USERNAME",
  "acct_crypt": 20,
  "baiduId": "...",
  ...
}
```

### 4.3 防重放令牌
```
GET https://wappass.baidu.com/wp/api/security/antireplaytoken?baiduId=...&tpl=wise&tt=...
```

### 4.4 验证码初始化
```
POST https://passport.baidu.com/cap/init
```

### 4.5 主登录接口
```
POST https://wappass.baidu.com/wp/api/login

Content-Type: application/x-www-form-urlencoded
```

---

## 五、加密参数分析

### 5.1 登录请求参数

| 参数 | 格式 | 说明 |
|------|------|------|
| `password` | 256位十六进制 | 加密后的密码 |
| `username` | 256位十六进制 | 加密后的用户名 |
| `k` | Base64 | 密钥参数 |
| `s` | Base64 | 签名参数 |
| `ds` | Base64 | 数据签名 |
| `tk` | URL编码 | Token |
| `sig` | Base64 | 请求签名 |
| `shaOne` | 40位十六进制 | SHA1 哈希 |
| `servertime` | 8位十六进制 | 服务器时间戳 |
| `fuid` | Base64 | 设备指纹 |

### 5.2 密码加密特征

**观察到的加密结果**:
```
password=3516c9051bd8ae634ad69d78791bca1463721faeb1b0e3adbb66a867b0eeaa0c...
```

- 长度: 256位十六进制 = 128字节 = 1024位
- 每次请求值不同（包含随机数/时间戳）
- 疑似 RSA-1024 或 AES + RSA 组合加密

### 5.3 用户名加密特征

**观察到的加密结果**:
```
username=4c322d44d412e728f4a2bbe0efcecb3446414239ee67bf0c9970b098f462e83e...
```

- 长度: 256位十六进制
- 相同输入每次输出不同

---

## 六、加密函数定位

### 6.1 调用栈分析

通过 XHR Hook 捕获到的调用栈:
```
XMLHttpRequest.send
  └── e.send (vendor.c7ed8022.js:18:92725)
      └── Promise (vendor.c7ed8022.js:44:36931)
          └── _ (vendor.c7ed8022.js:44:35250)
              └── (app.e51d2958.js:1:2334)
```

### 6.2 可用的加密库

页面加载了 **CryptoJS**，包含以下算法:
- AES, DES, TripleDES
- SHA1, SHA256, SHA384, SHA512, SHA3
- MD5, RIPEMD160
- PBKDF2, EvpKDF

**注意**: CryptoJS 未被用于登录密码加密，加密使用其他方式（可能是自定义 RSA 实现）

### 6.3 已定位的加密函数

#### 验证码数据加密 (AES-ECB)

```javascript
// 位置: window.PassMachine.haveMkd.encrypt
// 用途: 加密验证码相关数据

PassMachine.haveMkd.encrypt = function(e) {
    var t = this.store.nameL + this.store.nameR;  // 密钥
    var n = PassMachine.CryptoJS.enc.Utf8.parse(t);
    var i = PassMachine.CryptoJS.enc.Utf8.parse(e);
    var r = PassMachine.CryptoJS.AES.encrypt(i, n, {
        mode: PassMachine.CryptoJS.mode.ECB,
        padding: PassMachine.CryptoJS.pad.Pkcs7
    });
    return r.toString();
}

// 密钥示例: nameL="619bc882", nameR="appsapi0"
// 完整密钥: "619bc882appsapi0"
```

#### 登录密码加密

- **格式**: 256位十六进制 (128字节)
- **算法**: 疑似 RSA-1024
- **位置**: `vendor.c7ed8022.js` 的 webpack 模块中
- **状态**: 代码混淆，需要进一步分析

### 6.4 Vue 组件方法

登录组件 (`/password_login`) 的关键方法:
- `handleSubmit()` - 表单提交入口
- `handleLoginfn()` - 登录执行逻辑
- `handleSubmitResult()` - 结果处理

### 6.5 关键全局对象

```
window.Pass
├── CryptoJS          # CryptoJS 实例
├── publicFn          # 公共函数
├── client            # 客户端相关
└── moduleList        # 模块列表

window.PassMachine
├── CryptoJS          # 独立的 CryptoJS 实例
├── haveMkd           # 验证码加密模块
│   ├── encrypt()     # AES-ECB 加密
│   └── store         # 密钥存储
└── mkd               # 风控模块
```

---

## 七、实现方案建议

### 方案 A: 浏览器自动化（推荐）

**优点**: 无需逆向加密算法，稳定性高
**缺点**: 资源占用较高

```python
# 使用 Playwright 模拟登录
from playwright.sync_api import sync_playwright

def login_with_playwright(username, password):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            **p.devices['iPhone 15'],
            locale='zh-CN'
        )
        page = context.new_page()
        page.goto('https://wappass.baidu.com/passport/?login&tpl=wise...')

        # 填写表单
        page.fill('input[placeholder*="手机号"]', username)
        page.fill('input[placeholder*="密码"]', password)
        page.click('button:has-text("登")')

        # 等待登录结果
        # ...
```

### 方案 B: JSRPC 注入（推荐）

**优点**: 可复用浏览器加密能力，无需完整逆向
**缺点**: 需要维护浏览器连接

#### B.1 XHR 拦截方案

在登录请求发送前拦截并获取加密参数:

```javascript
// JSRPC 注入代码 - 在登录页面注入
(function() {
    'use strict';

    // 存储加密后的登录参数
    window._baiduLoginParams = null;

    // Hook XMLHttpRequest
    const originalSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(body) {
        // 检测登录请求
        if (this._url && this._url.includes('/wp/api/login')) {
            try {
                // 解析并存储登录参数
                const params = {};
                body.split('&').forEach(pair => {
                    const [key, value] = pair.split('=');
                    params[decodeURIComponent(key)] = decodeURIComponent(value || '');
                });

                window._baiduLoginParams = {
                    password: params.password,
                    username: params.username,
                    k: params.k,
                    s: params.s,
                    ds: params.ds,
                    tk: params.tk,
                    sig: params.sig,
                    shaOne: params.shaOne,
                    servertime: params.servertime,
                    fuid: params.fuid,
                    gid: params.gid,
                    session_id: params.session_id,
                    baiduId: params.baiduId
                };

                console.log('[JSRPC] Login params captured:', window._baiduLoginParams);
            } catch(e) {
                console.error('[JSRPC] Parse error:', e);
            }
        }
        return originalSend.apply(this, arguments);
    };

    // Hook open 方法获取 URL
    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        this._url = url;
        return originalOpen.apply(this, arguments);
    };

    console.log('[JSRPC] Baidu login hook installed');
})();

// 获取加密参数的 RPC 接口
window.getBaiduLoginParams = function() {
    return window._baiduLoginParams;
};
```

#### B.2 表单触发方案

通过程序化触发登录流程来获取加密参数:

```javascript
// JSRPC 注入代码 - 触发登录并获取参数
(function() {
    'use strict';

    window.baiduLogin = {
        // 获取当前加密参数
        getEncryptedParams: function() {
            return window._baiduLoginParams;
        },

        // 填写并触发登录
        triggerLogin: function(username, password) {
            // 清除上次参数
            window._baiduLoginParams = null;

            // 填写表单
            const userInput = document.querySelector('input[placeholder*="手机号"]') ||
                              document.querySelector('input[placeholder*="用户名"]');
            const passInput = document.querySelector('input[placeholder*="密码"]') ||
                              document.querySelector('input[type="password"]');

            if (userInput) {
                userInput.value = username;
                userInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
            if (passInput) {
                passInput.value = password;
                passInput.dispatchEvent(new Event('input', { bubbles: true }));
            }

            // 勾选协议
            const checkbox = document.querySelector('input[type="checkbox"]');
            if (checkbox && !checkbox.checked) {
                checkbox.click();
            }

            // 点击登录按钮
            setTimeout(() => {
                const loginBtn = document.querySelector('button');
                if (loginBtn && !loginBtn.disabled) {
                    loginBtn.click();
                }
            }, 100);

            return { status: 'triggered' };
        },

        // 等待加密参数生成
        waitForParams: function(timeout = 5000) {
            return new Promise((resolve, reject) => {
                const startTime = Date.now();
                const check = () => {
                    if (window._baiduLoginParams) {
                        resolve(window._baiduLoginParams);
                    } else if (Date.now() - startTime > timeout) {
                        reject(new Error('Timeout waiting for login params'));
                    } else {
                        setTimeout(check, 100);
                    }
                };
                check();
            });
        }
    };

    console.log('[JSRPC] Baidu login module loaded');
})();
```

#### B.3 Flask 代理服务

```python
# flask_proxy.py
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# JSRPC 客户端 (需要安装 js2py 或使用 selenium)
class JSRPCClient:
    def __init__(self, browser_endpoint):
        self.endpoint = browser_endpoint

    def execute_js(self, script):
        """在浏览器中执行 JS 并返回结果"""
        # 实现方式: WebSocket / HTTP + Selenium / Playwright
        pass

    def get_login_params(self):
        """获取加密后的登录参数"""
        return self.execute_js('return window._baiduLoginParams;')

    def trigger_login(self, username, password):
        """触发登录流程"""
        return self.execute_js(f'''
            window.baiduLogin.triggerLogin('{username}', '{password}');
        ''')

jsrpc = JSRPCClient('ws://localhost:9222')

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')

    # 1. 触发浏览器登录
    jsrpc.trigger_login(username, password)

    # 2. 等待加密参数生成
    params = jsrpc.get_login_params()

    # 3. 使用加密参数发送请求
    response = requests.post(
        'https://wappass.baidu.com/wp/api/login',
        data=params,
        headers={
            'User-Agent': 'Mozilla/5.0 (iPhone...',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    )

    return jsonify(response.json())

if __name__ == '__main__':
    app.run(port=5000)
```

#### B.4 Python 客户端

```python
# baidu_login_jsrpc.py
import asyncio
from playwright.async_api import async_playwright

class BaiduLoginJSRPC:
    def __init__(self):
        self.browser = None
        self.page = None

    async def init(self):
        """初始化浏览器"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=False)
        context = await self.browser.new_context(
            **playwright.devices['iPhone 15'],
            locale='zh-CN'
        )
        self.page = await context.new_page()

        # 注入 JSRPC 代码
        await self.page.add_init_script(self._get_jsrpc_code())

        # 打开登录页
        await self.page.goto(
            'https://wappass.baidu.com/passport/?login&tpl=wise...'
        )

    def _get_jsrpc_code(self):
        """返回 JSRPC 注入代码"""
        return '''
        // 上面 B.1 和 B.2 的代码
        '''

    async def login(self, username: str, password: str) -> dict:
        """执行登录"""
        # 填写表单
        await self.page.fill('input[placeholder*="手机号"]', username)
        await self.page.fill('input[placeholder*="密码"]', password)

        # 勾选协议
        await self.page.check('input[type="checkbox"]')

        # 点击登录
        await self.page.click('button')

        # 等待并获取加密参数
        params = await self.page.evaluate('window._baiduLoginParams')
        return params

# 使用示例
async def main():
    client = BaiduLoginJSRPC()
    await client.init()
    params = await client.login('testuser', 'password')
    print(f"Encrypted params: {params}")

asyncio.run(main())
```

### 方案 C: 纯 Python 复现（难度高）

需要完整逆向:
1. RSA 公钥提取
2. AES 密钥生成逻辑
3. 签名算法（`k`, `s`, `ds`, `sig`）
4. 设备指纹生成

---

## 八、验证码集成

项目已有旋转验证码识别模型:

- **模型**: EfficientNet-B3 (ONNX)
- **准确率**: 97.21%
- **分类数**: 100（每类 3.6°）

**集成路径**:
```
captcha_model/onnx/captcha_effnet_b3.onnx
└── captcha_test/model.py (ONNXCaptchaPredictor)
    └── baidu_login/captcha_handler.py (待开发)
```

---

## 九、JSRPC 实现状态（已完成 ✅）

### 9.0 已完成的实现

**目录结构**:
```
baidu_login/
├── __init__.py           # 模块导出
├── jsrpc_client.py       # Playwright JSRPC 客户端
├── proxy_server.py       # Flask 代理服务
└── js/
    └── inject.js         # JSRPC 注入脚本
```

**核心功能**:
1. **JSRPC 注入脚本** (`js/inject.js`)
   - XHR Hook 捕获加密参数
   - `window.baiduLogin` API: 触发登录、获取加密参数
   - `window.baiduCrypto` API: 获取 AES 密钥

2. **Python 客户端** (`jsrpc_client.py`)
   - 使用 Playwright 异步 API
   - 模拟 iPhone 15 移动端
   - 自动注入 JSRPC 脚本
   - `get_encrypted_params(username, password)` - 获取加密参数
   - `get_aes_key()` - 获取 AES 密钥

3. **Flask 代理服务** (`proxy_server.py`)
   - `POST /api/encrypt` - 获取加密参数
   - `GET /api/aes-key` - 获取 AES 密钥
   - `GET /health` - 健康检查
   - 支持转发登录请求到百度服务器

**使用示例**:
```python
from baidu_login import BaiduLoginJSRPCClient

async def main():
    async with BaiduLoginJSRPCClient(headless=False) as client:
        params = await client.get_encrypted_params("username", "password")
        print(f"加密密码长度: {len(params.password)}")  # 256 字符
        print(f"AES 密钥: {await client.get_aes_key()}")
```

**验证结果** (2026-02-26):
- ✅ JSRPC 注入成功
- ✅ 加密参数捕获成功（密码/用户名各 256 字符）
- ✅ AES 密钥获取成功 (`619bc882appsapi0`)
- ✅ Python 客户端导入正常
- ✅ Flask 代理服务编译通过

---

## 十、下一步工作

### 10.1 待完成项

1. **搭建 JSRPC 服务**
   ```bash
   # 创建 baidu_login 目录
   mkdir -p baidu_login

   # 创建文件结构
   baidu_login/
   ├── __init__.py
   ├── jsrpc_client.py    # JSRPC 客户端
   ├── login_handler.py   # 登录处理
   ├── captcha.py         # 验证码集成
   └── js/
       └── inject.js      # 注入脚本
   ```

2. **实现注入脚本** (`js/inject.js`)
   - 复制上面的 JSRPC 注入代码
   - 添加验证码识别回调接口

3. **实现 Python 客户端**
   - 使用 Playwright/Selenium 控制浏览器
   - 实现 JSRPC 调用接口
   - 集成 ONNX 验证码识别

4. **集成验证码识别**
   ```python
   # captcha.py
   import sys
   sys.path.append('../captcha_test')
   from model import CaptchaModel

   class CaptchaSolver:
       def __init__(self):
           self.model = CaptchaModel()

       def solve(self, image_bytes: bytes) -> int:
           result = self.model.predict_from_bytes(image_bytes)
           return result['class_index']
   ```

### 9.2 进一步逆向（可选）

1. **定位 RSA 公钥**
   - 在 `vendor.c7ed8022.js` 中搜索公钥字符串
   - 使用 Chrome DevTools 设置条件断点
   - 条件: `arguments[0].length === 256`

2. **分析签名算法**
   - `k`, `s`, `ds` 参数的生成逻辑
   - `sig` 签名算法
   - `shaOne` SHA1 哈希输入

3. **提取设备指纹逻辑**
   - `fuid` 生成算法
   - 指纹数据收集方式

---

## 十、附录

### 10.1 完整登录请求示例

```http
POST /wp/api/login HTTP/1.1
Host: wappass.baidu.com
Content-Type: application/x-www-form-urlencoded
User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)...

adapter=&alg=v3&appid=&baiduId=EF3988BFF4726C4795301E7DD26B734B%3AFG%3D1
&password=3516c9051bd8ae634ad69d78791bca1463721faeb1b0e3adbb66a867b0eeaa0c...
&username=4c322d44d412e728f4a2bbe0efcecb3446414239ee67bf0c9970b098f462e83e...
&k=5752XDY77J%2BRSPsL%2BXyptBkEH%2F90nMer0V68repdEvZnf1VoTMS8q7IDQ3J6eYBk...
&s=bDd6D2UtfAkQwuS1U%2FJ4IZTNN6ZxVx4rQvsUye8LrVZcEwzw2gakOX%2FqYNn1F4U...
&ds=ac3qRWj3HxgVC9Hhiwbb3J9Nsm6%2BST8dWCjvO5ltCG5mpoH8GPhZulB%2FWGlV0d17...
&tk=9542nBJ4W7UY%2BHdBoXfL%2BTvJfD43SJ5AMgHZZXjpdfwRGdCJrWIMCpopxqOSfRXEN...
&sig=Qy9ubkc3c2h2c1ZMdkVpWDlXU3NXWGtQc2twT01KRUJZbTllVVV6OVdrOHJzYVdBdGdR...
&shaOne=00eccbaac6904d73f4296542f43dc2d72c8070c2
&servertime=5ca0730b25
&fuid=FOCoIC3q5fKa8fgJnwzbE93veJHPGdQ54rFmWFwGOJAR9ipjtGNZ6YwClj...
```

### 10.2 环境要求

```
# requirements.txt
playwright>=1.40.0
onnxruntime>=1.16.0
Pillow>=10.0.0
httpx>=0.25.0
```
