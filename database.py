
from datetime import datetime
import os

from sqlalchemy import (
    create_engine,
    event,
    text,
    select,
    JSON,
    DateTime,
    String,
    UnicodeText,
)
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
)


# 1. 数据库连接配置
# Windows keeps integrated authentication by default; Linux defaults to SQL auth.
_username = os.getenv("SQLSERVER_USERNAME") or None
_password = os.getenv("SQLSERVER_PASSWORD") or None
_auth = os.getenv("SQLSERVER_AUTH", "auto").strip().lower()
if _auth not in {"auto", "windows", "sql"}:
    raise ValueError("SQLSERVER_AUTH must be auto, windows, or sql")
if _auth == "auto":
    _auth = "sql" if os.name != "nt" or _username or _password else "windows"
if _auth == "windows" and os.name != "nt":
    raise ValueError("Windows integrated authentication is only supported on Windows; use SQLSERVER_AUTH=sql on Linux")
if _auth == "windows" and (_username or _password):
    raise ValueError("SQLSERVER_AUTH=windows cannot be combined with SQL credentials")

_host = os.getenv("SQLSERVER_HOST") or ("暗精夜灵" if os.name == "nt" else "not-configured")
_query = {
    "driver": os.getenv("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server"),
    "Encrypt": "yes",
    "TrustServerCertificate": os.getenv(
        "SQLSERVER_TRUST_SERVER_CERTIFICATE", "yes" if os.name == "nt" else "no"
    ),
}
# Explicit SQL authentication prevents implicit Windows authentication on Linux.
if _auth == "sql":
    _query["authentication"] = "SqlPassword"

DATABASE_URL = URL.create(
    "mssql+pyodbc",
    username=_username if _auth == "sql" else None,
    password=_password if _auth == "sql" else None,
    host=_host,
    port=int(os.environ["SQLSERVER_PORT"]) if os.getenv("SQLSERVER_PORT") else None,
    database=os.getenv("SQLSERVER_DATABASE", "lingjing_stage3"),
    query=_query,
)

# 2. 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# Validate SQL configuration when a database connection is requested, so /health,
# uploads and standalone inference remain available without database credentials.
@event.listens_for(engine, "do_connect")
def _check_database_configuration(dialect, connection_record, args, kwargs):
    if _auth == "sql" and (not _username or not _password or _host == "not-configured"):
        raise SQLAlchemyError(
            "SQL Server authentication requires SQLSERVER_HOST, "
            "SQLSERVER_USERNAME and SQLSERVER_PASSWORD in the process environment"
        )


# 3. 创建数据库会话工厂
SessionLocal = sessionmaker(bind=engine)


# 4. 定义 ORM 基类
class Base(DeclarativeBase):
    pass


# 5. 定义分析记录表
class AnalysisRecord(Base):
    __tablename__ = "analysis_records"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    yolo_result: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
    )

    qwen_answer: Mapped[str] = mapped_column(
        UnicodeText,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False,
    )


# 6. 测试数据库连接
def test_connection():
    with engine.connect() as connection:
        result = connection.execute(
            text(
                "SELECT @@SERVERNAME AS server_name, "
                "DB_NAME() AS database_name"
            )
        )

        print("数据库连接成功：", result.mappings().one())


# 7. 创建数据表
def init_db():
    Base.metadata.create_all(bind=engine)
    print("数据表检查及创建完成：analysis_records")


# 8. 插入并查询测试记录
def test_save_and_query():
    with SessionLocal() as session:
        record = session.scalar(
            select(AnalysisRecord).where(
                AnalysisRecord.filename == "database_test.jpg"
            )
        )

        if record is None:
            record = AnalysisRecord(
                filename="database_test.jpg",
                yolo_result=[
                    {
                        "class_name": "paper",
                        "confidence": 0.9664,
                        "bbox": [
                            34.89,
                            17.97,
                            189.86,
                            113.73,
                        ],
                    }
                ],
                qwen_answer="测试记录：干净纸张，属于可回收物。",
            )

            session.add(record)
            session.commit()
            session.refresh(record)

            print("测试记录保存成功，编号：", record.id)

        else:
            print("测试记录已存在，编号：", record.id)

        records = session.scalars(
            select(AnalysisRecord).order_by(
                AnalysisRecord.id.desc()
            )
        ).all()

        print("\n数据库中的分析记录：")

        for item in records:
            print(
                "编号：", item.id,
                "| 图片：", item.filename,
                "| YOLO：", item.yolo_result,
                "| Qwen：", item.qwen_answer,
                "| 时间：", item.created_at,
            )


# 9. 程序入口
if __name__ == "__main__":
    test_connection()
    init_db()
    test_save_and_query()
