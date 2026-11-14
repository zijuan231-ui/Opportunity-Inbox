"""Kimi AI 机会通知解析服务。

页面只调用 parse_notice()，API 调用、Prompt 和 JSON 解析都收敛在本模块。
密钥只从环境变量 MOONSHOT_API_KEY 读取，任何日志和异常信息都不包含密钥。
"""

import json
import logging
import os
import re
import time

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from database import DEFAULT_OPPORTUNITY_TYPE, OPPORTUNITY_TYPES

BASE_URL = "https://api.moonshot.cn/v1"
MODEL_NAME = "kimi-k2.6"
REQUEST_TIMEOUT = 120  # 网络代理环境下需要更长的超时

# Day 5：新增 registration_process / source_link / benefits / key_dates / evidence
# key_dates 和 evidence 虽然在 JSON Schema 里是结构化对象，但落库时统一序列化
# 为 JSON 字符串。EXTRACT_FIELDS 里全部都是「期望的顶层 JSON key」。
EXTRACT_FIELDS = (
    "name",
    "type",
    "organization",
    "deadline",
    "requirements",
    "skills",
    "materials",
    "registration_process",
    "source_link",
    "benefits",
    "key_dates",
    "evidence",
)

# JSON 顶层 key：值可能是 dict/list，需要专门序列化或安全降级。
_STRUCTURED_FIELDS = {"key_dates", "evidence"}

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = r"""你是「机会通知解析助手」，负责从用户粘贴的原始通知中提取结构化信息。

只输出一个 JSON 对象，禁止使用 Markdown 代码围栏，禁止输出任何解释文字。

==================================================
一、字段定义（全部 12 个，都必须返回，缺失时用空值）
==================================================

【普通文本字段】（缺失时返回 ""）
- name：机会名称，优先使用通知标题中的正式名称。
- type：机会类型，只能从以下 8 个中选择一个：
  实习就业、科研学术、学科竞赛、奖学金与资助、志愿与社会实践、
  校园组织与活动、学习与成长、其他
- organization：发布组织，例如学校、学院、实验室、竞赛主办方、企业、公益组织或社团。
- deadline：普通参与者最重要的报名或申请截止日期，格式 YYYY-MM-DD。
  只在有明确且无歧义的具体年月日时才返回；只有月份、相对日期或含糊表述时返回 ""。
- requirements：申请条件，即申请人需要满足的资格。
  包括但不限于：年级、专业、绩点、团队人数、队长/成员/指导老师角色限制、身份限制、注册要求等。
  团队人数、角色构成、指导老师要求都属于 requirements，要完整保留。
- skills：通知明确要求的专业技能。
  只提取原文明确写了的技能（例如 "Python 编程"、"SQL 查询"、"英语 CET-6"）；
  没有明确要求技能时返回 ""，不得编造或推测。
- materials：需要提交的申请材料（如简历、推荐信、成绩单、报名表、作品等）。
  只提取原文明确要求学生/参赛者提交的材料；
  承办方、组织方、学校管理员需要填写的备案申请书、承诺书等材料，不是普通学生的申请材料，不要写入此字段。
- registration_process：报名或申请流程，按步骤整理。
  例如：注册账号 → 队长创建团队 → 搜索成员发送邀请 → 填写团队信息 → 学校管理员审核 → 完成规则答题测试 → 提交作品。
  用自然语言描述每一步，保持原文顺序和关键动词。
- source_link：通知中明确出现的官方报名链接、官网地址或资料下载链接。
  没有明确链接时返回 ""。
- benefits：机会明确说明的回报。
  例如：薪酬、日薪、证书、学分、奖学金金额、科研经历、指导机会、就业绿色通道等。
  只提取原文明确写出的回报，没有时返回 ""。

【结构化 JSON 字段】（必须返回合法 JSON 数组 / 对象，缺失时返回 [] 或 {}）
- key_dates：关键时间节点数组，每个元素如下结构：
  {
    "event": "事件名称（如 参赛队报名/学校管理员审核/校赛/省赛/全国总决赛/成绩公示/证书发放）",
    "start_date": "YYYY-MM-DD 或空字符串",
    "end_date": "YYYY-MM-DD 或空字符串",
    "description": "对该时间节点的简短说明（可留空字符串）"
  }
  规则：
  - 多个时间节点必须全部提取，不得只保留最后一个或最重要的。
  - 同一事件有起止时间时 start_date 和 end_date 都填写；只有一个日期时，哪个已知就填哪个，另一个留空字符串。
  - 日期不完整（只有月日没有年份，或年份有歧义）时，start_date 和 end_date 都留空字符串，
    但 event 和 description 仍然要写（例如 event "省赛", description "2027年5月举行"）。
  - 不要把比赛举办日期、证书发放日期等非报名/审核类日期填到顶层 deadline，
    这些信息统一放在 key_dates 中。

- evidence：重要字段的原文依据，对象结构。key 是字段名，value 是：
  {
    "value": "该字段的提取值（与顶层同名字段的值一致）",
    "quote": "原始通知中直接出现的、能证明该值的原文片段。quote 必须逐字来自原文，不得改写或总结。"
  }
  需要提供 evidence 的字段优先包括：deadline, requirements, materials, registration_process。
  如果 key_dates 中也有重要时间节点，可以为 key_dates 单独保留，但顶层 evidence 不强制。
  找不到可靠原文依据时，quote 留空字符串；不要编造 quote。

==================================================
二、严格遵守的提取规则
==================================================
1. 只提取原始通知中明确出现的信息，不得编造、推测或补全年份。
2. 通知中没有提供的信息，按字段类型返回空字符串 "" 或空数组 []。
3. 不得把承办方、组织方、管理员需要的材料当成普通学生的申请材料。
4. 不得把面向其他角色（如学校管理员、省赛承办方）的报名/备案流程放进 registration_process。
5. 不得把常见申请材料（如简历、推荐信）当成通知明确要求的 materials——只有通知明确列出来的才算。
6. 不得编造 skills、benefits 或 type——通知没写的就是空。
7. 同一信息出现多种说法时，选择最完整、最明确的一种（例如 deadline 优先选普通参赛者的报名截止日）。
8. 多个时间节点全部保留在 key_dates，不要合并也不要遗漏。
9. 条件、材料、流程尽量保留完整信息，不要为了简短而丢掉关键限制（如 "3-5 人" 不要缩写成 "4 人"）。
10. quote 必须是原文逐字引用，可以截取片段但不能改写。
11. type 无法判断或存在多种可能时，返回 "其他"，不得强行归类。
12. 不要输出字段定义以外的任何字段（例如 match_reason、gap_analysis、status）。

==================================================
三、输出要求
==================================================
- 只返回一个 JSON 对象，合法、可直接被 json.loads 解析。
- 所有 12 个字段都必须出现；不要少字段。
- 日期统一 YYYY-MM-DD；不能用 "2026/11/15"、"11月15日"、"下周五"。
- 结构化字段 key_dates 和 evidence 必须是标准 JSON 数组 / 对象，不能是字符串。"""


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

    logger.info(
        "Kimi 解析请求：模型=%s，输入字符数=%d", MODEL_NAME, len(notice_text)
    )

    client = _build_client(api_key)
    started = time.perf_counter()
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

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    raw_content = ""
    if response.choices:
        raw_content = response.choices[0].message.content or ""
    redacted = _redact(raw_content, api_key)

    logger.info(
        "Kimi 响应：耗时=%d ms，内容长度=%d 字符，有内容=%s",
        elapsed_ms, len(raw_content), bool(raw_content.strip()),
    )

    try:
        raw_data = _extract_json(redacted)
    except AIParserError:
        # JSON 解析失败也记一条日志，但原始内容截断避免泄露。
        logger.warning(
            "AI 返回无法解析为 JSON，前 300 字=%r", raw_content[:300],
        )
        raise

    result = _validate_fields(raw_data)

    if logger.isEnabledFor(logging.DEBUG):
        for field in EXTRACT_FIELDS:
            value = result.get(field)
            preview = (
                value[:80] + "…" if isinstance(value, str) and len(value) > 80 else value
            )
            logger.debug("字段 %-20s => %r", field, preview)

    logger.info(
        "字段校验完成：有效字段 %d / %d",
        sum(1 for k in EXTRACT_FIELDS if str(result.get(k, "")).strip()),
        len(EXTRACT_FIELDS),
    )
    return result


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
    """校验并规整字段。

    Day 5 关键改进：
    - 普通文本字段：dict/list 不再直接清空，而是安全降级为可读字符串。
    - key_dates / evidence：必须是 dict/list，否则用 _safe_json_dumps 序列化。
    - deadline：非标准日期格式仍清空（严格规则）。
    - type：超出枚举的原始值保留到 evidence，字段值落回 "其他"。
    - 任意一个新增字段解析失败，不影响整体返回。
    """
    result = {}
    for field in EXTRACT_FIELDS:
        value = data.get(field)
        try:
            if field in _STRUCTURED_FIELDS:
                result[field] = _validate_structured(field, value)
            else:
                result[field] = _validate_text(value, field)
        except Exception as error:  # noqa: BLE001 — 单个字段解析失败不应影响整体
            logger.warning("字段 %s 校验异常，降级为空串：%s", field, error)
            result[field] = ""

    # deadline 严格单格式校验。
    if result["deadline"] and not _DATE_PATTERN.match(result["deadline"]):
        result["deadline"] = ""

    # type 超出枚举时落回 "其他"，但把原始值塞进 evidence 供追溯。
    if result["type"] not in OPPORTUNITY_TYPES:
        original_type = result["type"]
        result["type"] = DEFAULT_OPPORTUNITY_TYPE
        if original_type:
            result["evidence"] = _inject_type_evidence(
                result.get("evidence", ""), original_type
            )

    return result


def _validate_text(value, field):
    """普通文本字段：安全地把任意类型规整为字符串。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        # list of scalar：用分号拼接。list of dict：JSON 序列化保留结构。
        if all(not isinstance(item, (dict, list)) for item in value):
            return "；".join(str(item).strip() for item in value if str(item).strip())
        return _safe_json_dumps(value)
    if isinstance(value, dict):
        # Day 5 不再直接清空 dict —— 序列化成字符串保留。
        return _safe_json_dumps(value)
    return str(value).strip()


def _validate_structured(field, value):
    """key_dates / evidence 的专用校验：必须是 dict/list，落库时序列化为 JSON 字符串。"""
    if field == "key_dates":
        # 期望 list
        if value is None:
            return "[]"
        if isinstance(value, str):
            # 模型可能把 JSON 字符串当字符串返回 —— 尝试二次解析。
            parsed = _try_parse_json_string(value)
            if parsed is not None:
                value = parsed
            else:
                return "[]"
        if isinstance(value, list):
            return _safe_json_dumps(value)
        # 类型不匹配，安全降级为空数组，不抛异常。
        logger.warning("key_dates 预期 list，实际 %s，降级为空数组", type(value).__name__)
        return "[]"

    if field == "evidence":
        # 期望 dict
        if value is None:
            return "{}"
        if isinstance(value, str):
            parsed = _try_parse_json_string(value)
            if parsed is not None:
                value = parsed
            else:
                return "{}"
        if isinstance(value, dict):
            return _safe_json_dumps(value)
        logger.warning("evidence 预期 dict，实际 %s，降级为空对象", type(value).__name__)
        return "{}"

    return ""


def _try_parse_json_string(text):
    """尝试把模型错误返回的 JSON 字符串二次解析；失败返回 None。"""
    if not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 兜底：截取第一段 JSON 对象/数组再试。
        for start, end in (("{", "}"), ("[", "]")):
            s = text.find(start)
            e = text.rfind(end)
            if s != -1 and e > s:
                try:
                    return json.loads(text[s : e + 1])
                except json.JSONDecodeError:
                    continue
        return None


def _safe_json_dumps(value):
    """带 ensure_ascii=False 的 JSON 序列化，失败时退回 str()。"""
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        try:
            return str(value)
        except Exception:
            return ""


def _inject_type_evidence(evidence_json, original_type):
    """当 type 超出枚举时，把原始值写进 evidence 以便追溯。"""
    try:
        evidence = json.loads(evidence_json) if evidence_json else {}
    except json.JSONDecodeError:
        evidence = {}
    if not isinstance(evidence, dict):
        evidence = {}
    evidence["type"] = {"value": original_type, "quote": "(模型分类超出预设枚举)"}
    return _safe_json_dumps(evidence)
