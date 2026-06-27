"""
外贸获客系统 - 默认数据初始化
"""
import logging
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.lead import LeadSource

logger = logging.getLogger(__name__)

DEFAULT_SOURCES = [
    {"name": "Google 搜索", "type": "search_engine", "description": "通过 Google 搜索引擎按关键词采集潜在客户信息"},
    {"name": "LinkedIn", "type": "social_media", "description": "通过 LinkedIn 搜索企业和高管信息"},
    {"name": "阿里巴巴国际站", "type": "b2b_platform", "description": "从 Alibaba.com 采集采购商和供应商信息"},
    {"name": "环球资源", "type": "b2b_platform", "description": "从 Global Sources 采集全球买家信息"},
    {"name": "中国制造网", "type": "b2b_platform", "description": "从 Made-in-China.com 采集采购商数据"},
    {"name": "Google Maps", "type": "map", "description": "通过 Google Maps 按区域搜索企业信息"},
    {"name": "Facebook", "type": "social_media", "description": "通过 Facebook 搜索企业和品牌主页"},
    {"name": "海关数据", "type": "customs_data", "description": "通过各国海关进出口数据获取目标客户"},
    {"name": "展会名录", "type": "exhibition", "description": "从行业展会参展商名录中获取客户信息"},
    {"name": "手动录入", "type": "manual", "description": "手动录入的客户线索"},
    {"name": "其他渠道", "type": "other", "description": "其他未分类的客户来源渠道"},
]


def seed_default_sources():
    """初始化默认线索来源，如果不存在则创建"""
    try:
        db: Session = SessionLocal()
        now = datetime.now(UTC)
        existing = db.query(LeadSource).count()
        if existing > 0:
            logger.info(f"线索来源已存在 {existing} 条，跳过初始化")
            db.close()
            return existing

        count = 0
        for src in DEFAULT_SOURCES:
            try:
                db.add(LeadSource(
                    name=src["name"],
                    type=src["type"],
                    description=src["description"],
                    is_active=True,
                    created_at=now,
                    updated_at=now
                ))
                count += 1
            except Exception as e:
                logger.warning(f"跳过重复来源 '{src['name']}': {e}")
                db.rollback()

        db.commit()
        logger.info(f"已初始化 {count} 条默认线索来源")
        db.close()
        return count
    except Exception as e:
        logger.error(f"初始化线索来源失败: {e}")
        try:
            db.close()
        except:
            pass
        return 0  # 不抛出异常，允许应用继续启动