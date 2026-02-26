/**
 * 百度移动端登录 JSRPC 注入脚本
 *
 * 功能:
 * 1. Hook XHR 请求，捕获加密后的登录参数
 * 2. 提供程序化触发登录的接口
 * 3. 暴露 RPC 调用接口供 Python 客户端使用
 *
 * 使用方法:
 * 1. 在浏览器加载此脚本
 * 2. 调用 window.baiduLogin.triggerLogin(username, password)
 * 3. 调用 window.baiduLogin.waitForParams() 获取加密参数
 */

(function() {
    'use strict';

    // ========================================
    // 存储加密后的登录参数
    // ========================================
    window._baiduLoginParams = null;
    window._baiduLoginState = 'idle'; // idle, triggered, success, error

    // ========================================
    // XHR Hook - 捕获登录请求参数
    // ========================================
    const originalSend = XMLHttpRequest.prototype.send;
    const originalOpen = XMLHttpRequest.prototype.open;

    XMLHttpRequest.prototype.open = function(method, url, ...args) {
        this._url = url;
        this._method = method;
        return originalOpen.apply(this, [method, url, ...args]);
    };

    XMLHttpRequest.prototype.send = function(body) {
        const url = this._url || '';

        // 检测登录请求
        if (url.includes('/wp/api/login')) {
            try {
                const params = {};
                if (typeof body === 'string') {
                    body.split('&').forEach(pair => {
                        const eqIndex = pair.indexOf('=');
                        if (eqIndex > 0) {
                            const key = decodeURIComponent(pair.substring(0, eqIndex));
                            const value = decodeURIComponent(pair.substring(eqIndex + 1) || '');
                            params[key] = value;
                        }
                    });
                }

                window._baiduLoginParams = {
                    // 加密参数
                    password: params.password,
                    username: params.username,
                    k: params.k,
                    s: params.s,
                    ds: params.ds,

                    // 签名参数
                    tk: params.tk,
                    sig: params.sig,
                    shaOne: params.shaOne,
                    servertime: params.servertime,

                    // 设备/会话参数
                    fuid: params.fuid,
                    gid: params.gid,
                    session_id: params.session_id,
                    baiduId: params.baiduId,
                    time: params.time,

                    // 其他参数
                    alg: params.alg,
                    isEncrypted: params.isEncrypted,
                    loginmerge: params.loginmerge,
                    tpl: params.tpl,
                    lang: params.lang,
                    u: params.u,

                    // 原始请求体
                    _rawBody: body
                };

                window._baiduLoginState = 'success';
                console.log('[JSRPC] Login params captured');
                console.log('[JSRPC] Password length:', params.password ? params.password.length : 0);
            } catch(e) {
                console.error('[JSRPC] Parse error:', e);
                window._baiduLoginState = 'error';
            }
        }

        return originalSend.apply(this, [body]);
    };

    // ========================================
    // 百度登录 RPC 接口
    // ========================================
    window.baiduLogin = {

        /**
         * 获取当前加密参数
         */
        getParams: function() {
            return window._baiduLoginParams;
        },

        /**
         * 获取当前状态
         */
        getState: function() {
            return window._baiduLoginState;
        },

        /**
         * 重置状态
         */
        reset: function() {
            window._baiduLoginParams = null;
            window._baiduLoginState = 'idle';
            return { status: 'reset' };
        },

        /**
         * 填写表单
         */
        fillForm: function(username, password) {
            // 查找输入框
            const userInput = document.querySelector('input[placeholder*="手机号"]') ||
                              document.querySelector('input[placeholder*="用户名"]') ||
                              document.querySelector('input[placeholder*="邮箱"]');
            const passInput = document.querySelector('input[placeholder*="密码"]') ||
                              document.querySelector('input[type="password"]');

            if (!userInput || !passInput) {
                return { status: 'error', message: 'Input fields not found' };
            }

            // 填写用户名
            userInput.value = username;
            userInput.dispatchEvent(new Event('input', { bubbles: true }));
            userInput.dispatchEvent(new Event('change', { bubbles: true }));

            // 填写密码
            passInput.value = password;
            passInput.dispatchEvent(new Event('input', { bubbles: true }));
            passInput.dispatchEvent(new Event('change', { bubbles: true }));

            return { status: 'filled' };
        },

        /**
         * 勾选协议
         */
        checkAgreement: function() {
            // 方法1: 直接操作 checkbox
            const checkbox = document.querySelector('input[type="checkbox"]');
            if (checkbox) {
                if (!checkbox.checked) {
                    // 设置 checked 属性
                    checkbox.checked = true;
                    // 触发所有可能的事件
                    checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                    checkbox.dispatchEvent(new Event('input', { bubbles: true }));
                    checkbox.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                    console.log('[JSRPC] Checkbox set to checked');
                }
                return { status: 'checked', method: 'checkbox', checked: checkbox.checked };
            }

            // 方法2: 点击协议区域
            const agreementArea = document.querySelector('[class*="agreement"]') ||
                                  document.querySelector('[class*="protocol"]');
            if (agreementArea) {
                agreementArea.click();
                console.log('[JSRPC] Agreement area clicked');
                return { status: 'checked', method: 'area' };
            }

            return { status: 'checked', method: 'fallback' };
        },

        /**
         * 检查协议是否已勾选
         */
        isAgreementChecked: function() {
            const checkbox = document.querySelector('input[type="checkbox"]');
            return checkbox ? checkbox.checked : false;
        },

        /**
         * 点击登录按钮
         */
        clickLogin: function() {
            const buttons = document.querySelectorAll('button');
            for (let btn of buttons) {
                const text = btn.textContent || '';
                if ((text.includes('登') || text.includes('Login')) && !btn.disabled) {
                    btn.click();
                    window._baiduLoginState = 'triggered';
                    console.log('[JSRPC] Login button clicked');
                    return { status: 'clicked', disabled: btn.disabled };
                }
            }
            // 如果按钮被禁用，返回原因
            for (let btn of buttons) {
                if (btn.textContent.includes('登')) {
                    return { status: 'error', message: 'Login button disabled', disabled: btn.disabled };
                }
            }
            return { status: 'error', message: 'Login button not found' };
        },

        /**
         * 触发完整登录流程
         */
        triggerLogin: function(username, password) {
            // 重置状态
            window._baiduLoginParams = null;
            window._baiduLoginState = 'idle';

            // 填写表单
            const fillResult = this.fillForm(username, password);
            if (fillResult.status === 'error') {
                return fillResult;
            }

            // 勾选协议
            this.checkAgreement();

            // 验证协议是否勾选成功
            const agreementOk = this.isAgreementChecked();
            console.log('[JSRPC] Agreement checked:', agreementOk);

            // 延迟点击登录按钮，确保页面状态更新
            setTimeout(() => {
                const clickResult = this.clickLogin();
                if (clickResult.status === 'error') {
                    console.error('[JSRPC] Click login failed:', clickResult.message);
                    window._baiduLoginState = 'error';
                }
            }, 300);

            return { status: 'triggered', agreementChecked: agreementOk };
        },

        /**
         * 等待加密参数生成
         */
        waitForParams: function(timeout) {
            timeout = timeout || 10000;
            return new Promise((resolve, reject) => {
                const startTime = Date.now();
                const check = () => {
                    if (window._baiduLoginState === 'success' && window._baiduLoginParams) {
                        resolve(window._baiduLoginParams);
                    } else if (window._baiduLoginState === 'error') {
                        reject(new Error('Login failed'));
                    } else if (Date.now() - startTime > timeout) {
                        reject(new Error('Timeout waiting for login params'));
                    } else {
                        setTimeout(check, 100);
                    }
                };
                check();
            });
        },

        /**
         * 使用加密参数发送登录请求
         * (供外部调用，返回完整的登录参数)
         */
        getEncryptedCredentials: async function(username, password) {
            this.triggerLogin(username, password);
            try {
                const params = await this.waitForParams();
                return {
                    status: 'success',
                    params: params
                };
            } catch(e) {
                return {
                    status: 'error',
                    message: e.message
                };
            }
        }
    };

    // ========================================
    // PassMachine AES 加密接口 (已定位)
    // ========================================
    window.baiduCrypto = {
        /**
         * 获取 AES 加密密钥
         */
        getAESKey: function() {
            if (window.PassMachine && window.PassMachine.haveMkd && window.PassMachine.haveMkd.store) {
                const store = window.PassMachine.haveMkd.store;
                return store.nameL + store.nameR;
            }
            return null;
        },

        /**
         * 使用 AES-ECB 加密 (验证码数据加密)
         */
        encryptAES: function(data) {
            if (!window.PassMachine || !window.PassMachine.haveMkd) {
                return null;
            }
            try {
                return window.PassMachine.haveMkd.encrypt(data);
            } catch(e) {
                console.error('[JSRPC] AES encrypt error:', e);
                return null;
            }
        }
    };

    console.log('[JSRPC] Baidu login injection loaded');
    console.log('[JSRPC] Available APIs:');
    console.log('  - window.baiduLogin.triggerLogin(username, password)');
    console.log('  - window.baiduLogin.waitForParams(timeout)');
    console.log('  - window.baiduLogin.getParams()');
    console.log('  - window.baiduCrypto.getAESKey()');
    console.log('  - window.baiduCrypto.encryptAES(data)');

})();
