"""发现机会：上传文件或粘贴文本，统一走 Kimi AI 解析，人工确认后保存。"""

import json

import streamlit as st

import database
from sample_data import STATUS_ORDER
from services import ai_parser, text_extraction

# Day 5：扩充了 5 个新字段（其中 key_dates / evidence 是 JSON 字符串）。
# PARSE_FIELDS 决定 AI 解析预览表单中展示哪些字段。
# 注意：match_reason / gap_analysis 由用户手动填写或后续匹配得到，不在 AI EXTRACT_FIELDS 里。
PARSE_FIELDS = [
    ("name", "机会名称", "text"),
    ("type", "机会类型", "select"),
    ("organization", "发布组织", "text"),
    ("deadline", "主要报名截止", "text"),
    ("registration_process", "报名流程", "textarea"),
    ("key_dates", "关键时间节点（JSON）", "json"),
    ("requirements", "申请条件", "textarea"),
    ("skills", "技能要求", "textarea"),
    ("materials", "申请材料", "textarea"),
    ("source_link", "官方链接", "text"),
    ("benefits", "机会回报", "textarea"),
    ("evidence", "原文依据（JSON）", "json"),
    ("match_reason", "匹配理由", "textarea"),
    ("gap_analysis", "能力差距", "textarea"),
    ("status", "申请状态", "select"),
    ("raw_text", "原始通知", "textarea"),
]

JSON_FIELDS = {"key_dates", "evidence"}

TEXTAREA_FIELDS = {
    "registration_process",
    "requirements",
    "skills",
    "materials",
    "benefits",
    "match_reason",
    "gap_analysis",
    "raw_text",
}

SELECT_FIELDS = {"type", "status"}

DEFAULT_STATUS = "待评估"

UPLOAD_EXTENSIONS = ["pdf", "txt", "docx"]

PARSE_STATE_KEYS = (
    "show_parse_result",
    "parsed_source_text",
    "parsed_values",
    "pending_upload",
)


def _render_field_value(raw_value, label):
    """尝试把 JSON 字符串解析并友好展示，失败时原样展示。"""
    if not raw_value:
        return None
    if label not in JSON_FIELDS:
        return None
    try:
        data = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return None
    return data


def _render_key_dates_preview(data):
    """把 key_dates 数组按时间排序后友好展示。"""
    if not isinstance(data, list) or not data:
        st.caption("无关键时间节点")
        return
    # 按 start_date / end_date 第一个非空日期排序。
    def sort_key(item):
        if not isinstance(item, dict):
            return ""
        return item.get("start_date") or item.get("end_date") or ""

    sorted_items = sorted(data, key=sort_key)
    st.markdown("**关键时间节点（共 %d 项）**" % len(sorted_items))
    for idx, item in enumerate(sorted_items, 1):
        if not isinstance(item, dict):
            continue
        event = item.get("event") or f"事件 {idx}"
        start = item.get("start_date") or ""
        end = item.get("end_date") or ""
        description = item.get("description") or ""
        if start and end:
            date_range = f"{start} → {end}"
        elif start:
            date_range = start
        elif end:
            date_range = end
        else:
            date_range = "日期待确认"
        line = f"**{idx}. {event}**  —  {date_range}"
        if description:
            line += f"\n   说明：{description}"
        st.markdown(line)


def _render_evidence_preview(data):
    """把 evidence 对象按字段分组展示原文依据。"""
    if not isinstance(data, dict) or not data:
        st.caption("无原文依据")
        return
    st.markdown("**原文依据（共 %d 项）**" % len(data))
    for field_name, entry in data.items():
        if not isinstance(entry, dict):
            continue
        value = entry.get("value") or ""
        quote = entry.get("quote") or ""
        with st.expander(f"📌 {field_name}", expanded=False):
            if value:
                st.markdown(f"**提取值**：{value}")
            if quote:
                st.markdown(f"> {quote}")
            if not value and not quote:
                st.caption("（无内容）")


def _render_json_field_preview(field_key, raw_value):
    """JSON 字段预览：解析成功则结构化展示，否则提示格式错误。"""
    parsed = _render_field_value(raw_value, field_key)
    if parsed is None and raw_value:
        st.caption("⚠️ 当前 JSON 格式不正确，请在下方文本框中修正。")
        return False
    if field_key == "key_dates":
        _render_key_dates_preview(parsed)
    elif field_key == "evidence":
        _render_evidence_preview(parsed)
    return True


def render_parse_result(form_version, parsed):
    """以可编辑控件展示 AI 解析结果，并返回用户填写的内容。"""
    st.info("AI 解析完成，请核对以下字段后再保存。")
    st.caption(
        "AI 只提取原文中明确出现的信息，缺失字段留空，请自行补充；"
        "所有字段都可以修改，保存时记录的是你确认后的内容。"
    )

    values = {}
    with st.container(border=True):
        for key, label, kind in PARSE_FIELDS:
            widget_key = f"parse-{form_version}-{key}"
            raw_value = parsed.get(key, "")

            # JSON 字段先展示结构化预览，再提供可编辑的 JSON 文本框。
            if kind == "json":
                st.markdown(f"**{label}**")
                valid = _render_json_field_preview(key, raw_value)
                edited_value = st.text_area(
                    f"编辑 {label}（JSON）",
                    value=raw_value or "",
                    key=widget_key,
                    height=120,
                    placeholder='例如：[{"event":"报名","start_date":"2027-01-01","end_date":"2027-01-20","description":""}]',
                )
                # 如果用户修正了 JSON，再次验证。
                if edited_value and edited_value != raw_value:
                    try:
                        json.loads(edited_value)
                        st.caption("✅ JSON 格式正确")
                    except json.JSONDecodeError as exc:
                        st.caption(f"⚠️ JSON 格式错误：{exc.msg}")
                values[key] = edited_value
                continue

            if key == "status":
                current = parsed.get(key) or DEFAULT_STATUS
                values[key] = st.selectbox(
                    label,
                    STATUS_ORDER,
                    index=STATUS_ORDER.index(current) if current in STATUS_ORDER else 0,
                    key=widget_key,
                )
            elif key == "type":
                current = parsed.get(key) or database.DEFAULT_OPPORTUNITY_TYPE
                if current not in database.OPPORTUNITY_TYPES:
                    current = database.DEFAULT_OPPORTUNITY_TYPE
                values[key] = st.selectbox(
                    label,
                    database.OPPORTUNITY_TYPES,
                    index=database.OPPORTUNITY_TYPES.index(current),
                    key=widget_key,
                )
            elif key in TEXTAREA_FIELDS:
                values[key] = st.text_area(
                    label, value=raw_value, key=widget_key,
                    height=100 if key != "raw_text" else 200,
                )
            else:
                values[key] = st.text_input(
                    label, value=raw_value, key=widget_key
                )
    return values


def save_opportunity(values, allow_past_deadline=False):
    """保存机会；上传来源会先落盘原始文件，再写数据库。"""
    upload = st.session_state.get("pending_upload")
    payload = dict(values)

    # JSON 字段：确保用户编辑后的 JSON 是合法的，否则降级为空。
    for field in ("key_dates", "evidence"):
        text = (payload.get(field) or "").strip()
        if text:
            try:
                json.loads(text)  # 只做格式校验，值本身就是字符串
                payload[field] = text
            except json.JSONDecodeError:
                st.error(
                    f"「{field}」的 JSON 格式不正确，请修正后再保存。"
                )
                return
        else:
            payload[field] = ""

    file_info = None
    if upload:
        payload["source_kind"] = "upload"
        payload["source_file_name"] = upload["name"]
        try:
            payload["source_file_path"] = database.save_upload_file(
                upload["bytes"], upload["name"], upload["ext"]
            )
            file_info = payload["source_file_path"]
        except OSError:
            st.error("原始文件保存失败，机会未保存，请稍后重试。")
            return
    else:
        payload["source_kind"] = "paste"

    try:
        opportunity_id = database.create_opportunity(
            payload, allow_past_deadline=allow_past_deadline
        )
    except database.DeadlineConfirmationRequired as error:
        if file_info:
            database.remove_upload_file(file_info)
        st.session_state["pending_expired_save"] = str(error)
        return
    except database.DataValidationError as error:
        if file_info:
            database.remove_upload_file(file_info)
        st.error(f"无法保存：{error}")
        return
    except database.DatabaseError:
        if file_info:
            database.remove_upload_file(file_info)
        st.error("数据库暂时不可用，机会未保存，请稍后重试。")
        return

    st.session_state.pop("pending_expired_save", None)
    st.session_state["discover_flash"] = (
        f"已保存机会「{payload['name'].strip()}」（编号 {opportunity_id}）。"
    )
    st.session_state["reset_discover_form"] = True
    st.rerun()


def _clear_parse_state():
    for key in PARSE_STATE_KEYS:
        st.session_state.pop(key, None)


def _store_parse_result(source_text, upload=None):
    """解析成功后统一记录结果，供可编辑表单与保存逻辑复用。"""
    try:
        with st.spinner("正在调用 Kimi 解析内容……"):
            parsed = ai_parser.parse_notice(source_text)
    except ai_parser.AIParserError as error:
        # 解析失败：保留原始输入，用户可直接重试。
        st.error(str(error))
        return False

    parsed["raw_text"] = source_text
    st.session_state["parsed_values"] = parsed
    st.session_state["parsed_source_text"] = source_text
    st.session_state["show_parse_result"] = True
    st.session_state["pending_upload"] = upload
    st.session_state["parse_form_version"] = (
        st.session_state.get("parse_form_version", 0) + 1
    )
    return True


def _render_source_input(form_version):
    """渲染上传/粘贴两种录入方式，返回当前原始文本与上传文件信息。"""
    upload_tab, paste_tab = st.tabs(["上传文件", "粘贴文本"])

    uploaded = None
    with upload_tab:
        uploaded = st.file_uploader(
            "选择 PDF / TXT / DOCX 文件",
            type=UPLOAD_EXTENSIONS,
            key=f"discover-upload-{form_version}",
        )
        st.caption(
            f"支持 PDF、TXT、DOCX，单个文件不超过 "
            f"{database.MAX_UPLOAD_BYTES // (1024 * 1024)}MB。"
        )

    with paste_tab:
        notice_text = st.text_area(
            "机会通知",
            height=220,
            placeholder="在这里粘贴实习、竞赛、科研、奖学金、志愿活动等通知……",
            key=f"discover-text-{form_version}",
        )

    return uploaded, notice_text


def _extract_upload(uploaded):
    """校验并提取上传文件的文本，失败时返回 None 并提示原因。"""
    if uploaded.size > database.MAX_UPLOAD_BYTES:
        st.error(
            f"文件超过 {database.MAX_UPLOAD_BYTES // (1024 * 1024)}MB 上限，请压缩后再上传。"
        )
        return None

    file_ext = uploaded.name.rsplit(".", 1)[-1].lower()
    if file_ext not in UPLOAD_EXTENSIONS:
        st.error("暂不支持该文件类型，请上传 PDF、TXT 或 DOCX 文件。")
        return None

    try:
        with st.spinner("正在提取文件正文……"):
            content = text_extraction.extract_text(uploaded.getvalue(), file_ext)
    except text_extraction.TextExtractionError as error:
        st.error(str(error))
        return None
    except Exception:  # noqa: BLE001
        st.error("文件解析失败，请确认文件未损坏后重试。")
        return None

    return {
        "name": uploaded.name,
        "ext": file_ext,
        "bytes": uploaded.getvalue(),
        "content": content,
    }


def _handle_parse_click(uploaded, notice_text):
    """统一处理两种录入方式的解析请求。"""
    if uploaded is not None:
        extracted = _extract_upload(uploaded)
        if extracted is None:
            return
        if _store_parse_result(extracted["content"], upload=extracted):
            st.session_state["source_label"] = f"文件：{extracted['name']}"
        return

    text = (notice_text or "").strip()
    if not text:
        _clear_parse_state()
        st.session_state.pop("pending_expired_save", None)
        st.warning("请先上传文件或粘贴文本内容，再进行解析。")
        return
    if _store_parse_result(text):
        st.session_state["source_label"] = "粘贴文本"


def render_discover():
    """渲染发现机会页面。"""
    st.title("发现机会")
    st.caption("上传通知文件或粘贴文本，由 Kimi AI 提取字段，确认后保存到本地数据库。")

    flash = st.session_state.pop("discover_flash", None)
    if flash:
        st.success(flash)

    if st.session_state.pop("reset_discover_form", False):
        st.session_state.pop("pending_expired_save", None)
        _clear_parse_state()
        st.session_state["parse_form_version"] = (
            st.session_state.get("parse_form_version", 0) + 1
        )
        st.session_state["discover_input_version"] = (
            st.session_state.get("discover_input_version", 0) + 1
        )
        st.session_state["source_label"] = ""

    # 输入控件使用独立版本号，避免解析后输入内容被重置。
    input_version = st.session_state.get("discover_input_version", 0)
    uploaded, notice_text = _render_source_input(input_version)

    if st.button("AI 解析", type="primary"):
        _handle_parse_click(uploaded, notice_text)

    if not st.session_state.get("show_parse_result"):
        return

    current_source = (
        f"{uploaded.name}:{uploaded.size}" if uploaded is not None else (notice_text or "").strip()
    )
    stored_source = st.session_state.get("parsed_source_text", "")
    if _source_changed(uploaded, current_source, stored_source):
        _clear_parse_state()
        st.session_state.pop("pending_expired_save", None)
        st.caption("输入内容已变化，此前的解析结果已失效，请重新解析。")
        return

    source_label = st.session_state.get("source_label", "")
    if source_label:
        st.caption(f"解析来源：{source_label}")

    # 解析版本号在解析成功后已更新，这里再读取以匹配新建的控件 key。
    form_version = st.session_state.get("parse_form_version", 0)
    values = render_parse_result(form_version, st.session_state.get("parsed_values", {}))

    if st.button("保存机会", type="primary"):
        save_opportunity(values)

    pending_message = st.session_state.get("pending_expired_save")
    if pending_message:
        st.warning(pending_message)
        if st.button("确认保存过期机会", type="primary", key="confirm-expired-save"):
            save_opportunity(values, allow_past_deadline=True)


def _source_changed(uploaded, current_source, stored_source):
    """判断当前输入是否偏离了产生解析结果的来源。"""
    if uploaded is not None:
        pending = st.session_state.get("pending_upload") or {}
        stored_id = f"{pending.get('name')}:{len(pending.get('bytes', b''))}"
        return current_source != stored_id
    return current_source != (stored_source or "").strip()
