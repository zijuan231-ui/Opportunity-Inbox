"""机会工作台：数量、状态和最近添加的机会。"""

import streamlit as st

from sample_data import OPPORTUNITIES, STATUS_ORDER

DETAIL_FIELDS = [
    ("category", "机会类型"),
    ("organization", "发布组织"),
    ("deadline", "截止日期"),
    ("status", "当前状态"),
    ("created_at", "添加日期"),
    ("requirements", "申请条件"),
    ("skills_required", "技能要求"),
    ("materials", "申请材料"),
    ("raw_content", "原始通知"),
]


def count_by_status(opportunities, status):
    """统计某个状态在机会列表中出现的次数。"""
    return sum(1 for item in opportunities if item["status"] == status)


def recent_opportunities(opportunities):
    """按添加日期从新到旧排列机会。"""
    return sorted(opportunities, key=lambda item: item["created_at"], reverse=True)


def render_opportunity(item):
    """在展开区域中展示一条机会的完整信息。"""
    with st.expander(f"{item['title']}  ·  {item['status']}"):
        for key, label in DETAIL_FIELDS:
            st.markdown(f"**{label}**")
            st.write(item[key])


def render_workbench():
    """渲染机会工作台。统计数字全部来自机会列表。"""
    st.title("机会工作台")
    st.caption("查看已保存的机会、数量和当前状态。")

    total = len(OPPORTUNITIES)
    preparing = count_by_status(OPPORTUNITIES, "准备中")

    total_col, preparing_col = st.columns(2)
    total_col.metric("机会数量", total)
    preparing_col.metric("准备中", preparing)

    st.subheader("机会状态")
    status_cols = st.columns(len(STATUS_ORDER))
    for column, status in zip(status_cols, STATUS_ORDER):
        column.metric(status, count_by_status(OPPORTUNITIES, status))

    st.subheader("最近添加")
    for item in recent_opportunities(OPPORTUNITIES):
        render_opportunity(item)
