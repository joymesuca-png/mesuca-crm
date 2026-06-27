"""
外贸获客系统 - 数据库连接管理
支持 SQLite（开发）和 PostgreSQL（生产）
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# 根据配置选择数据库类型
if settings.DATABASE_TYPE == "postgresql":
    # 优先使用完整的 DATABASE_URL，否则用独立变量拼接
    DATABASE_URL = settings.DATABASE_URL
    if "sqlite" in DATABASE_URL:
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


# ============ 可选服务（延迟连接，不阻塞启动） ============

_mongo_client = None
_mongo_db = None
_redis_client = None
_es_client = None


def get_mongo_db():
    """获取 MongoDB 数据库连接（延迟初始化）"""
    global _mongo_client, _mongo_db
    if _mongo_db is None:
        try:
            from pymongo import MongoClient
            _mongo_client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=2000)
            _mongo_db = _mongo_client['lead_capture']
            _mongo_client.admin.command('ping')
            logger.info("MongoDB 连接成功")
        except Exception as e:
            logger.warning(f"MongoDB 连接失败: {e}")
            _mongo_client = None
            _mongo_db = None
    return _mongo_db


def get_redis():
    """获取 Redis 连接（延迟初始化）"""
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2
            )
            _redis_client.ping()
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.warning(f"Redis 连接失败: {e}")
            _redis_client = None
    return _redis_client


def get_es_client():
    """获取 Elasticsearch 客户端（延迟初始化）"""
    global _es_client
    if _es_client is None:
        try:
            from elasticsearch import Elasticsearch
            _es_client = Elasticsearch(
                [settings.ELASTICSEARCH_URL],
                request_timeout=5
            )
            if _es_client.ping():
                logger.info("Elasticsearch 连接成功")
            else:
                logger.warning("Elasticsearch ping 失败")
                _es_client = None
        except Exception as e:
            logger.warning(f"Elasticsearch 连接失败: {e}")
            _es_client = None
    return _es_client


def init_db():
    """初始化数据库表（仅用于 SQLite/开发环境）"""
    from app.models import lead  # 导入所有模型以注册到 Base
    
    Base.metadata.create_all(bind=engine)
    logger.info(f"数据库初始化完成 (类型：{settings.DATABASE_TYPE})")