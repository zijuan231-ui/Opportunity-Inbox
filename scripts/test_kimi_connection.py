"""临时脚本：测试 Moonshot(Kimi) API 连接。不会读取或输出密钥内容。"""

import os
import sys

from openai import APIStatusError, OpenAI

BASE_URL = "https://api.moonshot.cn/v1"
TEST_MESSAGE = "你好，请用一句话介绍自己。"

# 优先尝试的文本对话模型；都不在列表里时退回第一个非向量/多模态模型。
PREFERRED_MODELS = (
    "kimi-latest",
    "moonshot-v1-8k",
    "moonshot-v1-32k",
    "moonshot-v1-128k",
    "kimi-k2-0905-preview",
)
NON_CHAT_KEYWORDS = ("embedding", "vision", "image", "audio")


def redact(text, secret):
    """把可能出现的密钥替换掉，避免错误信息泄露。"""
    text = str(text or "")
    if secret:
        text = text.replace(secret, "***")
    return text


def pick_chat_model(names):
    """选择一个可用于普通文本对话的模型。"""
    for preferred in PREFERRED_MODELS:
        if preferred in names:
            return preferred
    for name in names:
        if any(keyword in name.lower() for keyword in NON_CHAT_KEYWORDS):
            continue
        return name
    return names[0] if names else None


def main():
    api_key = os.getenv("MOONSHOT_API_KEY")
    if not api_key or not api_key.strip():
        print("未检测到 MOONSHOT_API_KEY，无法测试。")
        return 1

    client = OpenAI(api_key=api_key, base_url=BASE_URL, timeout=30)

    try:
        models = client.models.list()
    except APIStatusError as error:
        print(f"获取模型列表失败：HTTP {error.status_code}")
        print("错误信息：", redact(getattr(error, "message", error), api_key)[:800])
        return 1
    except Exception as error:  # noqa: BLE001
        print("获取模型列表失败：", type(error).__name__)
        print("错误信息：", redact(error, api_key)[:800])
        return 1

    names = sorted({model.id for model in models.data})
    print("可用模型列表：")
    for name in names:
        print(" -", name)

    if not names:
        print("模型列表为空，无法继续测试。")
        return 1

    model_name = pick_chat_model(names)
    print("\n实际使用的模型：", model_name)

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": TEST_MESSAGE}],
        )
    except APIStatusError as error:
        print(f"对话请求失败：HTTP {error.status_code}（模型 {model_name}）")
        print("错误信息：", redact(getattr(error, "message", error), api_key)[:800])
        return 1
    except Exception as error:  # noqa: BLE001
        print(f"对话请求失败：{type(error).__name__}（模型 {model_name}）")
        print("错误信息：", redact(error, api_key)[:800])
        return 1

    content = (response.choices[0].message.content or "").strip()
    print("\n对话是否成功：是")
    print("模型回复：", content)

    usage = response.usage
    if usage:
        print(
            "token 用量："
            f"prompt={usage.prompt_tokens} "
            f"completion={usage.completion_tokens} "
            f"total={usage.total_tokens}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
