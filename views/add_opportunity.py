"""添加机会：输入通知，并展示固定的模拟解析结果。"""

import streamlit as st

from sample_data import MOCK_PARSE_RESULT

PARSE_FIELDS = [
    ("title", "机会名称"),
    ("category", "机会类型"),
    ("organization", "发布组织"),
    ("deadline", "截止日期"),
    ("requirements", "申请条件"),
    ("skills_required", "技能要求"),
    ("materials", "申请材料"),
    ("raw_content", "原始通知"),
]

TEXTAREA_FIELDS = {"requirements", "skills_required", "materials", "raw_content"}


def render_parse_result():
    """以可编辑控件展示预先写好的解析结果，不读取输入框内容，也不保存。"""
    st.info("模拟解析完成")
    st.warning("演示数据：未调用 AI，结果不会根据输入内容动态变化。")

    with st.container(border=True):
        for key, label in PARSE_FIELDS:
            widget_key = f"parse_{key}"
            if key in TEXTAREA_FIELDS:
                st.text_area(label, value=MOCK_PARSE_RESULT[key], key=widget_key)
            else:
                st.text_input(label, value=MOCK_PARSE_RESULT[key], key=widget_key)

    st.caption("以上内容仅用于演示，可编辑但不会被保存。数据库保存功能尚未实现。")


def render_add_opportunity():
    """渲染添加机会页面。"""
    st.title("添加机会")
    st.caption("粘贴一段机会通知。当前按钮只演示解析完成后的样子。")

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

    if st.session_state.get("show_mock_parse"):
        if st.session_state.get("parsed_source_text") != notice_text:
            st.session_state.pop("show_mock_parse", None)
            st.session_state.pop("parsed_source_text", None)
            st.caption("输入内容已变化，此前的模拟解析结果已失效。")
        else:
            render_parse_result()
