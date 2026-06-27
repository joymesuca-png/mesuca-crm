"""
外贸获客系统 - 客户线索数据模型
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from app.core.database import Base


class LeadSource(Base):
    """线索来源表"""
    __tablename__ = "lead_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)  # 来源名称：Google, LinkedIn, B2B 平台等
    type = Column(String(50), nullable=False)  # 来源类型：search_engine, social_media, b2b_platform
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)
    
    leads = relationship("Lead", back_populates="source")


class Lead(Base):
    """客户线索主表"""
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 基本信息
    company_name = Column(String(200), index=True)  # 公司名称
    contact_name = Column(String(100))  # 联系人姓名
    email = Column(String(200), index=True)  # 邮箱
    phone = Column(String(50))  # 电话
    website = Column(String(200))  # 网站
    
    # 地址信息
    country = Column(String(100), index=True)  # 国家
    state = Column(String(100))  # 州/省
    city = Column(String(100))  # 城市
    address = Column(String(500))  # 详细地址
    
    # 业务信息
    industry = Column(String(100))  # 行业
    product_interest = Column(String(500))  # 感兴趣的产品
    lead_score = Column(Float, default=0.0)  # 线索评分
    
    # 来源信息
    source_id = Column(Integer, ForeignKey('lead_sources.id'))
    source_url = Column(String(500))  # 来源 URL
    original_data = Column(Text)  # 原始数据 (JSON 格式)
    
    # 状态管理
    status = Column(String(50), default='new')  # new, contacted, qualified, converted, lost
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # 负责人
    
    # 验证状态
    email_verified = Column(Boolean, default=False)  # 邮箱是否验证
    phone_verified = Column(Boolean, default=False)  # 电话是否验证
    
    # 时间戳
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    last_contacted_at = Column(DateTime, nullable=True)
    
    # 关系
    source = relationship("LeadSource", back_populates="leads")
    notes = relationship("LeadNote", back_populates="lead")
    # owner 关系暂时注释掉，因为 User 模型在同一个文件中定义顺序问题
    # owner = relationship("User", back_populates="leads")
    
    __table_args__ = (
        Index('idx_company_country', 'company_name', 'country'),
        Index('idx_status_created', 'status', 'created_at'),
    )


class User(Base):
    """系统用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    full_name = Column(String(100))
    role = Column(String(50), default='user')  # admin, user, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    
    # leads = relationship("Lead", back_populates="owner")


class LeadNote(Base):
    """线索跟进记录"""
    __tablename__ = "lead_notes"
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    content = Column(Text, nullable=False)
    note_type = Column(String(50), default='general')  # general, call, email, meeting
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    
    lead = relationship("Lead", back_populates="notes")


class Tag(Base):
    """标签表"""
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    color = Column(String(7), default='#3498db')  # 十六进制颜色
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    
    # leads = relationship("LeadTag", back_populates="tag")


class LeadTag(Base):
    """线索标签关联表"""
    __tablename__ = "lead_tag_association"
    
    lead_id = Column(Integer, ForeignKey('leads.id', ondelete='CASCADE'), primary_key=True)
    tag_id = Column(Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
    
    # lead = relationship("Lead", back_populates="tags")
    # tag = relationship("Tag", back_populates="leads")