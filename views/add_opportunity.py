"""添加机会：粘贴通知，展示可编辑的模拟解析结果，并保存到数据库。"""

import streamlit as st

import database
from sample_data import MOCK_PARSE_RESULT, STATUS_ORDER

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

# 模拟解析的初始值。演示数据固定，不随输入内容变化。
MOCK_DEFAULTS = {
    "name": MOCK_PARSE_RESULT["title"],
    "type": MOCK_PARSE_RESULT["category"],
    "organization": MOCK_PARSE_RESULT["organization"],
    "deadline": MOCK_PARSE_RESULT["deadline"],
    "status": "待评估",
    "requirements": MOCK_PARSE_RESULT["requirements"],
    "skills": MOCK_PARSE_RESULT["skills_required"],
    "materials": MOCK_PARSE_RESULT["materials"],
    "match_reason": "",
    "gap_analysis": "",
    "raw_text": MOCK_PARSE_RESULT["raw_content"],
}


def render_parse_result(form_version):
    """以可编辑控件展示预先写好的解析结果，并返回用户填写的内容。"""
    st.info("模拟解析完成")
    st.warning("演示数据：未调用 AI，解析结果固定，不会根据输入内容动态变化。")
    st.caption("下面字段可以自由修改，保存时记录的是你确认后的内容，不代表已经完成 AI 解析。")

    values = {}
    with st.container(border=True):
        for key, label in PARSE_FIELDS:
            widget_key = f"parse-{form_version}-{key}"
            if key == "status":
                values[key] = st.selectbox(
                    label,
                    STATUS_ORDER,
                    index=STATUS_ORDER.index(MOCK_DEFAULTS[key]),
                    key=widget_key,
                )
            elif key in TEXTAREA_FIELDS:
                values[key] = st.text_area(
                    label, value=MOCK_DEFAULTS[key], key=widget_key
                )
            else:
                values[key] = st.text_input(
                    label, value=MOCK_DEFAULTS[key], key=widget_key
                )
    return values


def render_add_opportunity():
    """渲染添加机会页面。"""
    st.title("添加机会")
    st.caption("粘贴一段机会通知，确认字段后保存到本地数据库。")

    flash = st.session_state.pop("add_flash", None)
    if flash:
        st.success(flash)

    if st.session_state.pop("reset_add_form", False):
        for key in ("notice_text", "show_mock_parse", "parsed_source_text"):
            st.session_state.pop(key, None)
        st.session_state["parse_form_version"] = (
            st.session_state.get("parse_form_version", 0) + 1
        )

    notice_text = st.text_area(
        "机会通知",
        height=220,
        placeholder="在这里粘贴实习、竞赛、科研项目或奖学金通知……",
        key="notice_text",
    )

    if st.button("模拟解析", type="primary"):
        if notice_text.strip():
            st.session_state["show_mock_parse"] = True
            st.session_state["parsed_source_text"] = notice_text
        else:
            st.session_state.pop("show_mock_parse", None)
            st.session_state.pop("parsed_source_text", None)
            st.warning("请先粘贴机会通知内容，再点击模拟解析。")

    if not st.session_state.get("show_mock_parse"):
        return

    if st.session_state.get("parsed_source_text") != notice_text:
        st.session_state.pop("show_mock_parse", None)
        st.session_state.pop("parsed_source_text", None)
        st.caption("输入内容已变化，此前的模拟解析结果已失效。")
        return

    form_version = st.session_state.get("parse_form_version", 0)
    values = render_parse_result(form_version)

    if st.button("保存机会", type="primary"):
        try:
            opportunity_id = database.create_opportunity(values)
        except database.DataValidationError as error:
            st.error(f"无法保存：{error}")
        except database.DatabaseError:
            st.error("数据库暂时不可用，机会未保存，请稍后重试。")
        else:
            st.session_state["add_flash"] = (
                f"已保存机会「{values['name'].strip()}」（编号 {opportunity_id}）。"
            )
            st.session_state["reset_add_form"] = True
            st.rerun()
