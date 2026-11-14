"""机会数据的 SQLite 存储层。页面不直接拼 SQL，只调用本模块的函数。"""

import logging
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from sample_data import OPPORTUNITIES

DB_PATH = Path(__file__).resolve().parent / "data" / "opportunities.db"
UPLOADS_DIR = DB_PATH.parent / "uploads"

# 供页面捕获的数据库异常类型，避免页面直接依赖 sqlite3。
DatabaseError = sqlite3.Error

DEFAULT_STATUS = "待评估"

# 机会类型：面向大学生综合成长机会，与知识库分类是两套独立枚举。
OPPORTUNITY_TYPES = (
    "实习就业",
    "科研学术",
    "学科竞赛",
    "奖学金与资助",
    "志愿与社会实践",
    "校园组织与活动",
    "学习与成长",
    "其他",
)

DEFAULT_OPPORTUNITY_TYPE = "其他"

# 旧的类型取值到新枚举的映射，用于兼容存量数据。
LEGACY_TYPE_MAP = {
    "实习": "实习就业",
    "就业": "实习就业",
    "竞赛": "学科竞赛",
    "科研项目": "科研学术",
    "科研": "科研学术",
    "奖学金": "奖学金与资助",
    "资助": "奖学金与资助",
    "志愿": "志愿与社会实践",
    "社会实践": "志愿与社会实践",
    "社团": "校园组织与活动",
    "校园组织": "校园组织与活动",
    "学习": "学习与成长",
}

# Day 5 新增的文本字段（纯文本，不涉及结构）。
_TEXT_COLUMNS = (
    "registration_process",
    "source_link",
    "benefits",
)

# Day 5 新增的 JSON 字段（以 TEXT 列存储 JSON 字符串）。
_JSON_COLUMNS = (
    "key_dates",
    "evidence",
)

_COLUMNS_BASE = (
    "name",
    "type",
    "organization",
    "deadline",
    "requirements",
    "skills",
    "materials",
    "match_reason",
    "gap_analysis",
    "status",
    "raw_text",
    "source_kind",
    "source_file_name",
    "source_file_path",
)

COLUMNS = _COLUMNS_BASE + _TEXT_COLUMNS + _JSON_COLUMNS

REQUIRED_FIELDS = {"name": "机会名称", "deadline": "截止日期"}

# sample_data 中的字段名与数据库列名不一致时在这里转换。
SEED_KEY_MAP = {
    "title": "name",
    "category": "type",
    "skills_required": "skills",
    "raw_content": "raw_text",
}

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_CREATE_OPPORTUNITIES_SQL = """
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT '',
    organization TEXT NOT NULL DEFAULT '',
    deadline TEXT NOT NULL,
    requirements TEXT NOT NULL DEFAULT '',
    skills TEXT NOT NULL DEFAULT '',
    materials TEXT NOT NULL DEFAULT '',
    match_reason TEXT NOT NULL DEFAULT '',
    gap_analysis TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '待评估',
    raw_text TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL DEFAULT 'paste',
    source_file_name TEXT NOT NULL DEFAULT '',
    source_file_path TEXT NOT NULL DEFAULT '',
    registration_process TEXT NOT NULL DEFAULT '',
    source_link TEXT NOT NULL DEFAULT '',
    benefits TEXT NOT NULL DEFAULT '',
    key_dates TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_CREATE_META_SQL = """
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

# ---------------- 知识库 ----------------

KNOWLEDGE_CATEGORIES = (
    "岗位与职业发展",
    "科研与学术",
    "竞赛与创新",
    "奖学金与升学",
    "志愿与社会实践",
    "校园组织与活动",
    "学习资源",
    "通用规则与指南",
    "其他",
)
KNOWLEDGE_SOURCE_TYPES = ("official", "general", "third_party", "unknown")
KNOWLEDGE_INPUT_METHODS = ("upload", "paste")

# 旧的资料分类到新分类的映射，用于兼容存量数据。
LEGACY_CATEGORY_MAP = {
    "通用岗位知识": "岗位与职业发展",
    "企业官方资料": "岗位与职业发展",
    "招聘规则": "通用规则与指南",
}

KNOWLEDGE_COLUMNS = (
    "title", "category", "organization", "target", "input_method",
    "source_type", "source_url", "file_name", "file_path", "file_ext",
    "tags", "content",
)

KNOWLEDGE_REQUIRED_FIELDS = {"title": "资料名称", "content": "资料内容"}

_CREATE_KNOWLEDGE_DOCUMENTS_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '其他',
    organization TEXT NOT NULL DEFAULT '',
    target TEXT NOT NULL DEFAULT '',
    input_method TEXT NOT NULL DEFAULT 'paste',
    source_type TEXT NOT NULL DEFAULT 'unknown',
    source_url TEXT NOT NULL DEFAULT '',
    file_name TEXT NOT NULL DEFAULT '',
    file_path TEXT NOT NULL DEFAULT '',
    file_ext TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_KNOWLEDGE_INSERT_SQL = """
INSERT INTO knowledge_documents (
    title, category, organization, target, input_method, source_type, source_url,
    file_name, file_path, file_ext, tags, content, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_KNOWLEDGE_UPDATE_SQL = """
UPDATE knowledge_documents SET
    title = ?, category = ?, organization = ?, target = ?,
    source_type = ?, source_url = ?, tags = ?, content = ?, updated_at = ?
WHERE id = ?
"""

_KNOWLEDGE_SELECT_SQL = """
SELECT id, title, category, organization, target, input_method, source_type,
       source_url, file_name, file_path, file_ext, tags, content,
       created_at, updated_at
FROM knowledge_documents
"""


_INSERT_SQL = """
INSERT INTO opportunities (
    name, type, organization, deadline, requirements, skills, materials,
    match_reason, gap_analysis, status, raw_text, source_kind,
    source_file_name, source_file_path,
    registration_process, source_link, benefits, key_dates, evidence,
    created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPDATE_SQL = """
UPDATE opportunities SET
    name = ?, type = ?, organization = ?, deadline = ?, requirements = ?,
    skills = ?, materials = ?, match_reason = ?, gap_analysis = ?,
    status = ?, raw_text = ?, source_kind = ?, source_file_name = ?,
    source_file_path = ?,
    registration_process = ?, source_link = ?, benefits = ?, key_dates = ?,
    evidence = ?, updated_at = ?
WHERE id = ?
"""

_SELECT_SQL = """
SELECT id, name, type, organization, deadline, requirements, skills,
       materials, match_reason, gap_analysis, status, raw_text,
       source_kind, source_file_name, source_file_path,
       registration_process, source_link, benefits, key_dates, evidence,
       created_at, updated_at
FROM opportunities
"""


class DataValidationError(ValueError):
    """机会字段校验未通过，消息可直接展示给用户。"""


class DeadlineConfirmationRequired(DataValidationError):
    """截止日期已经过期，需要用户确认后才可以保存。"""


@contextmanager
def get_connection():
    """打开连接并在退出时提交或回滚，确保写入要么全部成功要么全部撤销。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    """创建数据表。可重复调用；仅当数据库从未初始化过且为空时导入演示数据。"""
    with get_connection() as connection:
        connection.execute(_CREATE_OPPORTUNITIES_SQL)
        connection.execute(_CREATE_META_SQL)
        connection.execute(_CREATE_KNOWLEDGE_DOCUMENTS_SQL)
        _migrate_legacy_data(connection)

        seeded = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'seeded'"
        ).fetchone()
        if seeded is not None:
            return

        existing = connection.execute(
            "SELECT COUNT(*) AS total FROM opportunities"
        ).fetchone()["total"]
        if existing == 0:
            _insert_seed_rows(connection)

        # 标记已初始化。之后即使记录被删光，也不会再次导入演示数据。
        connection.execute(
            "INSERT INTO app_meta (key, value) VALUES ('seeded', '1')"
        )


def list_opportunities():
    """按添加时间从新到旧返回全部机会。"""
    with get_connection() as connection:
        rows = connection.execute(
            f"{_SELECT_SQL} ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_opportunity(opportunity_id):
    """按 id 返回单条机会，不存在时返回 None。"""
    with get_connection() as connection:
        row = connection.execute(
            f"{_SELECT_SQL} WHERE id = ?", (opportunity_id,)
        ).fetchone()
    return dict(row) if row else None


def create_opportunity(data, allow_past_deadline=False):
    """新增一条机会并返回新记录的 id。

    字段不合法时抛出 DataValidationError；截止日期已过期且未确认时
    抛出 DeadlineConfirmationRequired。
    """
    payload = _normalize(data)
    _validate(payload, created_date=date.today(), allow_past_deadline=allow_past_deadline)
    now = _now()

    with get_connection() as connection:
        cursor = connection.execute(
            _INSERT_SQL,
            _insert_values(payload, now),
        )
        return cursor.lastrowid


def update_opportunity(opportunity_id, data, allow_past_deadline=False):
    """整体更新一条机会，返回是否命中了记录。

    截止日期不能早于该机会的创建日期；字段不合法时抛出 DataValidationError，
    过期但未确认时抛出 DeadlineConfirmationRequired。
    """
    payload = _normalize(data)
    now = _now()

    with get_connection() as connection:
        row = connection.execute(
            "SELECT created_at FROM opportunities WHERE id = ?", (opportunity_id,)
        ).fetchone()
        if row is None:
            return False

        _validate(
            payload,
            created_date=_stored_date(row["created_at"]),
            allow_past_deadline=allow_past_deadline,
        )
        cursor = connection.execute(
            _UPDATE_SQL,
            (
                payload["name"],
                payload["type"],
                payload["organization"],
                payload["deadline"],
                payload["requirements"],
                payload["skills"],
                payload["materials"],
                payload["match_reason"],
                payload["gap_analysis"],
                payload["status"],
                payload["raw_text"],
                payload["source_kind"],
                payload["source_file_name"],
                payload["source_file_path"],
                payload["registration_process"],
                payload["source_link"],
                payload["benefits"],
                payload["key_dates"],
                payload["evidence"],
                now,
                opportunity_id,
            ),
        )
        return cursor.rowcount > 0


def update_status(opportunity_id, status):
    """只更新申请状态，返回是否命中了记录。"""
    status = (status or "").strip() or DEFAULT_STATUS
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE opportunities SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), opportunity_id),
        )
        return cursor.rowcount > 0


def delete_opportunity(opportunity_id):
    """删除一条机会，并清理关联的原始文件。

    先删数据库记录，成功后再删物理文件；文件清理失败只记日志，
    不会让删除操作失败。返回是否删除了记录。
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT source_file_path FROM opportunities WHERE id = ?",
            (opportunity_id,),
        ).fetchone()
        cursor = connection.execute(
            "DELETE FROM opportunities WHERE id = ?", (opportunity_id,)
        )
        deleted = cursor.rowcount > 0
    if deleted and row is not None:
        remove_upload_file(row["source_file_path"])
    return deleted


# ---------------- 知识库 CRUD ----------------

def list_documents():
    """按上传时间倒序返回全部知识资料。"""
    with get_connection() as connection:
        rows = connection.execute(
            f"{_KNOWLEDGE_SELECT_SQL} ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_document(document_id):
    """按 id 返回单条资料，不存在时返回 None。"""
    with get_connection() as connection:
        row = connection.execute(
            f"{_KNOWLEDGE_SELECT_SQL} WHERE id = ?", (document_id,)
        ).fetchone()
    return dict(row) if row else None


def create_document(data):
    """新增一条知识资料并返回新记录的 id。"""
    payload = _normalize_knowledge(data)
    _validate_knowledge(payload)
    now = _now()
    with get_connection() as connection:
        cursor = connection.execute(
            _KNOWLEDGE_INSERT_SQL,
            (
                payload["title"], payload["category"], payload["organization"],
                payload["target"], payload["input_method"],
                payload["source_type"], payload["source_url"],
                payload["file_name"], payload["file_path"],
                payload["file_ext"], payload["tags"], payload["content"], now, now,
            ),
        )
        return cursor.lastrowid


def update_document(document_id, data):
    """更新资料的元数据和文本内容，不改文件路径。返回是否命中记录。"""
    payload = _normalize_knowledge(data)
    _validate_knowledge(payload)
    now = _now()
    with get_connection() as connection:
        cursor = connection.execute(
            _KNOWLEDGE_UPDATE_SQL,
            (
                payload["title"], payload["category"], payload["organization"],
                payload["target"], payload["source_type"],
                payload["source_url"], payload["tags"], payload["content"],
                now, document_id,
            ),
        )
        return cursor.rowcount > 0


def delete_document(document_id):
    """删除一条知识资料，返回是否命中记录。上传文件的清理由调用方负责。"""
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM knowledge_documents WHERE id = ?", (document_id,)
        )
        return cursor.rowcount > 0


def resolve_upload_path(file_path):
    """把数据库里的相对路径解析为安全的绝对路径。

    若解析结果超出 data/uploads/ 目录则抛出 DataValidationError，
    防止路径穿越。
    """
    uploads = UPLOADS_DIR.resolve()
    target = (uploads / file_path).resolve()
    try:
        target.relative_to(uploads)
    except ValueError:
        raise DataValidationError("文件路径不合法，已拒绝操作。")
    return target


MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 单个上传文件上限 20MB

logger = logging.getLogger(__name__)


def save_upload_file(raw_bytes, original_name, file_ext):
    """把上传文件写入 data/uploads/，返回相对路径（文件名随机化）。"""
    safe_stem = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", Path(original_name).stem)[:50]
    safe_stem = safe_stem.strip("._") or "document"
    relative = f"{uuid.uuid4().hex[:8]}_{safe_stem}.{file_ext}"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOADS_DIR / relative).write_bytes(raw_bytes)
    return relative


def remove_upload_file(file_path):
    """删除 data/uploads/ 下的上传文件，返回是否删除成功。

    路径不合法（目录穿越）或文件不存在时直接返回 False，绝不触碰
    uploads 目录以外的任何文件；删除失败只记录日志，不抛异常。
    """
    if not file_path:
        return False
    try:
        target = resolve_upload_path(file_path)
    except DataValidationError:
        logger.warning("拒绝删除不合法的路径：%r", file_path)
        return False
    try:
        if target.is_file():
            target.unlink()
            return True
    except OSError as error:
        logger.warning("删除上传文件失败 %s：%s", target, error)
    return False


def _normalize_knowledge(data):
    payload = {}
    for column in KNOWLEDGE_COLUMNS:
        payload[column] = str(data.get(column, "") or "").strip()
    payload["category"] = payload["category"] or "其他"
    payload["input_method"] = payload["input_method"] or "paste"
    payload["source_type"] = payload["source_type"] or "unknown"
    return payload


# Day 5 新增列的迁移：必须在 _migrate_legacy_data 内，保证幂等。
_DAY5_NEW_COLUMNS = (
    ("registration_process", "TEXT NOT NULL DEFAULT ''"),
    ("source_link", "TEXT NOT NULL DEFAULT ''"),
    ("benefits", "TEXT NOT NULL DEFAULT ''"),
    ("key_dates", "TEXT NOT NULL DEFAULT ''"),
    ("evidence", "TEXT NOT NULL DEFAULT ''"),
)


def _migrate_legacy_data(connection):
    """兼容 Day 1—Day 5 的存量数据：通用化字段名、映射旧枚举值、补全缺失列。

    可重复执行：字段已重命名或值已是新枚举时不会再次改动。
    """
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(knowledge_documents)")
    }
    # company / position 带有招聘场景语义，重命名为 organization / target。
    if "company" in columns:
        connection.execute(
            "ALTER TABLE knowledge_documents RENAME COLUMN company TO organization"
        )
    if "position" in columns:
        connection.execute(
            "ALTER TABLE knowledge_documents RENAME COLUMN position TO target"
        )
    if "tags" not in columns:
        connection.execute(
            "ALTER TABLE knowledge_documents ADD COLUMN tags TEXT NOT NULL DEFAULT ''"
        )

    # 旧的机会类型映射到新的类型枚举。
    for legacy, current in LEGACY_TYPE_MAP.items():
        connection.execute(
            "UPDATE opportunities SET type = ? WHERE type = ?", (current, legacy)
        )
    # 旧的资料分类映射到新的分类枚举。
    for legacy, current in LEGACY_CATEGORY_MAP.items():
        connection.execute(
            "UPDATE knowledge_documents SET category = ? WHERE category = ?",
            (current, legacy),
        )

    # 机会记录关联原始文件：新增列，旧记录默认视为粘贴录入。
    opportunity_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(opportunities)")
    }
    for column, ddl in (
        ("source_kind", "TEXT NOT NULL DEFAULT 'paste'"),
        ("source_file_name", "TEXT NOT NULL DEFAULT ''"),
        ("source_file_path", "TEXT NOT NULL DEFAULT ''"),
    ):
        if column not in opportunity_columns:
            connection.execute(
                f"ALTER TABLE opportunities ADD COLUMN {column} {ddl}"
            )

    # Day 5 新增的 5 列（文本字段 + JSON 存储字段）。
    for column, ddl in _DAY5_NEW_COLUMNS:
        if column not in opportunity_columns:
            connection.execute(
                f"ALTER TABLE opportunities ADD COLUMN {column} {ddl}"
            )


def _validate_knowledge(payload):
    errors = []
    for field, label in KNOWLEDGE_REQUIRED_FIELDS.items():
        if not payload[field]:
            errors.append(f"请填写{label}")
    if payload["category"] not in KNOWLEDGE_CATEGORIES:
        errors.append("资料分类不合法")
    if payload["input_method"] not in KNOWLEDGE_INPUT_METHODS:
        errors.append("录入方式不合法")
    if payload["source_type"] not in KNOWLEDGE_SOURCE_TYPES:
        errors.append("来源类型不合法")
    if errors:
        raise DataValidationError("；".join(errors))


def _now():
    """当前时间，统一为 YYYY-MM-DD HH:MM:SS。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalize(data):
    """把页面传来的字段整理成统一结构，缺失字段按空字符串处理。"""
    payload = {}
    for column in COLUMNS:
        payload[column] = str(data.get(column, "") or "").strip()
    payload["status"] = payload["status"] or DEFAULT_STATUS
    payload["source_kind"] = payload["source_kind"] or "paste"
    return payload


def _validate(payload, created_date, allow_past_deadline=False):
    """校验必填字段、日期格式和日期业务规则，错误信息可直接展示。"""
    errors = []
    for field, label in REQUIRED_FIELDS.items():
        if not payload[field]:
            errors.append(f"请填写{label}")

    deadline_text = payload["deadline"]
    deadline = None
    if deadline_text:
        if _is_valid_date(deadline_text):
            deadline = date.fromisoformat(deadline_text)
        else:
            errors.append("截止日期需使用 YYYY-MM-DD 格式，例如 2026-12-31")

    if errors:
        raise DataValidationError("；".join(errors))

    if deadline is None:
        return

    today = date.today()
    # 历史机会：截止日期不能早于机会自身的创建日期。
    # 当天新建的机会视为今天创建，过期情况交给下面的确认流程处理。
    if created_date is not None and created_date < today and deadline < created_date:
        raise DataValidationError(
            f"截止日期不能早于机会创建日期（{created_date.isoformat()}），请修改后重新保存。"
        )

    # 日期本身合法但已经过期：不禁止保存，要求用户确认。
    if deadline < today and not allow_past_deadline:
        raise DeadlineConfirmationRequired(
            f"截止日期 {deadline.isoformat()} 已经过去，确认仍要保存这条机会吗？"
        )


def _stored_date(created_at):
    """从 created_at（YYYY-MM-DD HH:MM:SS）中取出日期部分。"""
    text = (created_at or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return date.today()


def _is_valid_date(value):
    """严格按 YYYY-MM-DD 校验，避免接受 2026-1-1 之类的写法。"""
    if not _DATE_PATTERN.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _insert_values(payload, timestamp):
    """按 _INSERT_SQL 的占位符顺序拼出参数元组。"""
    return (
        payload["name"],
        payload["type"],
        payload["organization"],
        payload["deadline"],
        payload["requirements"],
        payload["skills"],
        payload["materials"],
        payload["match_reason"],
        payload["gap_analysis"],
        payload["status"],
        payload["raw_text"],
        payload["source_kind"],
        payload["source_file_name"],
        payload["source_file_path"],
        payload["registration_process"],
        payload["source_link"],
        payload["benefits"],
        payload["key_dates"],
        payload["evidence"],
        timestamp,
        timestamp,
    )


def _insert_seed_rows(connection):
    """把 sample_data 中的演示机会写入空库。"""
    for item in OPPORTUNITIES:
        payload = _normalize({SEED_KEY_MAP.get(key, key): value for key, value in item.items()})
        created_at = f"{item['created_at']} 00:00:00"
        connection.execute(_INSERT_SQL, _insert_values(payload, created_at))
