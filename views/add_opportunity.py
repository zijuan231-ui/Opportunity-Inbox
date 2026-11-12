"""添加机会：粘贴通知，调用 Kimi AI 解析，确认字段后保存到数据库。"""

import streamlit as st

import database
from sample_data import STATUS_ORDER
from services import ai_parser

PARSE_FIELDS = [
    ("name", "机会名称"),
    ("type", "机会类型"),
    ("organization", "发布组织"),
    ("deadline", "截止日期"),
    ("status", "申请状态"),
    ("requirements", "申请条件"),
    ("skills", "技能要求"),
    ("materials", "申请材料"),
    ("match_reason", "匹配理由"),
    ("gap_analysis", "能力差距"),
    ("raw_text", "原始通知"),
]

TEXTAREA_FIELDS = {
    "requirements",
    "skills",
    "materials",
    "match_reason",
    "gap_analysis",
    "raw_text",
}

DEFAULT_STATUS = "待评估"


def render_parse_result(form_version, parsed):
    """以可编辑控件展示 AI 解析结果，并返回用户填写的内容。"""
    st.info("Kimi AI 智能解析完成，请核对以下字段后再保存。")
    st.caption(
        "AI 只提取通知中明确出现的信息，缺失字段留空，请自行补充；"
        "所有字段都可以修改，保存时记录的是你确认后的内容。"
    )

    values = {}
    with st.container(border=True):
        for key, label in PARSE_FIELDS:
            widget_key = f"parse-{form_version}-{key}"
            if key == "status":
                current = parsed.get(key) or DEFAULT_STATUS
                values[key] = st.selectbox(
                    label,
                    STATUS_ORDER,
                    index=STATUS_ORDER.index(current),
                    key=widget_key,
                )
            elif key in TEXTAREA_FIELDS:
                values[key] = st.text_area(
                    label, value=parsed.get(key, ""), key=widget_key
                )
            else:
                values[key] = st.text_input(
                    label, value=parsed.get(key, ""), key=widget_key
                )
    return values


def save_opportunity(values, allow_past_deadline=False):
    """保存机会。校验失败时提示，成功时重置表单并重新运行。"""
    try:
        opportunity_id = database.create_opportunity(
            values, allow_past_deadline=allow_past_deadline
        )
    except database.DeadlineConfirmationRequired as error:
        st.session_state["pending_expired_save"] = str(error)
        return
    except database.DataValidationError as error:
        st.error(f"无法保存：{error}")
        return
    except database.DatabaseError:
        st.error("数据库暂时不可用，机会未保存，请稍后重试。")
        return

    st.session_state.pop("pending_expired_save", None)
    st.session_state["add_flash"] = (
        f"已保存机会「{values['name'].strip()}」（编号 {opportunity_id}）。"
    )
    st.session_state["reset_add_form"] = True
    st.rerun()


def _clear_parse_state():
    """清空解析相关的会话状态。"""
    for key in ("show_parse_result", "parsed_source_text", "parsed_values"):
        st.session_state.pop(key, None)


def render_add_opportunity():
    """渲染添加机会页面。"""
    st.title("添加机会")
    st.caption("粘贴一段机会通知，由 Kimi AI 提取字段，确认后保存到本地数据库。")

    flash = st.session_state.pop("add_flash", None)
    if flash:
        st.success(flash)

    if st.session_state.pop("reset_add_form", False):
        for key in ("notice_text", "pending_expired_save"):
            st.session_state.pop(key, None)
        _clear_parse_state()
        st.session_state["parse_form_version"] = (
            st.session_state.get("parse_form_version", 0) + 1
        )

    notice_text = st.text_area(
        "机会通知",
        height=220,
        placeholder="在这里粘贴实习、竞赛、科研项目或奖学金通知……",
        key="notice_text",
    )

    if st.button("Kimi AI 智能解析", type="primary"):
        if notice_text.strip():
            try:
                with st.spinner("正在调用 Kimi 解析通知……"):
                    parsed = ai_parser.parse_notice(notice_text)
            except ai_parser.AIParserError as error:
                # 解析失败：保留原始通知和已填写内容，用户可直接重试。
                st.error(str(error))
            else:
                parsed["raw_text"] = notice_text
                st.session_state["parsed_values"] = parsed
                st.session_state["parsed_source_text"] = notice_text
                st.session_state["show_parse_result"] = True
                st.session_state["parse_form_version"] = (
                    st.session_state.get("parse_form_version", 0) + 1
                )
        else:
            _clear_parse_state()
            st.session_state.pop("pending_expired_save", None)
            st.warning("请先粘贴机会通知内容，再点击解析。")

    if not st.session_state.get("show_parse_result"):
        return

    if st.session_state.get("parsed_source_text") != notice_text:
        _clear_parse_state()
        st.session_state.pop("pending_expired_save", None)
        st.caption("输入内容已变化，此前的解析结果已失效，请重新解析。")
        return

    form_version = st.session_state.get("parse_form_version", 0)
    values = render_parse_result(form_version, st.session_state.get("parsed_values", {}))

    if st.button("保存机会", type="primary"):
        save_opportunity(values)

    pending_message = st.session_state.get("pending_expired_save")
    if pending_message:
        st.warning(pending_message)
        if st.button("确认保存过期机会", type="primary", key="confirm-expired-save"):
            save_opportunity(values, allow_past_deadline=True)
