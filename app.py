"""Opportunity Inbox 静态原型入口。"""

import streamlit as st

from views.add_opportunity import render_add_opportunity
from views.profile import render_profile
from views.workbench import render_workbench

PAGES = {
    "机会工作台": render_workbench,
    "添加机会": render_add_opportunity,
    "个人画像": render_profile,
}


def apply_local_style():
    """补充本地样式：留白、白卡片和蓝色强调。不加载外部资源。"""
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 920px;
            padding-top: 2.2rem;
            padding-bottom: 3rem;
        }
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e6e8ec;
        }
        [data-testid="stSidebar"] .block-container {
            padding-top: 1.6rem;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e6e8ec;
            border-radius: 12px;
            padding: 0.75rem 0.9rem;
        }
        div[data-testid="stExpander"] {
            background: #ffffff;
            border-radius: 12px;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border-radius: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    """配置页面，并通过侧边栏切换三个视图。"""
    st.set_page_config(
        page_title="Opportunity Inbox",
        page_icon="📥",
        layout="centered",
        initial_sidebar_state="expanded",
    )
    apply_local_style()

    with st.sidebar:
        st.header("Opportunity Inbox")
        st.caption("机会发现与决策助手")
        page_name = st.radio("功能", list(PAGES), label_visibility="collapsed")

    PAGES[page_name]()


main()
