"""百度验证码加密模块。"""

import base64
import hashlib
from typing import Optional

# 尝试导入 SHA3 支持
try:
    # Python 3.6+ 内置 hashlib.sha3_256
    _sha3_256 = hashlib.sha3_256
    _sha3_512 = hashlib.sha3_512
except AttributeError:
    # 回退到 pysha3
    import sha3
    _sha3_256 = sha3.sha3_256
    _sha3_512 = sha3.sha3_512

# 常量定义
GU = "appsapi2"

# 哈希算法选择映射
FB = "ABCDEFGabcdefg"
ER = "HIJKLMNhijklmn"
JQ = "OPQRSTopqrst"
O = "UVWXYZuvwxyz"
DZ = "01234"
NZ = "56789"


def md5_hash(data: str) -> str:
    """计算 MD5 哈希值。"""
    return hashlib.md5(data.encode('utf-8')).hexdigest()


def sha1_hash(data: str) -> str:
    """计算 SHA1 哈希值。"""
    return hashlib.sha1(data.encode('utf-8')).hexdigest()


def sha256_hash(data: str) -> str:
    """计算 SHA256 哈希值。"""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def sha512_hash(data: str) -> str:
    """计算 SHA512 哈希值。"""
    return hashlib.sha512(data.encode('utf-8')).hexdigest()


def sha3_256_hash(data: str) -> str:
    """计算 SHA3-256 哈希值。"""
    return _sha3_256(data.encode('utf-8')).hexdigest()


def sha3_512_hash(data: str) -> str:
    """计算 SHA3-512 哈希值。"""
    return _sha3_512(data.encode('utf-8')).hexdigest()


def get_new_key(as_token: str) -> str:
    """根据 as_token 末字符选择哈希算法，生成加密密钥。

    Args:
        as_token: 百度 API 返回的 as 参数

    Returns:
        16 位加密密钥
    """
    if not as_token:
        as_token = ""

    e = as_token + GU
    n = ""

    if not as_token:
        return ""

    r = as_token[-1]  # 取最后一个字符

    if r in FB:
        n = md5_hash(e)
    elif r in ER:
        n = sha1_hash(e)
    elif r in JQ:
        n = sha256_hash(e)
    elif r in O:
        n = sha512_hash(e)
    elif r in DZ:
        n = sha3_256_hash(e)
    elif r in NZ:
        n = sha3_512_hash(e)
    else:
        # 默认使用 MD5
        n = md5_hash(e)

    return n[:16]  # 取前 16 位


def zero_pad(data: bytes, block_size: int = 16) -> bytes:
    """ZeroBytePadding 填充。

    将数据填充到 block_size 的倍数，不足部分用 0 填充。
    """
    padding_len = block_size - (len(data) % block_size)
    if padding_len == block_size:
        padding_len = 0
    return data + b'\x00' * padding_len


def encrypt(data: str, key: str) -> str:
    """AES/ECB/ZeroBytePadding 加密。

    Args:
        data: 待加密的字符串
        key: 16 位加密密钥

    Returns:
        Base64 编码的加密结果
    """
    from Crypto.Cipher import AES

    if not data:
        data = ""

    input_bytes = data.encode('utf-8')
    key_bytes = key.encode('utf-8')

    # ZeroBytePadding
    padded_data = zero_pad(input_bytes, 16)

    # AES/ECB 加密
    cipher = AES.new(key_bytes, AES.MODE_ECB)
    encrypted = cipher.encrypt(padded_data)

    return base64.b64encode(encrypted).decode('utf-8')


def encrypt_angle(angle: int, as_token: str, backstr: str) -> str:
    """加密角度参数，生成 fs 参数。

    Args:
        angle: 预测的角度值 (0-99)
        as_token: 百度 API 返回的 as 参数
        backstr: 百度 API 返回的 backstr 参数

    Returns:
        加密后的 fs 参数
    """
    # 获取加密密钥
    key = get_new_key(as_token)

    # 计算 ac_c
    ac_c = f"{angle / 100:.2f}"

    # 构建 tt JSON
    tt_json = (
        '{"common":{"cl":[],"mv":[],"sc":[],"kb":[],"sb":[],"sd":[],"sm":[],'
        '"cr":{"screenTop":0,"screenLeft":0,"clientWidth":500,"clientHeight":850,'
        '"screenWidth":500,"screenHeight":850,"availWidth":500,"availHeight":850,'
        '"outerWidth":500,"outerHeight":850,"scrollWidth":500,"scrollHeight":500},'
        '"simu":0},"backstr":"' + backstr + '",'
        '"captchalist":{"spin-0":{"mv":[{"t":1720598845000,"fx":158,"fy":519},'
        '{"t":1720598845206,"fx":175,"fy":519},{"t":1720598845418,"fx":186,"fy":519},'
        '{"t":1720598845632,"fx":206,"fy":519},{"t":1720598845901,"fx":216,"fy":519},'
        '{"t":1720598847005,"fx":218,"fy":519},{"t":1720598847638,"fx":217,"fy":519},'
        '{"t":1720598848117,"fx":218,"fy":519},{"t":1720598848533,"fx":220,"fy":519}],'
        '"ac_c":' + ac_c + ','
        '"cr":{"left":105,"top":272,"width":290,"height":280},'
        '"back":{"left":174,"top":316,"width":152,"height":152}}}}'
    )

    # 加密 tt_json
    encrypted_tt = encrypt(tt_json, key)

    # 构建最终 JSON
    final_json = '{"common_en":"' + encrypted_tt + '"}'

    # 再次加密
    return encrypt(final_json, key)
