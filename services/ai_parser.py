"""Kimi AI 机会通知解析服务。

页面只调用 parse_notice()，API 调用、Prompt 和 JSON 解析都收敛在本模块。
密钥只从环境变量 MOONSHOT_API_KEY 读取，任何日志和异常信息都不包含密钥。
"""

import json
import os
import re

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

BASE_URL = "https://api.moonshot.cn/v1"
MODEL_NAME = "kimi-k2.6"
REQUEST_TIMEOUT = 60

EXTRACT_FIELDS = (
    "name",
    "type",
    "organization",
    "deadline",
    "requirements",
    "skills",
    "materials",
)

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SYSTEM_PROMPT = """你是「机会通知解析助手」，负责从用户粘贴的原始通知中提取结构化信息。

只输出一个 JSON 对象，禁止使用 Markdown 代码围栏，禁止输出任何解释文字。

JSON 字段定义：
- name：机会名称
- type：机会类型，只能取：实习、竞赛、科研、奖学金、其他
- organization：发布组织或企业名称
- deadline：报名或申请的截止日期，格式 YYYY-MM-DD
- requirements：申请条件（如年级、绩点、专业限制等）
- skills：技能要求
- materials：申请材料（如简历、推荐信等）

提取规则（必须严格遵守）：
1. 只提取原始通知中明确出现的信息，不得编造或推测任何内容。
2. 通知中没有提供的信息，返回空字符串 ""。
3. deadline 只有当通知给出明确且无歧义的具体日期（含年、月、日）时才返回；只写了月份（如"12月截止"）、相对日期（如"下周截止"）或表述含糊时，一律返回 ""。
4. 同一信息出现多种说法时，选择最完整、最明确的一种。
5. 不要输出字段定义之外的任何字段，例如 match_reason、gap_analysis、status。"""


class AIParserError(Exception):
    """AI 解析失败，消息为友好中文，可直接展示给用户。"""


class APIKeyMissingError(AIParserError):
    """未检测到 MOONSHOT_API_KEY 环境变量。"""


def _build_client(api_key):
    """创建 OpenAI 兼容客户端。独立成函数便于测试时替换。"""
    return OpenAI(api_key=api_key, base_url=BASE_URL, timeout=REQUEST_TIMEOUT)


def parse_notice(notice_text):
    """调用 Kimi 解析机会通知，返回结构化字段字典。

    失败时抛出 AIParserError（含 APIKeyMissingError），消息可直接展示，
    不包含 API Key 或原始堆栈。
    """
    notice_text = (notice_text or "").strip()
    if not notice_text:
        raise AIParserError("请先粘贴机会通知内容，再进行解析。")

    api_key = os.getenv("MOONSHOT_API_KEY")
    if not api_key or not api_key.strip():
        raise APIKeyMissingError(
            "未检测到环境变量 MOONSHOT_API_KEY，请先配置 Kimi API 密钥后重启应用。"
        )

    client = _build_client(api_key)
    try:
        # 注意：kimi-k2.6 仅允许默认 temperature，不能传自定义采样参数。
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": notice_text},
            ],
        )
    except AuthenticationError as error:
        raise AIParserError("Kimi API 密钥无效或已过期，请检查 MOONSHOT_API_KEY 配置。") from error
    except RateLimitError as error:
        raise AIParserError("请求过于频繁或 API 额度不足，请稍后重试。") from error
    except APITimeoutError as error:
        raise AIParserError("AI 服务响应超时，请稍后重试。") from error
    except APIConnectionError as error:
        raise AIParserError("无法连接 Kimi AI 服务，请检查网络后重试。") from error
    except APIStatusError as error:
        raise AIParserError(f"AI 服务返回错误（HTTP {error.status_code}），请稍后重试。") from error
    except APIError as error:
        raise AIParserError("AI 服务调用失败，请稍后重试。") from error
    except Exception as error:
        # 兜底：不让意外异常把堆栈或密钥暴露到页面。
        raise AIParserError("AI 服务调用失败，请稍后重试。") from error

    content = ""
    if response.choices:
        content = response.choices[0].message.content or ""
    data = _extract_json(_redact(content, api_key))
    return _validate_fields(data)


def _redact(text, api_key):
    """把文本中可能出现的密钥替换掉，避免泄露。"""
    text = str(text or "")
    if api_key:
        text = text.replace(api_key, "***")
    return text


def _extract_json(text):
    """从模型返回内容中提取 JSON 对象，容忍代码围栏和附带说明文字。"""
    text = (text or "").strip()
    if not text:
        raise AIParserError("AI 返回内容为空，请重试。")

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)

    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 兜底：截取第一个 { 到最后一个 } 之间的内容再试一次。
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                data = None

    if not isinstance(data, dict):
        raise AIParserError("AI 返回的内容无法解析为结构化数据，请重试。")
    return data


def _validate_fields(data):
    """校验并规整字段：缺失补空字符串，非法日期留空交由用户补充。"""
    result = {}
    for field in EXTRACT_FIELDS:
        value = data.get(field, "")
        if isinstance(value, list):
            value = "；".join(str(item) for item in value if str(item).strip())
        elif isinstance(value, dict):
            value = ""
        result[field] = str(value or "").strip()

    if result["deadline"] and not _DATE_PATTERN.match(result["deadline"]):
        result["deadline"] = ""
    return result
