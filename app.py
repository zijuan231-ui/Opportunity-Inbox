"""Opportunity Inbox 应用入口。"""

import streamlit as st

import database
from views.add_opportunity import render_discover
from views.knowledge import render_knowledge
from views.profile import render_profile
from views.workbench import render_workbench

PAGES = {
    "机会工作台": render_workbench,
    "发现机会": render_discover,
    "个人画像": render_profile,
}

# 知识库转为开发者后台维护入口，不占用普通用户的一级导航。
BACKGROUND_PAGES = {
    "知识库（后台）": render_knowledge,
}


@st.cache_resource
def bootstrap_database():
    """每个进程只初始化一次：建表，并在空库中导入演示数据。"""
    database.init_db()


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

    try:
        bootstrap_database()
    except database.DatabaseError:
        st.error("数据库初始化失败，请检查 data/ 目录是否可写后重试。")
        st.stop()

    with st.sidebar:
        st.header("Opportunity Inbox")
        st.caption("机会发现与决策助手")
        page_name = st.radio("功能", list(PAGES), label_visibility="collapsed")
        with st.expander("开发者工具"):
            show_background = st.toggle("显示知识库后台", value=False)
            background_name = None
            if show_background:
                background_name = st.radio(
                    "后台功能",
                    list(BACKGROUND_PAGES),
                    label_visibility="collapsed",
                )

    # 打开后台开关后优先展示后台页面，否则展示普通用户页面。
    if background_name:
        BACKGROUND_PAGES[background_name]()
    else:
        PAGES[page_name]()


main()
