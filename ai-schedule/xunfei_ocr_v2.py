"""
讯飞 OCR 图片识别 - 新版 api.xf-yun.com 接口
支持本地图片文件 & 图片URL两种方式
使用前：将下方 APP_ID / API_KEY / API_SECRET 替换为你自己的
"""

import base64
import hmac
import hashlib
from datetime import datetime, timezone
import json
import requests
from urllib.parse import quote
from pathlib import Path


# ==================== 配置区域 ====================
APP_ID = "28c3d6f8"                                 # 讯飞 APPID
API_KEY = "c0ad5f0834c0e4d65b594c6845a8a08f"      # 讯飞 APIKey
API_SECRET = "MGQ3MmQwYjcxOWZmMThjZTZlYzViM2Uy"    # 讯飞 APISecret
API_URL = "https://api.xf-yun.com/v1/private/sf8e6aca1"
HOST = "api.xf-yun.com"
# ===================================================


# ==================== 认证签名 ====================

def build_auth_url() -> str:
    """
    构建带鉴权参数的请求URL
    签名规则（HMAC-SHA256）：
      1. signature_origin = "host: {HOST}\ndate: {date}\nPOST {path} HTTP/1.1"
      2. signature = base64(hmac_sha256(API_SECRET, signature_origin))
      3. authorization_origin = 'api_key="{API_KEY}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
      4. authorization = base64(authorization_origin)
      5. 最终URL = API_URL?authorization=xxx&host=xxx&date=xxx
    """
    path = "/v1/private/sf8e6aca1"
    date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

    # Step 1: 拼接签名原始字符串
    signature_origin = f"host: {HOST}\ndate: {date}\nPOST {path} HTTP/1.1"

    # Step 2: HMAC-SHA256 签名 -> base64
    signature_sha = hmac.new(
        API_SECRET.encode("utf-8"),
        signature_origin.encode("utf-8"),
        hashlib.sha256
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")

    # Step 3: 拼接 authorization 原始字符串
    auth_origin = (
        f'api_key="{API_KEY}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )

    # Step 4: base64 编码得到最终 authorization
    authorization = base64.b64encode(auth_origin.encode("utf-8")).decode("utf-8")

    # Step 5: 拼接到 URL
    request_url = f"{API_URL}?authorization={quote(authorization)}&host={quote(HOST)}&date={quote(date)}"
    return request_url


# ==================== 图片编码 ====================

def encode_image_file(image_path: str) -> tuple[str, str]:
    """本地图片 -> (Base64字符串, 后缀名)"""
    suffix = Path(image_path).suffix.lower().lstrip(".")
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return data, suffix


def encode_image_url(image_url: str) -> tuple[str, str]:
    """图片 URL -> 下载 -> (Base64字符串, 后缀名)"""
    resp = requests.get(image_url, timeout=15)
    resp.raise_for_status()
    suffix = Path(image_url.split("?")[0]).suffix.lower().lstrip(".") or "jpg"
    data = base64.b64encode(resp.content).decode("utf-8")
    return data, suffix


# ==================== OCR 核心 ====================

def ocr_recognize(image_input, is_url: bool = False) -> dict:
    """
    调用讯飞 OCR API (api.xf-yun.com 新版)
    :param image_input: 本地图片路径 或 图片URL
    :param is_url:      True=图片URL, False=本地文件
    :return:           API 返回的 JSON 字典
    """
    if is_url:
        img_b64, img_type = encode_image_url(image_input)
    else:
        img_b64, img_type = encode_image_file(image_input)

    # 请求体
    payload = {
        "header": {
            "app_id": APP_ID,
            "status": 3,  # 3 = 一次性传输
        },
        "parameter": {
            "sf8e6aca1": {
                "category": "ch_en_public_cloud",
                "result": {
                    "encoding": "utf8",
                    "compress": "raw",
                    "format": "json",
                },
            }
        },
        "payload": {
            "sf8e6aca1_data_1": {
                "encoding": img_type,
                "status": 3,
                "image": img_b64,
            }
        },
    }

    request_url = build_auth_url()
    resp = requests.post(
        request_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()


# ==================== 结果解析 ====================

def parse_text(result: dict) -> str:
    """从返回 JSON 中提取识别文字"""
    header = result.get("header", {})
    code = header.get("code", -1)
    if code != 0:
        raise RuntimeError(f"识别失败: code={code}, message={header.get('message', '未知错误')}")

    # 结果在 payload.result.text，是 base64 编码的 JSON 字符串
    result_b64 = result.get("payload", {}).get("result", {}).get("text", "")
    if not result_b64:
        return json.dumps(result, ensure_ascii=False, indent=2)

    text_json = base64.b64decode(result_b64).decode("utf-8")
    text_data = json.loads(text_json)

    # 提取纯文本
    lines = []
    for page in text_data.get("pages", []):
        for line in page.get("lines", []):
            line_text = "".join(w.get("content", "") for w in line.get("words", []))
            if line_text.strip():
                lines.append(line_text)

    return "\n".join(lines)


# ==================== CLI 入口 ====================

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="讯飞 OCR 图片识别 (新版 api.xf-yun.com)")
    parser.add_argument("image", help="图片文件路径 或 图片URL")
    parser.add_argument("--url", action="store_true", help="将 image 参数视为 URL 而非本地路径")
    args = parser.parse_args()

    print(f"识别: {args.image}")
    try:
        result = ocr_recognize(args.image, is_url=args.url)
        text = parse_text(result)
        print("\n识别结果：")
        print(text)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)
