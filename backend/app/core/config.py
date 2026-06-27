"""
外贸获客系统 - 配置管理模块
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用设置
    APP_NAME: str = "外贸获客系统"
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # 数据库配置 - 默认使用 SQLite 便于开发
    DATABASE_TYPE: str = "sqlite"  # sqlite, postgresql
    DATABASE_URL: str = "sqlite:///./lead_capture.db"
    # PostgreSQL 备用配置
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "lead_capture"
    
    MONGODB_URL: str = "mongodb://localhost:27017"
    REDIS_URL: str = "redis://localhost:6379/0"
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    
    # Celery 配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # Playwright 配置
    PLAYWRIGHT_BROWSER: str = "chromium"
    
    # API 配置
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # 限流配置
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # 邮箱验证 API
    EMAIL_VALIDATION_API_KEY: Optional[str] = None
    
    # 外部 API 密钥
    GOOGLE_API_KEY: Optional[str] = None
    BING_API_KEY: Optional[str] = None
    LINKEDIN_API_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
