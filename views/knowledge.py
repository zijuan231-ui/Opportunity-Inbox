"""知识库管理：上传/粘贴资料，查看详情，编辑元数据，删除并清理文件。"""

import streamlit as st

import database
from services import text_extraction

CATEGORY_OPTIONS = list(database.KNOWLEDGE_CATEGORIES)

SOURCE_TYPE_LABELS = {
    "official": "官方渠道",
    "general": "通用公开资料",
    "third_party": "第三方整理",
    "unknown": "不确定",
}
SOURCE_TYPE_OPTIONS = list(SOURCE_TYPE_LABELS)

UPLOAD_EXTENSIONS = ["pdf", "txt", "docx"]


def _split_tags(raw):
    """把逗号分隔的标签文本拆成列表，去空去重并保留顺序。"""
    parts = []
    for chunk in (raw or "").replace("，", ",").replace("、", ",").split(","):
        tag = chunk.strip()
        if tag and tag not in parts:
            parts.append(tag)
    return parts


def _normalize_tags(raw):
    """标签统一存成逗号分隔字符串。"""
    return ",".join(_split_tags(raw))


def _flash(message):
    st.session_state["kb_flash"] = message


def _bump_form_version():
    st.session_state["kb_form_version"] = (
        st.session_state.get("kb_form_version", 0) + 1
    )


def _metadata_inputs(version, defaults=None):
    """渲染共用的元数据输入控件，返回当前填写值。"""
    defaults = defaults or {}
    with st.container(border=True):
        left, right = st.columns([2, 1])
        with left:
            title = st.text_input(
                "资料名称",
                value=defaults.get("title", ""),
                placeholder="例如：实验室招新通知 / 计算机设计大赛章程",
                key=f"kb-title-{version}",
            )
            org_col, target_col = st.columns(2)
            organization = org_col.text_input(
                "发布组织（选填）",
                value=defaults.get("organization", ""),
                placeholder="企业、学校、学院、实验室、主办方或社团",
                key=f"kb-organization-{version}",
            )
            target = target_col.text_input(
                "相关对象/方向（选填）",
                value=defaults.get("target", ""),
                placeholder="岗位、竞赛、项目或研究方向",
                key=f"kb-target-{version}",
            )
            tags = st.text_input(
                "自定义标签（选填）",
                value=defaults.get("tags", ""),
                placeholder="多个标签用逗号分隔，例如：数据科学, 面试经验",
                key=f"kb-tags-{version}",
            )
        with right:
            category = st.selectbox("资料分类", CATEGORY_OPTIONS, key=f"kb-category-{version}")
            source_type_label = st.selectbox(
                "来源类型", SOURCE_TYPE_OPTIONS,
                format_func=SOURCE_TYPE_LABELS.get,
                index=SOURCE_TYPE_OPTIONS.index(defaults.get("source_type", "unknown"))
                if defaults.get("source_type") in SOURCE_TYPE_OPTIONS else 3,
                key=f"kb-source-type-{version}",
            )
            source_url = st.text_input(
                "原始链接（选填）",
                value=defaults.get("source_url", ""),
                key=f"kb-source-url-{version}",
            )
    return {
        "title": title,
        "category": category,
        "organization": organization,
        "target": target,
        "tags": tags,
        "source_type": source_type_label,
        "source_url": source_url,
    }


def _save_document(values, input_method, content, file_info=None):
    """写库；上传文件写库失败时清理已保存的文件。"""
    payload = dict(values)
    payload["input_method"] = input_method
    payload["content"] = content
    payload["tags"] = _normalize_tags(payload.get("tags", ""))
    if file_info:
        payload.update(file_info)
    try:
        document_id = database.create_document(payload)
    except database.DataValidationError as error:
        if file_info:
            database.remove_upload_file(file_info["file_path"])
        st.error(f"无法保存：{error}")
        return
    except database.DatabaseError:
        if file_info:
            database.remove_upload_file(file_info["file_path"])
        st.error("数据库暂时不可用，资料未保存，请稍后重试。")
        return

    _flash(f"已保存资料「{payload['title'].strip()}」（编号 {document_id}）。")
    _bump_form_version()
    st.rerun()


def _render_add_section():
    st.subheader("添加资料")
    version = st.session_state.get("kb_form_version", 0)

    upload_tab, paste_tab = st.tabs(["上传文件", "粘贴文本"])
    with upload_tab:
        uploaded = st.file_uploader(
            "选择 PDF / TXT / DOCX 文件",
            type=UPLOAD_EXTENSIONS,
            key=f"kb-upload-{version}",
        )
        if uploaded is not None:
            st.caption(
                f"已选择：{uploaded.name}（{uploaded.size / 1024:.0f} KB），"
                f"单个文件不超过 {database.MAX_UPLOAD_BYTES // (1024 * 1024)}MB。"
            )
    with paste_tab:
        pasted_text = st.text_area(
            "资料内容",
            height=200,
            placeholder="在这里粘贴招聘公告、岗位 JD 或其他文本资料……",
            key=f"kb-paste-{version}",
        )

    values = _metadata_inputs(version)

    if st.button("保存资料", type="primary"):
        if uploaded is not None:
            _save_uploaded(uploaded, values)
        elif (pasted_text or "").strip():
            title = values["title"].strip() or "未命名资料"
            _save_document({**values, "title": title}, "paste", pasted_text.strip())
        else:
            st.warning("请先上传文件或粘贴文本内容。")


def _save_uploaded(uploaded, values):
    """校验并解析上传文件，提取文本后保存。"""
    if uploaded.size > database.MAX_UPLOAD_BYTES:
        st.error(
            f"文件超过 {database.MAX_UPLOAD_BYTES // (1024 * 1024)}MB 上限，请压缩后再上传。"
        )
        return

    file_ext = uploaded.name.rsplit(".", 1)[-1].lower()
    try:
        with st.spinner("正在提取文件文本……"):
            content = text_extraction.extract_text(uploaded.getvalue(), file_ext)
    except text_extraction.TextExtractionError as error:
        st.error(str(error))
        return
    except Exception:  # noqa: BLE001
        st.error("文件解析失败，请确认文件未损坏后重试。")
        return

    title = values["title"].strip() or uploaded.name.rsplit(".", 1)[0]
    file_path = database.save_upload_file(uploaded.getvalue(), uploaded.name, file_ext)
    file_info = {
        "file_name": uploaded.name,
        "file_path": file_path,
        "file_ext": file_ext,
    }
    _save_document({**values, "title": title}, "upload", content, file_info)


def _render_document(doc):
    """渲染单条资料的卡片：详情、编辑、删除。"""
    source_label = SOURCE_TYPE_LABELS.get(doc["source_type"], doc["source_type"])
    summary = " ｜ ".join(
        part for part in (
            doc["category"],
            doc["organization"] or "组织未填",
            doc["target"] or "对象未填",
            f"来源：{source_label}",
            f"{'上传' if doc['input_method'] == 'upload' else '粘贴'}于 {doc['created_at'][:10]}",
            f"{len(doc['content'])} 字",
        )
    )
    with st.expander(f"{doc['title']}"):
        st.caption(summary)
        if doc["tags"]:
            st.caption("　".join(f"#{tag}" for tag in _split_tags(doc["tags"])))
        if doc["source_url"]:
            st.markdown(f"[原始链接]({doc['source_url']})")

        with st.expander("查看全文"):
            st.text(doc["content"])

        with st.expander("编辑元数据"):
            values = _edit_inputs(doc)
            if st.button("保存修改", key=f"kb-edit-save-{doc['id']}"):
                _save_edit(doc, values)

        with st.popover("删除"):
            st.markdown(f"确认删除「{doc['title']}」吗？此操作无法撤销。")
            if doc["file_path"]:
                st.caption("将同时删除已上传的原始文件。")
            if st.button("确认删除", type="primary", key=f"kb-del-confirm-{doc['id']}"):
                _delete_document(doc)


def _edit_inputs(doc):
    with st.container():
        title = st.text_input("资料名称", value=doc["title"], key=f"kb-edit-title-{doc['id']}")
        org_col, target_col = st.columns(2)
        organization = org_col.text_input("发布组织", value=doc["organization"], key=f"kb-edit-org-{doc['id']}")
        target = target_col.text_input("相关对象/方向", value=doc["target"], key=f"kb-edit-target-{doc['id']}")
        tags = st.text_input(
            "自定义标签（逗号分隔）", value=doc["tags"], key=f"kb-edit-tags-{doc['id']}"
        )
        category = st.selectbox(
            "资料分类", CATEGORY_OPTIONS,
            index=CATEGORY_OPTIONS.index(doc["category"]) if doc["category"] in CATEGORY_OPTIONS else 8,
            key=f"kb-edit-category-{doc['id']}",
        )
        source_type = st.selectbox(
            "来源类型", SOURCE_TYPE_OPTIONS,
            format_func=SOURCE_TYPE_LABELS.get,
            index=SOURCE_TYPE_OPTIONS.index(doc["source_type"]) if doc["source_type"] in SOURCE_TYPE_OPTIONS else 3,
            key=f"kb-edit-source-type-{doc['id']}",
        )
        source_url = st.text_input("原始链接", value=doc["source_url"], key=f"kb-edit-url-{doc['id']}")
    return {
        "title": title, "organization": organization, "target": target,
        "tags": tags, "category": category, "source_type": source_type,
        "source_url": source_url,
    }


def _save_edit(doc, values):
    payload = {**doc, **values}
    payload["tags"] = _normalize_tags(values.get("tags", ""))
    try:
        database.update_document(doc["id"], payload)
    except database.DataValidationError as error:
        st.error(f"无法保存修改：{error}")
        return
    except database.DatabaseError:
        st.error("数据库暂时不可用，修改未保存，请稍后重试。")
        return
    _flash(f"已更新资料「{values['title'].strip()}」。")
    st.rerun()


def _delete_document(doc):
    try:
        deleted = database.delete_document(doc["id"])
    except database.DatabaseError:
        st.error("数据库暂时不可用，删除失败，请稍后重试。")
        return
    if deleted and doc["file_path"]:
        # 数据库记录已删除；文件清理失败只记日志，不影响列表刷新。
        database.remove_upload_file(doc["file_path"])
    _flash(f"已删除资料「{doc['title']}」。")
    st.rerun()


def render_knowledge():
    """渲染知识库页面。"""
    st.title("知识库")
    st.caption("保存岗位 JD、企业资料和招聘规则，为后续匹配分析做准备。")

    flash = st.session_state.pop("kb_flash", None)
    if flash:
        st.success(flash)

    _render_add_section()

    st.subheader("已保存资料")
    documents = database.list_documents()
    if not documents:
        st.info("知识库还是空的，先添加一份资料吧。")
        return

    category_filter = st.selectbox("按分类筛选", ["全部分类"] + CATEGORY_OPTIONS)
    if category_filter != "全部分类":
        documents = [d for d in documents if d["category"] == category_filter]

    st.caption(f"共 {len(documents)} 条资料")
    for doc in documents:
        _render_document(doc)
