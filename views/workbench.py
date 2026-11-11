"""机会工作台：从 SQLite 读取机会，展示数量、状态和详情。"""

import streamlit as st

import database
from sample_data import STATUS_ORDER

DETAIL_FIELDS = [
    ("type", "机会类型"),
    ("organization", "发布组织"),
    ("deadline", "截止日期"),
    ("status", "当前状态"),
    ("match_reason", "匹配理由"),
    ("gap_analysis", "能力差距"),
    ("requirements", "申请条件"),
    ("skills", "技能要求"),
    ("materials", "申请材料"),
    ("raw_text", "原始通知"),
    ("created_at", "添加时间"),
    ("updated_at", "更新时间"),
]


def count_by_status(opportunities, status):
    """统计某个状态在机会列表中出现的次数。"""
    return sum(1 for item in opportunities if item["status"] == status)


def recent_opportunities(opportunities):
    """按添加时间从新到旧排列机会。"""
    return sorted(
        opportunities,
        key=lambda item: (item["created_at"], item["id"]),
        reverse=True,
    )


def display_value(value):
    """空字段统一显示为破折号，避免出现空白行。"""
    text = (value or "").strip()
    return text or "—"


def set_flash(kind, message):
    """记录一条提示，在下次页面运行时展示。"""
    st.session_state["workbench_flash"] = {"kind": kind, "message": message}


def show_flash():
    """展示并清除上一次操作留下的提示。"""
    flash = st.session_state.pop("workbench_flash", None)
    if flash:
        getattr(st, flash["kind"])(flash["message"])


def render_opportunity(item):
    """在展开区域中展示一条机会的完整信息，并提供改状态和删除操作。"""
    with st.expander(f"{item['name']}  ·  {item['status']}"):
        for key, label in DETAIL_FIELDS:
            st.caption(label)
            st.markdown(display_value(item[key]))

        st.space("small")
        status_col, save_col, delete_col = st.columns(
            [2, 1, 1], vertical_alignment="bottom"
        )

        with status_col:
            current_index = (
                STATUS_ORDER.index(item["status"])
                if item["status"] in STATUS_ORDER
                else 0
            )
            new_status = st.selectbox(
                "申请状态",
                STATUS_ORDER,
                index=current_index,
                key=f"status-select-{item['id']}",
            )

        with save_col:
            if st.button(
                "保存状态",
                key=f"status-save-{item['id']}",
                width="stretch",
            ):
                try:
                    updated = database.update_status(item["id"], new_status)
                except database.DatabaseError:
                    set_flash("error", "数据库暂时不可用，状态未更新。")
                else:
                    if updated:
                        set_flash(
                            "success",
                            f"已将「{item['name']}」的状态更新为「{new_status}」。",
                        )
                    else:
                        set_flash("warning", "没有找到这条机会，可能已被删除。")
                st.rerun()

        with delete_col:
            with st.popover("删除"):
                st.markdown(f"确认删除「{item['name']}」吗？此操作无法撤销。")
                if st.button(
                    "确认删除",
                    key=f"delete-{item['id']}",
                    type="primary",
                    width="stretch",
                ):
                    try:
                        deleted = database.delete_opportunity(item["id"])
                    except database.DatabaseError:
                        set_flash("error", "数据库暂时不可用，机会未删除。")
                    else:
                        if deleted:
                            set_flash("success", f"已删除「{item['name']}」。")
                        else:
                            set_flash("warning", "没有找到这条机会，可能已被删除。")
                    st.rerun()


def render_workbench():
    """渲染机会工作台。统计数字全部来自数据库中的机会列表。"""
    st.title("机会工作台")
    st.caption("查看已保存的机会、数量和当前状态。")
    show_flash()

    try:
        opportunities = database.list_opportunities()
    except database.DatabaseError:
        st.error("无法读取机会数据，请检查数据库文件后重试。")
        return

    if not opportunities:
        st.info("还没有保存的机会，可以到「添加机会」页面添加第一条。")
        return

    total = len(opportunities)
    preparing = count_by_status(opportunities, "准备中")

    total_col, preparing_col = st.columns(2)
    total_col.metric("机会数量", total)
    preparing_col.metric("准备中", preparing)

    st.subheader("机会状态")
    status_cols = st.columns(len(STATUS_ORDER))
    for column, status in zip(status_cols, STATUS_ORDER):
        column.metric(status, count_by_status(opportunities, status))

    st.subheader("最近添加")
    for item in recent_opportunities(opportunities):
        render_opportunity(item)
