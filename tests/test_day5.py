"""Day 5 AI 解析升级单元测试。

覆盖：
- ai_parser._validate_fields（dict 不再清空、JSON 结构化字段、type 超出枚举降级）
- ai_parser._validate_text / _validate_structured / _inject_type_evidence
- database 迁移函数（DAY5 新增列）
- database.create_opportunity / update_opportunity / list_opportunities 新字段
- 集成：用 mock 的 parse_notice 返回值走完整保存 → 读取链路
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# 把项目根目录加进 sys.path，确保 import 的是项目自身代码。
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import database
from database import (
    _normalize,
    COLUMNS,
    OPPORTUNITY_TYPES,
    DEFAULT_OPPORTUNITY_TYPE,
    DataValidationError,
)
from services import ai_parser
from services.ai_parser import (
    _extract_json,
    _safe_json_dumps,
    _try_parse_json_string,
    _validate_fields,
    _validate_structured,
    _validate_text,
    _inject_type_evidence,
    EXTRACT_FIELDS,
)


# =====================================================================
# 一、ai_parser 单元测试
# =====================================================================


class TestValidateText(unittest.TestCase):
    """_validate_text 把任意类型安全降级为字符串。"""

    def test_string_strip(self):
        self.assertEqual(_validate_text("  hello  ", "name"), "hello")

    def test_none(self):
        self.assertEqual(_validate_text(None, "name"), "")

    def test_scalar_list_joined(self):
        self.assertEqual(
            _validate_text(["简历", "推荐信"], "materials"), "简历；推荐信"
        )

    def test_complex_list_serialized(self):
        value = [{"a": 1}, {"b": 2}]
        result = _validate_text(value, "name")
        # 不应是 Python dict 的 repr，应是合法 JSON
        parsed = json.loads(result)
        self.assertEqual(parsed, value)

    def test_dict_not_emptied_but_serialized(self):
        """Day 5 关键修复：dict 不再直接清空。"""
        value = {"key1": "val1", "key2": 123}
        result = _validate_text(value, "name")
        self.assertNotEqual(result, "")
        parsed = json.loads(result)
        self.assertEqual(parsed, value)


class TestValidateStructured(unittest.TestCase):
    """_validate_structured 处理 key_dates / evidence 两个 JSON 字段。"""

    # --- key_dates ---
    def test_key_dates_list_ok(self):
        data = [
            {"event": "报名", "start_date": "2027-01-01", "end_date": "2027-01-20", "description": ""}
        ]
        result = _validate_structured("key_dates", data)
        parsed = json.loads(result)
        self.assertEqual(parsed, data)

    def test_key_dates_none(self):
        self.assertEqual(_validate_structured("key_dates", None), "[]")

    def test_key_dates_string_json(self):
        """模型可能把 JSON 当字符串返回。"""
        s = '[{"event":"报名","start_date":"2027-01-01","end_date":"","description":""}]'
        result = _validate_structured("key_dates", s)
        parsed = json.loads(result)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["event"], "报名")

    def test_key_dates_string_invalid(self):
        result = _validate_structured("key_dates", "not json")
        self.assertEqual(result, "[]")

    def test_key_dates_wrong_type_dict(self):
        """类型不匹配 -> 安全降级为空数组，不抛异常。"""
        result = _validate_structured("key_dates", {"a": 1})
        self.assertEqual(result, "[]")

    # --- evidence ---
    def test_evidence_dict_ok(self):
        data = {
            "deadline": {"value": "2027-01-20", "quote": "截止日期2027年1月20日"}
        }
        result = _validate_structured("evidence", data)
        parsed = json.loads(result)
        self.assertEqual(parsed, data)

    def test_evidence_none(self):
        self.assertEqual(_validate_structured("evidence", None), "{}")

    def test_evidence_string_json(self):
        s = '{"name":{"value":"测试","quote":"测试名称"}}'
        result = _validate_structured("evidence", s)
        parsed = json.loads(result)
        self.assertEqual(parsed["name"]["value"], "测试")

    def test_evidence_wrong_type_list(self):
        result = _validate_structured("evidence", [1, 2, 3])
        self.assertEqual(result, "{}")


class TestValidateFieldsIntegration(unittest.TestCase):
    """_validate_fields 端到端校验。"""

    def test_minimal_valid(self):
        data = {
            "name": "测试",
            "type": "学科竞赛",
            "deadline": "2027-01-20",
            "requirements": "",
            "skills": "",
            "materials": "",
            "registration_process": "注册 → 填写",
            "source_link": "https://example.com",
            "benefits": "证书",
            "key_dates": [],
            "evidence": {},
            "organization": "某大学",
        }
        result = _validate_fields(data)
        for field in EXTRACT_FIELDS:
            self.assertIn(field, result)
        self.assertEqual(result["name"], "测试")
        self.assertEqual(result["type"], "学科竞赛")
        self.assertEqual(result["key_dates"], "[]")
        self.assertEqual(result["evidence"], "{}")

    def test_deadline_non_iso_cleared(self):
        data = {
            "name": "测试", "type": "其他", "deadline": "2027/1/20",
            "requirements": "", "skills": "", "materials": "",
            "registration_process": "", "source_link": "", "benefits": "",
            "key_dates": [], "evidence": {}, "organization": "",
        }
        result = _validate_fields(data)
        self.assertEqual(result["deadline"], "")

    def test_type_out_of_enum_falls_back_and_evidence_injected(self):
        data = {
            "name": "测试", "type": "创业孵化", "deadline": "2027-01-20",
            "requirements": "", "skills": "", "materials": "",
            "registration_process": "", "source_link": "", "benefits": "",
            "key_dates": [], "evidence": {}, "organization": "",
        }
        result = _validate_fields(data)
        self.assertEqual(result["type"], "其他")  # 落回默认
        parsed = json.loads(result["evidence"])
        self.assertEqual(parsed["type"]["value"], "创业孵化")

    def test_dict_value_not_emptied(self):
        """Day 5 关键回归：模型返回的 dict 字段（非结构化字段）被安全序列化，不是清空。"""
        data = {
            "name": "测试", "type": "其他", "deadline": "2027-01-20",
            "requirements": {"年级": "大二以上", "绩点": "3.5+"},
            "skills": "", "materials": "",
            "registration_process": "", "source_link": "", "benefits": "",
            "key_dates": [], "evidence": {}, "organization": "",
        }
        result = _validate_fields(data)
        self.assertNotEqual(result["requirements"], "")
        parsed = json.loads(result["requirements"])
        self.assertEqual(parsed["年级"], "大二以上")

    def test_all_fields_present(self):
        """即使模型只返回 name 和 type，其他字段也应有默认值。"""
        result = _validate_fields({"name": "x", "type": "实习就业", "deadline": ""})
        for field in EXTRACT_FIELDS:
            self.assertIn(field, result, f"{field} 缺失")

    def test_key_dates_with_missing_dates(self):
        data = {
            "name": "三创赛", "type": "学科竞赛", "deadline": "2027-01-20",
            "requirements": "", "skills": "", "materials": "",
            "registration_process": "", "source_link": "", "benefits": "",
            "key_dates": [
                {"event": "省赛", "start_date": "", "end_date": "", "description": "2027年5月"}
            ],
            "evidence": {},
            "organization": "",
        }
        result = _validate_fields(data)
        parsed = json.loads(result["key_dates"])
        self.assertEqual(parsed[0]["event"], "省赛")
        self.assertEqual(parsed[0]["start_date"], "")

    def test_evidence_quote_from_original(self):
        data = {
            "name": "测试", "type": "其他", "deadline": "2027-01-20",
            "requirements": "", "skills": "", "materials": "",
            "registration_process": "", "source_link": "", "benefits": "",
            "key_dates": [],
            "evidence": {
                "deadline": {"value": "2027-01-20", "quote": "参赛队报名时间为2026年11月1日至2027年1月20日"}
            },
            "organization": "",
        }
        result = _validate_fields(data)
        parsed = json.loads(result["evidence"])
        self.assertEqual(
            parsed["deadline"]["quote"],
            "参赛队报名时间为2026年11月1日至2027年1月20日",
        )


class TestExtractJson(unittest.TestCase):
    """_extract_json 基本健壮性（来自 ai_parser 原有测试，确保 Day 5 没破坏）。"""

    def test_plain_json(self):
        result = _extract_json('{"a": 1}')
        self.assertEqual(result, {"a": 1})

    def test_fenced_json(self):
        result = _extract_json('```json\n{"a": 1}\n```')
        self.assertEqual(result, {"a": 1})

    def test_wrapped_text(self):
        result = _extract_json('好的，结果如下：\n{"a": 1}\n谢谢')
        self.assertEqual(result, {"a": 1})

    def test_not_dict_raises(self):
        with self.assertRaises(ai_parser.AIParserError):
            _extract_json('[1, 2, 3]')

    def test_empty_raises(self):
        with self.assertRaises(ai_parser.AIParserError):
            _extract_json('')


class TestTryParseJsonString(unittest.TestCase):
    """_try_parse_json_string 二次解析 JSON 字符串。"""

    def test_ok(self):
        self.assertEqual(_try_parse_json_string('{"a":1}'), {"a": 1})

    def test_array_ok(self):
        self.assertEqual(_try_parse_json_string('[1,2]'), [1, 2])

    def test_with_wrapping(self):
        text = '以下是结果：{"a":1}，仅供参考'
        self.assertEqual(_try_parse_json_string(text), {"a": 1})

    def test_invalid(self):
        self.assertIsNone(_try_parse_json_string("not json"))

    def test_none_input(self):
        self.assertIsNone(_try_parse_json_string(None))


class TestSafeJsonDumps(unittest.TestCase):
    """_safe_json_dumps 序列化安全网。"""

    def test_normal(self):
        self.assertEqual(_safe_json_dumps({"a": "中文"}), '{"a":"中文"}')

    def test_fallback_to_str(self):
        class Bad:
            def __str__(self): return "bad"
        # 即便 json.dumps 失败也应返回 str
        result = _safe_json_dumps(Bad())
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


class TestInjectTypeEvidence(unittest.TestCase):
    """_inject_type_evidence 在 evidence 里记录超枚举的原始 type。"""

    def test_empty_existing(self):
        result = _inject_type_evidence("", "创业孵化")
        parsed = json.loads(result)
        self.assertEqual(parsed["type"]["value"], "创业孵化")

    def test_merge_existing(self):
        existing = '{"deadline":{"value":"2027-01-20","quote":"..."}}'
        result = _inject_type_evidence(existing, "创业孵化")
        parsed = json.loads(result)
        self.assertEqual(parsed["deadline"]["value"], "2027-01-20")
        self.assertEqual(parsed["type"]["value"], "创业孵化")


# =====================================================================
# 二、database 单元测试
# =====================================================================


class TestDatabaseMigration(unittest.TestCase):
    """Day 5 迁移：在旧表上加 5 列，不丢历史数据。"""

    def setUp(self):
        # 使用临时数据库，不碰真实库。
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = Path(self.tmp.name)
        # 备份并替换 DB_PATH
        self._orig_db_path = database.DB_PATH
        database.DB_PATH = self.db_path

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self.db_path.unlink(missing_ok=True)

    def _get_columns(self):
        conn = sqlite3.connect(self.db_path)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(opportunities)").fetchall()]
        conn.close()
        return cols

    def test_fresh_init_has_all_day5_columns(self):
        database.init_db()
        cols = self._get_columns()
        for new_col in ("registration_process", "source_link", "benefits", "key_dates", "evidence"):
            self.assertIn(new_col, cols, f"{new_col} 未创建")

    def test_migration_from_day4_schema(self):
        """模拟 Day 4 旧库（没有 Day 5 列），执行迁移后应全部补齐。"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(database._CREATE_OPPORTUNITIES_SQL)
        conn.execute(database._CREATE_META_SQL)
        # 插入一条 Day 4 数据，不带 Day 5 新列
        conn.execute(
            "INSERT INTO opportunities (name, type, organization, deadline, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("旧机会", "实习就业", "旧公司", "2027-01-01", "2026-01-01 00:00:00", "2026-01-01 00:00:00"),
        )
        # 手动删除 Day 5 新列模拟旧库
        for new_col in ("registration_process", "source_link", "benefits", "key_dates", "evidence"):
            conn.execute(f"ALTER TABLE opportunities DROP COLUMN {new_col}")
        # DAY 4 还可能没有 source_kind 等列
        conn.execute("ALTER TABLE opportunities DROP COLUMN source_kind")
        conn.execute("ALTER TABLE opportunities DROP COLUMN source_file_name")
        conn.execute("ALTER TABLE opportunities DROP COLUMN source_file_path")
        conn.commit()
        conn.close()

        cols_before = self._get_columns()
        self.assertNotIn("registration_process", cols_before)

        # 运行迁移
        database.init_db()

        cols_after = self._get_columns()
        for new_col in ("registration_process", "source_link", "benefits", "key_dates", "evidence"):
            self.assertIn(new_col, cols_after, f"{new_col} 迁移未添加")

        # 旧数据仍在，且新列默认为空
        with database.get_connection() as conn2:
            row = conn2.execute("SELECT * FROM opportunities WHERE name='旧机会'").fetchone()
            self.assertEqual(row["name"], "旧机会")
            self.assertEqual(row["registration_process"], "")
            self.assertEqual(row["key_dates"], "")

    def test_migration_idempotent(self):
        """迁移执行两次不应报错。"""
        database.init_db()
        database.init_db()  # 第二次
        cols = self._get_columns()
        self.assertIn("registration_process", cols)


class TestDatabaseDay5Fields(unittest.TestCase):
    """create_opportunity / update_opportunity / list_opportunities 包含新字段。"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = Path(self.tmp.name)
        self._orig_db_path = database.DB_PATH
        database.DB_PATH = self.db_path
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self.db_path.unlink(missing_ok=True)

    def test_create_with_day5_fields(self):
        key_dates_json = json.dumps(
            [{"event": "报名", "start_date": "2027-01-01", "end_date": "2027-01-20", "description": ""}],
            ensure_ascii=False,
        )
        evidence_json = json.dumps(
            {"deadline": {"value": "2027-01-20", "quote": "截止2027年1月20日"}},
            ensure_ascii=False,
        )
        opp_id = database.create_opportunity({
            "name": "三创赛测试",
            "type": "学科竞赛",
            "organization": "教育部",
            "deadline": "2027-01-20",
            "requirements": "3-5人团队",
            "skills": "",
            "materials": "",
            "registration_process": "注册→创建团队→审核",
            "source_link": "https://example.com",
            "benefits": "证书",
            "key_dates": key_dates_json,
            "evidence": evidence_json,
        })
        row = database.get_opportunity(opp_id)
        self.assertEqual(row["name"], "三创赛测试")
        self.assertEqual(row["registration_process"], "注册→创建团队→审核")
        self.assertEqual(row["source_link"], "https://example.com")
        self.assertEqual(row["benefits"], "证书")
        self.assertEqual(row["key_dates"], key_dates_json)
        self.assertEqual(row["evidence"], evidence_json)

        # key_dates / evidence 序列化正确
        self.assertEqual(json.loads(row["key_dates"])[0]["event"], "报名")
        self.assertEqual(json.loads(row["evidence"])["deadline"]["value"], "2027-01-20")

    def test_update_day5_fields(self):
        opp_id = database.create_opportunity({
            "name": "更新测试", "type": "其他", "organization": "x",
            "deadline": "2027-01-01",
            "registration_process": "旧流程",
            "source_link": "", "benefits": "", "key_dates": "[]", "evidence": "{}",
        })
        ok = database.update_opportunity(opp_id, {
            "name": "更新测试v2", "type": "实习就业", "organization": "y",
            "deadline": "2027-02-01",
            "registration_process": "新流程",
            "source_link": "https://new.example.com",
            "benefits": "日薪200",
            "key_dates": '[{"event":"面试","start_date":"2027-02-10","end_date":"","description":""}]',
            "evidence": '{"requirements":{"value":"","quote":""}}',
        }, allow_past_deadline=True)
        self.assertTrue(ok)
        row = database.get_opportunity(opp_id)
        self.assertEqual(row["registration_process"], "新流程")
        self.assertEqual(row["source_link"], "https://new.example.com")
        self.assertEqual(row["benefits"], "日薪200")
        self.assertEqual(json.loads(row["key_dates"])[0]["event"], "面试")

    def test_list_opportunities_returns_new_fields(self):
        database.create_opportunity({
            "name": "列表测试", "type": "其他", "organization": "x",
            "deadline": "2027-01-01",
            "registration_process": "p", "source_link": "l", "benefits": "b",
            "key_dates": "[]", "evidence": "{}",
        })
        rows = database.list_opportunities()
        row = [r for r in rows if r["name"] == "列表测试"][0]
        self.assertIn("registration_process", row)
        self.assertIn("key_dates", row)
        self.assertIn("evidence", row)

    def test_day5_fields_not_required(self):
        """Day 5 新字段都是可选的，缺失时不应报错。"""
        opp_id = database.create_opportunity({
            "name": "最小化测试", "type": "其他", "organization": "x",
            "deadline": "2027-01-01",
        })
        row = database.get_opportunity(opp_id)
        self.assertEqual(row["registration_process"], "")
        self.assertEqual(row["key_dates"], "")
        self.assertEqual(row["evidence"], "")

    def test_colums_constant_matches_schema(self):
        """COLUMNS 常量与实际表结构的业务列完全一致。"""
        with database.get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(opportunities)").fetchall()}
        actual = cols - {"id", "created_at", "updated_at"}
        expected = set(COLUMNS)
        self.assertEqual(actual, expected, f"不一致：actual={actual ^ expected}")


# =====================================================================
# 三、parser → database 集成测试
# =====================================================================


class TestParserDatabaseIntegration(unittest.TestCase):
    """mock Kimi 返回一个 Day 5 完整 JSON，走完整链路到数据库。"""

    MOCK_KIMI_RETURN = json.dumps({
        "name": "三创赛 2027",
        "type": "学科竞赛",
        "organization": "教育部高等学校电子商务类专业教学指导委员会",
        "deadline": "2027-01-20",
        "requirements": "3-5 名在校学生组成团队，设 1 名队长；"
                       "可邀请 0-2 名高校指导老师和 0-2 名企业指导老师。",
        "skills": "",
        "materials": "参赛作品申报书",
        "registration_process": "1. 队长在官网注册并创建团队；"
                                "2. 队长搜索成员发送邀请；"
                                "3. 成员接受邀请后提交团队；"
                                "4. 学校管理员审核通过；"
                                "5. 团队成员完成赛事规则答题测试。",
        "source_link": "https://www.3chuang.com",
        "benefits": "全国总决赛获奖团队获得证书和奖金",
        "key_dates": [
            {"event": "参赛队报名", "start_date": "2026-11-01", "end_date": "2027-01-20", "description": "普通参赛者报名窗口"},
            {"event": "校赛管理员审核", "start_date": "2027-01-21", "end_date": "2027-01-31", "description": ""},
            {"event": "全国总决赛", "start_date": "2027-06-01", "end_date": "2027-06-05", "description": ""},
        ],
        "evidence": {
            "deadline": {"value": "2027-01-20", "quote": "参赛队报名时间为2026年11月1日至2027年1月20日"},
            "requirements": {"value": "3-5名学生团队", "quote": "参赛团队学生成员为3-5人"},
            "registration_process": {"value": "队长创建团队并邀请成员", "quote": "队长创建团队，搜索成员并发送邀请……"},
        },
    }, ensure_ascii=False)

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = Path(self.tmp.name)
        self._orig_db_path = database.DB_PATH
        database.DB_PATH = self.db_path
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self._orig_db_path
        self.db_path.unlink(missing_ok=True)

    def _build_mock_response(self):
        """构造 mock 的 Kimi 响应对象。"""
        class MockMessage:
            def __init__(self, content):
                self.content = content

        class MockChoice:
            def __init__(self, content):
                self.message = MockMessage(content)

        class MockResponse:
            def __init__(self, content):
                self.choices = [MockChoice(content)]

        return MockResponse(self.MOCK_KIMI_RETURN)

    def test_full_pipeline(self):
        with patch("services.ai_parser._build_client") as mock_builder:
            mock_client = mock_builder.return_value
            mock_client.chat.completions.create.return_value = self._build_mock_response()

            # 设置 API Key
            with patch.dict(os.environ, {"MOONSHOT_API_KEY": "test-key"}):
                parsed = ai_parser.parse_notice("这是一段测试通知文本")

        # 1. AI 解析结果检查
        self.assertEqual(parsed["name"], "三创赛 2027")
        self.assertEqual(parsed["type"], "学科竞赛")
        self.assertEqual(parsed["deadline"], "2027-01-20")
        self.assertIn("3-5", parsed["requirements"])
        self.assertEqual(parsed["skills"], "")  # 通知没提技能
        self.assertNotIn("备案申请书", parsed["materials"])  # 承办方材料不应出现
        self.assertIn("队长", parsed["registration_process"])
        self.assertEqual(parsed["source_link"], "https://www.3chuang.com")
        self.assertIn("证书", parsed["benefits"])

        # key_dates 应正确序列化
        key_dates_parsed = json.loads(parsed["key_dates"])
        self.assertEqual(len(key_dates_parsed), 3)
        # deadline 选的是"参赛队报名"截止日，不是总决赛日
        self.assertEqual(parsed["deadline"], "2027-01-20")

        # evidence 应正确序列化
        evidence_parsed = json.loads(parsed["evidence"])
        self.assertEqual(evidence_parsed["deadline"]["value"], "2027-01-20")
        # quote 必须是原文逐字引用（来自 mock Kimi 返回）
        self.assertIn("参赛队报名时间为", evidence_parsed["deadline"]["quote"])

        # 2. 存库
        parsed["raw_text"] = "原始通知全文……"
        opp_id = database.create_opportunity(parsed)

        # 3. 读回
        row = database.get_opportunity(opp_id)
        self.assertEqual(row["name"], "三创赛 2027")
        self.assertEqual(row["registration_process"], parsed["registration_process"])
        self.assertEqual(row["key_dates"], parsed["key_dates"])
        self.assertEqual(row["evidence"], parsed["evidence"])

        # 4. 重新解析 key_dates
        saved_kd = json.loads(row["key_dates"])
        self.assertEqual(saved_kd[0]["event"], "参赛队报名")
        self.assertEqual(saved_kd[0]["start_date"], "2026-11-01")
        self.assertEqual(saved_kd[0]["end_date"], "2027-01-20")

        saved_ev = json.loads(row["evidence"])
        self.assertIn("deadline", saved_ev)


class TestParserEdgeCases(unittest.TestCase):
    """异常字段：dict 类型、复杂 list、空 evidence、类型超枚举等。"""

    def test_dict_requirements_no_longer_dropped(self):
        """模型错误地把 requirements 返回成 dict，不应被清空。"""
        data = {
            "name": "x", "type": "其他", "deadline": "2027-01-20",
            "requirements": {"资格": "大二以上", "绩点": "3.5"},
            "skills": "", "materials": "",
            "registration_process": "", "source_link": "", "benefits": "",
            "key_dates": [], "evidence": {}, "organization": "",
        }
        result = _validate_fields(data)
        self.assertNotEqual(result["requirements"], "")
        parsed = json.loads(result["requirements"])
        self.assertEqual(parsed["资格"], "大二以上")

    def test_complex_key_dates_without_event(self):
        """key_dates 某元素缺少 event 字段。"""
        data = {
            "name": "x", "type": "其他", "deadline": "2027-01-20",
            "requirements": "", "skills": "", "materials": "",
            "registration_process": "", "source_link": "", "benefits": "",
            "key_dates": [{"start_date": "2027-01-01", "end_date": "", "description": ""}],
            "evidence": {}, "organization": "",
        }
        result = _validate_fields(data)
        parsed = json.loads(result["key_dates"])
        # 元素保留，字段缺失不报错
        self.assertEqual(parsed[0]["start_date"], "2027-01-01")

    def test_evidence_empty(self):
        data = {
            "name": "x", "type": "其他", "deadline": "2027-01-20",
            "requirements": "", "skills": "", "materials": "",
            "registration_process": "", "source_link": "", "benefits": "",
            "key_dates": [], "evidence": {}, "organization": "",
        }
        result = _validate_fields(data)
        self.assertEqual(result["evidence"], "{}")

    def test_nested_list_in_text_field(self):
        """list of list 安全降级。"""
        data = {
            "name": "x", "type": "其他", "deadline": "2027-01-20",
            "materials": [["简历", "推荐信"], ["成绩单"]],
            "skills": "", "requirements": "",
            "registration_process": "", "source_link": "", "benefits": "",
            "key_dates": [], "evidence": {}, "organization": "",
        }
        result = _validate_fields(data)
        # 不应该抛异常，应该序列化成 JSON
        self.assertNotEqual(result["materials"], "")
        parsed = json.loads(result["materials"])
        self.assertEqual(parsed[0][0], "简历")


# =====================================================================
# 四、EXTRACT_FIELDS 常量一致性检查
# =====================================================================


class TestFieldConstants(unittest.TestCase):
    """EXTRACT_FIELDS 与 COLUMNS 必须同步，避免落库丢字段。"""

    def test_extract_fields_all_in_columns(self):
        extra = set(EXTRACT_FIELDS) - set(COLUMNS)
        self.assertEqual(extra, set(), f"EXTRACT_FIELDS 中有但 COLUMNS 缺失: {extra}")

    def test_all_opportunity_types_are_strings(self):
        self.assertTrue(all(isinstance(t, str) for t in OPPORTUNITY_TYPES))
        self.assertIn(DEFAULT_OPPORTUNITY_TYPE, OPPORTUNITY_TYPES)


if __name__ == "__main__":
    # 直接 python test_day5.py 运行时用 unittest.main
    unittest.main(verbosity=2)
