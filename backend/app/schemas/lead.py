"""
外贸获客系统 - Pydantic 数据模式
"""
from pydantic import BaseModel, EmailStr, HttpUrl, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


class LeadStatusEnum(str, Enum):
    """线索状态枚举"""
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    LOST = "lost"


class LeadSourceEnum(str, Enum):
    """线索来源类型枚举"""
    SEARCH_ENGINE = "search_engine"
    SOCIAL_MEDIA = "social_media"
    B2B_PLATFORM = "b2b_platform"
    CUSTOMS_DATA = "customs_data"
    MAP = "map"
    OTHER = "other"


# ============ 线索来源相关模式 ============

class LeadSourceBase(BaseModel):
    """线索来源基础模式"""
    name: str
    type: LeadSourceEnum
    description: Optional[str] = None
    is_active: bool = True


class LeadSourceCreate(LeadSourceBase):
    """创建线索来源"""
    pass


class LeadSourceUpdate(BaseModel):
    """更新线索来源"""
    name: Optional[str] = None
    type: Optional[LeadSourceEnum] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class LeadSourceResponse(LeadSourceBase):
    """线索来源响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: datetime


# ============ 客户线索相关模式 ============

class LeadBase(BaseModel):
    """客户线索基础模式"""
    company_name: str = Field(..., min_length=1, max_length=200)
    contact_name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=200)
    country: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)
    industry: Optional[str] = Field(None, max_length=100)
    product_interest: Optional[str] = Field(None, max_length=500)
    lead_score: float = 0.0
    source_url: Optional[str] = Field(None, max_length=500)
    original_data: Optional[str] = None  # JSON string


class LeadCreate(LeadBase):
    """创建客户线索"""
    source_id: int


class LeadUpdate(BaseModel):
    """更新客户线索"""
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    industry: Optional[str] = None
    product_interest: Optional[str] = None
    lead_score: Optional[float] = None
    status: Optional[LeadStatusEnum] = None
    owner_id: Optional[int] = None
    source_id: Optional[int] = None
    source_url: Optional[str] = None
    email_verified: Optional[bool] = None
    phone_verified: Optional[bool] = None


class LeadResponse(LeadBase):
    """客户线索响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    source_id: Optional[int] = None
    status: LeadStatusEnum
    owner_id: Optional[int] = None
    email_verified: bool
    phone_verified: bool
    created_at: datetime
    updated_at: datetime
    last_contacted_at: Optional[datetime] = None
    source: Optional[LeadSourceResponse] = None


class LeadListResponse(BaseModel):
    """客户线索列表响应"""
    items: List[LeadResponse]
    total: int
    page: int
    page_size: int


# ============ 跟进记录相关模式 ============

class LeadNoteBase(BaseModel):
    """跟进记录基础模式"""
    content: str
    note_type: str = "general"


class LeadNoteCreate(LeadNoteBase):
    """创建跟进记录"""
    lead_id: int
    user_id: int


class LeadNoteResponse(LeadNoteBase):
    """跟进记录响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    lead_id: int
    user_id: int
    created_at: datetime


# ============ 标签相关模式 ============

class TagBase(BaseModel):
    """标签基础模式"""
    name: str = Field(..., min_length=1, max_length=50)
    color: str = "#3498db"


class TagCreate(TagBase):
    """创建标签"""
    pass


class TagResponse(TagBase):
    """标签响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime


# ============ 用户相关模式 ============

class UserBase(BaseModel):
    """用户基础模式"""
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "user"


class UserCreate(UserBase):
    """创建用户"""
    password: str


class UserResponse(UserBase):
    """用户响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_at: datetime


# ============ 通用响应模式 ============

class MessageResponse(BaseModel):
    """消息响应"""
    message: str


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None