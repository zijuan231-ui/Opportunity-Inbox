"""机会数据的 SQLite 存储层。页面不直接拼 SQL，只调用本模块的函数。"""

import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from sample_data import OPPORTUNITIES

DB_PATH = Path(__file__).resolve().parent / "data" / "opportunities.db"

# 供页面捕获的数据库异常类型，避免页面直接依赖 sqlite3。
DatabaseError = sqlite3.Error

DEFAULT_STATUS = "待评估"

COLUMNS = (
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
)

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

_INSERT_SQL = """
INSERT INTO opportunities (
    name, type, organization, deadline, requirements, skills, materials,
    match_reason, gap_analysis, status, raw_text, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPDATE_SQL = """
UPDATE opportunities SET
    name = ?, type = ?, organization = ?, deadline = ?, requirements = ?,
    skills = ?, materials = ?, match_reason = ?, gap_analysis = ?,
    status = ?, raw_text = ?, updated_at = ?
WHERE id = ?
"""

_SELECT_SQL = """
SELECT id, name, type, organization, deadline, requirements, skills,
       materials, match_reason, gap_analysis, status, raw_text,
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
    """删除一条机会，返回是否命中了记录。"""
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM opportunities WHERE id = ?", (opportunity_id,)
        )
        return cursor.rowcount > 0


def _now():
    """当前时间，统一为 YYYY-MM-DD HH:MM:SS。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalize(data):
    """把页面传来的字段整理成统一结构，缺失字段按空字符串处理。"""
    payload = {}
    for column in COLUMNS:
        payload[column] = str(data.get(column, "") or "").strip()
    payload["status"] = payload["status"] or DEFAULT_STATUS
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
        timestamp,
        timestamp,
    )


def _insert_seed_rows(connection):
    """把 sample_data 中的演示机会写入空库。"""
    for item in OPPORTUNITIES:
        payload = _normalize({SEED_KEY_MAP.get(key, key): value for key, value in item.items()})
        created_at = f"{item['created_at']} 00:00:00"
        connection.execute(_INSERT_SQL, _insert_values(payload, created_at))
