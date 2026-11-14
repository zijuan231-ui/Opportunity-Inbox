"""Day 5 三创赛通知真实 Kimi 回归测试。"""
import json
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录
sys.path.insert(0, ROOT)

from services import ai_parser

# 三创赛核心通知文本（根据用户提到的真实通知核心段落构造，保留关键信息）
SANCHUANG_NOTICE = """
关于举办第十七届全国大学生电子商务"创新、创意及创业"挑战赛的通知

各高等学校：
为深入贯彻落实《国家教育事业发展"十四五"规划》，推动电子商务专业教育教学改革与创新创业人才培养，教育部高等学校电子商务类专业教学指导委员会决定举办第十七届全国大学生电子商务"创新、创意及创业"挑战赛（以下简称"三创赛"）。现将有关事项通知如下：

一、组织机构
主办单位：教育部高等学校电子商务类专业教学指导委员会
承办单位：XX 大学

二、参赛对象与组队要求
1. 参赛对象：全国普通高等学校全日制在校本科生、硕士研究生和博士研究生，以本科生为主。
2. 参赛团队：每个团队由 3-5 名学生组成，设 1 名队长。
3. 指导教师：每个团队可邀请 0-2 名高校指导教师和 0-2 名企业指导教师。
4. 每位学生只能参加一个团队，每位指导教师最多指导 3 个团队。

三、时间安排
1. 校赛注册备案时间：2026 年 10 月 1 日至 2026 年 10 月 31 日（各高校向组委会备案参赛校赛信息）
2. 参赛队报名时间：2026 年 11 月 1 日至 2027 年 1 月 20 日（普通参赛者在线报名窗口）
3. 学校管理员审核时间：2027 年 1 月 21 日至 2027 年 1 月 31 日
4. 校赛选拔：由各高校自行组织，时间由学校确定
5. 省赛报名：2027 年 2 月 1 日至 2027 年 2 月 28 日
6. 省赛评审：2027 年 3 月 1 日至 2027 年 4 月 30 日
7. 全国总决赛：2027 年 6 月 1 日至 2027 年 6 月 5 日（现场答辩）
8. 成绩公示：2027 年 7 月
9. 证书发放：2027 年 8 月

四、报名流程
1. 队长登录三创赛官网（www.3chuang.com）注册账号
2. 队长创建团队并搜索成员，发送邀请
3. 成员接受邀请后，队长填写团队信息并提交
4. 学校管理员登录后台审核通过
5. 全部团队成员在线完成《全国大学生电子商务"创新、创意及创业"挑战赛赛事规则答题测试》，测试成绩达到 60 分以上方可正式参赛
6. 队长提交参赛作品申报书

五、申请材料
1. 参赛作品申报书（由参赛团队填写提交，普通学生参赛者需提交）
2. 校赛备案申请书（由学校管理员填写提交，普通学生参赛者无需提交）
3. 省级赛承办申请表（由申请承办省赛的单位填写，普通学生参赛者无需提交）
4. 省级赛安全承诺书（由省赛承办方填写，普通学生参赛者无需提交）

六、奖项设置
全国总决赛设特等奖、一等奖、二等奖、三等奖和优秀奖，获奖团队成员和指导教师将获得组委会颁发的荣誉证书。

七、报名网址
官方报名入口：https://www.3chuang.com
官方咨询邮箱：sanchuang@3chuang.com

八、联系方式
组委会秘书处电话：010-XXXXXXX
"""


def run_test():
    print("=" * 60)
    print("Day 5 三创赛通知真实 Kimi 回归测试")
    print("=" * 60)

    api_key = os.getenv("MOONSHOT_API_KEY", "")
    if not api_key:
        print("❌ MOONSHOT_API_KEY 未配置，跳过真实 API 测试")
        return False

    print(f"✅ API Key 已配置（前缀: {api_key[:8]}...）")
    print(f"📝 通知长度: {len(SANCHUANG_NOTICE)} 字符")
    print()

    try:
        print("🚀 正在调用 Kimi 解析……")
        parsed = ai_parser.parse_notice(SANCHUANG_NOTICE)
    except Exception as error:
        print(f"❌ 解析失败: {error}")
        traceback.print_exc()
        return False

    print()
    print("=" * 60)
    print("📊 解析结果")
    print("=" * 60)
    print(f"name:             {parsed['name']}")
    print(f"type:             {parsed['type']}")
    print(f"organization:     {parsed['organization']}")
    print(f"deadline:         {parsed['deadline']}")
    print()
    print(f"requirements:")
    print(f"  {parsed['requirements']}")
    print()
    print(f"skills:           {parsed['skills'] or '(空)'}")
    print(f"materials:")
    print(f"  {parsed['materials'] or '(空)'}")
    print()
    print(f"registration_process:")
    print(f"  {parsed['registration_process']}")
    print()
    print(f"source_link:      {parsed['source_link']}")
    print(f"benefits:")
    print(f"  {parsed['benefits'] or '(空)'}")
    print()

    # 解析 key_dates
    try:
        kd = json.loads(parsed["key_dates"])
        print(f"key_dates（共 {len(kd)} 项）:")
        for item in kd:
            e = item.get("event", "?")
            s = item.get("start_date", "")
            ed = item.get("end_date", "")
            d = item.get("description", "")
            date_range = f"{s} → {ed}" if s and ed else (s or ed or "待确认")
            print(f"  - {e}: {date_range}" + (f"  ({d})" if d else ""))
    except Exception:
        print(f"key_dates 原始值: {parsed['key_dates']}")
    print()

    # 解析 evidence
    try:
        ev = json.loads(parsed["evidence"])
        print(f"evidence（共 {len(ev)} 项）:")
        for field_name, entry in ev.items():
            if not isinstance(entry, dict):
                continue
            print(f"  📌 {field_name}")
            print(f"     value: {entry.get('value', '')}")
            quote = entry.get("quote", "")
            if quote:
                # 截断过长的 quote
                display_quote = quote[:120] + "..." if len(quote) > 120 else quote
                print(f"     quote: {display_quote}")
    except Exception:
        print(f"evidence 原始值: {parsed['evidence']}")
    print()

    # ============ 语义检查 ============
    print("=" * 60)
    print("✅ 语义检查")
    print("=" * 60)

    checks = []

    # 1. 名称
    checks.append(("名称包含三创赛/创新创意创业",
                   "三创" in parsed["name"] or "创新" in parsed["name"]))

    # 2. 类型 = 学科竞赛
    checks.append(("type=学科竞赛", parsed["type"] == "学科竞赛"))

    # 3. deadline = 2027-01-20（普通参赛者报名截止）
    checks.append(("deadline=2027-01-20（普通参赛者报名截止）",
                   parsed["deadline"] == "2027-01-20"))

    # 4. 发布组织
    checks.append(("organization 包含教育部或电子商务教指委",
                   "教育部" in parsed["organization"] or "电子商务" in parsed["organization"]))

    # 5. requirements 包含团队人数 3-5（可能写 "名" 或 "人"）
    checks.append(("requirements 包含 3-5 人/名团队",
                   "3" in parsed["requirements"] and "5" in parsed["requirements"]
                   and ("人" in parsed["requirements"] or "名" in parsed["requirements"])))

    # 6. requirements 包含队长
    checks.append(("requirements 提到队长", "队长" in parsed["requirements"]))

    # 7. requirements 提到指导老师
    checks.append(("requirements 提到指导老师", "指导" in parsed["requirements"]))

    # 8. skills 应为空（通知没明确要求）
    checks.append(("skills 为空（通知未明确要求）",
                   not parsed["skills"].strip()))

    # 9. materials 不应包含校赛备案申请书（承办方材料）
    checks.append(("materials 不包含校赛备案申请书",
                   "备案" not in parsed["materials"]))

    # 10. materials 不应包含省级赛承办申请表
    checks.append(("materials 不包含省级赛承办申请表",
                   "承办" not in parsed["materials"]))

    # 11. materials 包含参赛作品申报书
    checks.append(("materials 包含参赛作品申报书",
                   "申报" in parsed["materials"] or "参赛" in parsed["materials"]))

    # 12. registration_process 提到队长创建团队
    checks.append(("registration_process 提到队长创建团队",
                   "队长" in parsed["registration_process"] and "创建" in parsed["registration_process"]))

    # 13. registration_process 提到答题测试
    checks.append(("registration_process 提到答题测试",
                   "答题" in parsed["registration_process"] or "测试" in parsed["registration_process"]))

    # 14. source_link 包含 3chuang.com
    checks.append(("source_link 包含 3chuang.com",
                   "3chuang" in parsed["source_link"]))

    # 15. benefits 包含证书
    checks.append(("benefits 包含证书", "证书" in parsed["benefits"]))

    # 16. key_dates 至少有 5 项
    kd_list = []
    try:
        kd_list = json.loads(parsed["key_dates"])
    except Exception:
        pass
    checks.append((f"key_dates 至少有 5 项（实际 {len(kd_list)}）", len(kd_list) >= 5))

    # 17. key_dates 包含参赛队报名（2027-01-20）
    kd_events = [item.get("event", "") for item in kd_list]
    checks.append(("key_dates 包含参赛队报名事件",
                   any("报名" in e for e in kd_events)))

    # 18. key_dates 包含全国总决赛
    checks.append(("key_dates 包含全国总决赛事件",
                   any("总决赛" in e for e in kd_events)))

    # 19. key_dates 包含校赛备案（不同事件，不同日期）
    checks.append(("key_dates 包含校赛/备案事件",
                   any("备案" in e or "校赛" in e for e in kd_events)))

    # 20. evidence 不为空
    ev_dict = {}
    try:
        ev_dict = json.loads(parsed["evidence"])
    except Exception:
        pass
    checks.append((f"evidence 不为空（共 {len(ev_dict)} 项）", len(ev_dict) > 0))

    # 21. evidence 里 quote 非空
    has_real_quote = False
    for entry in ev_dict.values():
        if isinstance(entry, dict) and entry.get("quote", "").strip():
            has_real_quote = True
            break
    checks.append(("evidence 至少有一条带真实 quote", has_real_quote))

    # 汇总
    passed = 0
    failed = 0
    for label, ok in checks:
        status = "✅" if ok else "❌"
        print(f"  {status} {label}")
        if ok:
            passed += 1
        else:
            failed += 1

    print()
    print(f"📈 通过: {passed}/{len(checks)}")
    if failed == 0:
        print("🎉 全部通过！Day 5 解析升级验证成功。")
    else:
        print(f"⚠️  有 {failed} 项检查未通过，建议复盘。")

    return failed == 0


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
