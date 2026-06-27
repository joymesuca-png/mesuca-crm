"""
外贸获客系统 - 数据库连接管理
支持 SQLite（开发）和 PostgreSQL（生产）
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from pymongo import MongoClient
from elasticsearch import Elasticsearch
import redis
from app.core.config import get_settings

settings = get_settings()

# 根据配置选择数据库类型
if settings.DATABASE_TYPE == "postgresql":
    DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
else:
    DATABASE_URL = settings.DATABASE_URL  # SQLite

# PostgreSQL/SQLite 配置
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# MongoDB 配置
try:
    mongo_client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    mongo_db = mongo_client['lead_capture']
except Exception as e:
    print(f"⚠️  MongoDB 连接失败：{e}")
    mongo_client = None
    mongo_db = None


def get_mongo_db():
    """获取 MongoDB 数据库连接"""
    return mongo_db


# Redis 配置
try:
    redis_client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5
    )
except Exception as e:
    print(f"⚠️  Redis 连接失败：{e}")
    redis_client = None


def get_redis():
    """获取 Redis 连接"""
    return redis_client


# Elasticsearch 配置
try:
    es_client = Elasticsearch(
        [settings.ELASTICSEARCH_URL],
        request_timeout=30
    )
except Exception as e:
    print(f"⚠️  Elasticsearch 连接失败：{e}")
    es_client = None


def get_es_client():
    """获取 Elasticsearch 客户端"""
    return es_client


def init_db():
    """初始化数据库表（仅用于 SQLite/开发环境）"""
    from app.models import lead  # 导入所有模型以注册到 Base
    
    Base.metadata.create_all(bind=engine)
    print(f"✅ 数据库初始化完成 (类型：{settings.DATABASE_TYPE})")
