"""机会工作台：从 SQLite 读取机会，展示数量、状态和详情。"""

import json

import streamlit as st

import database
from sample_data import STATUS_ORDER

# Day 5：新增 5 个字段。key_dates / evidence 是 JSON 字符串，在 render_opportunity 里单独处理。
DETAIL_FIELDS = [
    ("type", "机会类型"),
    ("organization", "发布组织"),
    ("deadline", "主要报名截止"),
    ("source_link", "官方链接"),
    ("benefits", "机会回报"),
    ("registration_process", "报名流程"),
    ("requirements", "申请条件"),
    ("skills", "技能要求"),
    ("materials", "申请材料"),
    ("match_reason", "匹配理由"),
    ("gap_analysis", "能力差距"),
    ("raw_text", "原始通知"),
    ("source_file_name", "原始文件"),
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


def render_source_file(item):
    """展示并下载机会关联的原始文件；文件缺失时给出提示。"""
    if not item.get("source_file_path"):
        return
    try:
        path = database.resolve_upload_path(item["source_file_path"])
    except database.DataValidationError:
        st.caption("原始文件路径不合法，已隐藏。")
        return
    if not path.is_file():
        st.caption("原始文件已不存在，可能已被清理。")
        return
    with path.open("rb") as handle:
        st.download_button(
            "下载原始文件",
            data=handle.read(),
            file_name=item.get("source_file_name") or path.name,
            key=f"download-{item['id']}",
        )


def _render_source_link(value):
    """把链接渲染为可点击的 markdown。"""
    if not value:
        st.markdown("—")
        return
    stripped = value.strip()
    if stripped.startswith(("http://", "https://")):
        st.markdown(f"[{stripped}]({stripped})")
    else:
        st.markdown(display_value(value))


def _render_key_dates(raw_value):
    """把 key_dates JSON 字符串友好渲染为时间节点列表。"""
    if not raw_value:
        st.markdown("—")
        return
    try:
        data = json.loads(raw_value)
    except json.JSONDecodeError:
        st.markdown(display_value(raw_value))
        return
    if not isinstance(data, list) or not data:
        st.markdown("—")
        return
    def sort_key(item):
        if not isinstance(item, dict):
            return ""
        return item.get("start_date") or item.get("end_date") or ""
    sorted_items = sorted(data, key=sort_key)
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
        line = f"- **{event}** — {date_range}"
        if description:
            line += f"  （{description}）"
        st.markdown(line)


def _render_evidence(raw_value):
    """把 evidence JSON 字符串渲染为可展开的字段证据组。"""
    if not raw_value:
        st.markdown("—")
        return
    try:
        data = json.loads(raw_value)
    except json.JSONDecodeError:
        st.markdown(display_value(raw_value))
        return
    if not isinstance(data, dict) or not data:
        st.markdown("—")
        return
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


def render_opportunity(item):
    """在展开区域中展示一条机会的完整信息，并提供改状态和删除操作。"""
    with st.expander(f"{item['name']}  ·  {item['status']}"):
        for key, label in DETAIL_FIELDS:
            if key == "source_file_name" and not item.get(key):
                continue
            st.caption(label)

            # 特殊渲染
            if key == "source_link":
                _render_source_link(item.get(key, ""))
                continue

            st.markdown(display_value(item[key]))

        # Day 5：独立于普通 DETAIL_FIELDS 展示 JSON 字段，保持良好的可读性。
        # key_dates
        st.caption("关键时间节点")
        _render_key_dates(item.get("key_dates", ""))

        # evidence
        st.caption("原文依据")
        _render_evidence(item.get("evidence", ""))

        render_source_file(item)

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
    type_options = ["全部类型"] + [
        item_type
        for item_type in database.OPPORTUNITY_TYPES
        if any(opportunity["type"] == item_type for opportunity in opportunities)
    ]
    selected_type = st.selectbox("按机会类型筛选", type_options)
    if selected_type != "全部类型":
        opportunities = [
            opportunity
            for opportunity in opportunities
            if opportunity["type"] == selected_type
        ]
        st.caption(f"当前筛选：{selected_type}，共 {len(opportunities)} 条")

    for item in recent_opportunities(opportunities):
        render_opportunity(item)
