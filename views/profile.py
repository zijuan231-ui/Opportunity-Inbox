"""个人画像：展示一份示例用户资料。"""

import streamlit as st

from sample_data import USER_PROFILE


def render_profile():
    """渲染只读的示例个人画像。"""
    profile = USER_PROFILE

    st.subheader("个人画像", anchor=False)
    st.caption("这是一份示例资料，用来预览画像页面的内容结构。")

    with st.container(border=True, gap="small"):
        st.markdown("##### 基本信息")
        education_col, major_col, grade_col = st.columns([1, 2, 1], gap="small")
        with education_col:
            st.caption("学历阶段")
            st.markdown(profile["education"])
        with major_col:
            st.caption("专业")
            st.markdown(profile["major"])
        with grade_col:
            st.caption("年级")
            st.markdown(profile["grade"])

    with st.container(border=True, gap="small"):
        st.markdown("##### 技能")
        for skill in profile["skills"]:
            st.markdown(f"{skill['name']} · {skill['level']}")

    with st.container(border=True, gap="small"):
        st.markdown("##### 项目经历")
        for project in profile["projects"]:
            st.markdown(f"**{project['name']}**")
            st.markdown(project["detail"])

    with st.container(border=True, gap="small"):
        st.markdown("##### 兴趣方向")
        st.markdown("、".join(profile["interests"]))

    with st.container(border=True, gap="small"):
        st.markdown("##### 发展目标")
        st.markdown(profile["goals"])

    with st.container(border=True, gap="small"):
        st.markdown("##### 其他限制或偏好")
        st.markdown(profile["constraints"])
