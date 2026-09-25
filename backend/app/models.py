import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)


class Bank(Base):
    __tablename__ = 'banks'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    data: Mapped[dict] = mapped_column(JSON)


class Report(Base):
    __tablename__ = 'reports'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    revision: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[str] = mapped_column(String(50), default=now)
    final_key: Mapped[str | None] = mapped_column(String(36), nullable=True)
    __mapper_args__ = {'version_id_col': revision, 'version_id_generator': False}


class Asset(Base):
    __tablename__ = 'assets'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    report_id: Mapped[str] = mapped_column(ForeignKey('reports.id'), index=True)
    caption: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(100))


class Event(Base):
    __tablename__ = 'events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    report_id: Mapped[str] = mapped_column(ForeignKey('reports.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(100))
    revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(50), default=now)

class DriveConnection(Base):
    __tablename__ = 'drive_connections'

    owner_id: Mapped[str] = mapped_column(
        ForeignKey('users.id'),
        primary_key=True
    )

    encrypted_refresh_token: Mapped[str] = mapped_column(Text)

    root_folder_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )


database_url = settings.database_url

if database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )

engine = create_engine(
    database_url,
    connect_args={
        "check_same_thread": False
    } if database_url.startswith("sqlite") else {},
    pool_pre_ping=True,
)

Session = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with Session() as db:
        yield db
