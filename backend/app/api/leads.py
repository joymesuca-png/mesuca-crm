"""
外贸获客系统 - 客户线索 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from app.core.database import get_db
from app.models.lead import Lead, LeadSource
from app.schemas.lead import (
    LeadCreate, LeadUpdate, LeadResponse, LeadListResponse,
    LeadSourceCreate, LeadSourceResponse, LeadSourceUpdate, MessageResponse
)

router = APIRouter()


@router.get("/sources", response_model=list[LeadSourceResponse])
async def get_lead_sources(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取所有线索来源"""
    sources = db.query(LeadSource).offset(skip).limit(limit).all()
    return sources


@router.post("/sources", response_model=LeadSourceResponse, status_code=201)
async def create_lead_source(
    source: LeadSourceCreate,
    db: Session = Depends(get_db)
):
    """创建新的线索来源"""
    db_source = LeadSource(**source.model_dump())
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


@router.put("/sources/{source_id}", response_model=LeadSourceResponse)
async def update_lead_source(
    source_id: int,
    source_update: LeadSourceUpdate,
    db: Session = Depends(get_db)
):
    """更新线索来源"""
    db_source = db.query(LeadSource).filter(LeadSource.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="线索来源不存在")
    
    update_data = source_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_source, field, value)
    
    db.commit()
    db.refresh(db_source)
    return db_source


@router.delete("/sources/{source_id}", response_model=MessageResponse)
async def delete_lead_source(
    source_id: int,
    db: Session = Depends(get_db)
):
    """删除线索来源"""
    db_source = db.query(LeadSource).filter(LeadSource.id == source_id).first()
    if not db_source:
        raise HTTPException(status_code=404, detail="线索来源不存在")
    
    db.delete(db_source)
    db.commit()
    return {"message": "线索来源已成功删除"}


@router.get("/", response_model=LeadListResponse)
async def get_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    country: Optional[str] = None,
    source_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取客户线索列表（支持分页和筛选）"""
    query = db.query(Lead).options(joinedload(Lead.source))
    
    # 应用筛选条件
    if status:
        query = query.filter(Lead.status == status)
    if country:
        query = query.filter(Lead.country == country)
    if source_id:
        query = query.filter(Lead.source_id == source_id)
    if search:
        query = query.filter(
            (Lead.company_name.ilike(f"%{search}%")) |
            (Lead.email.ilike(f"%{search}%"))
        )
    
    # 获取总数
    total = query.count()
    
    # 分页
    offset = (page - 1) * page_size
    leads = query.order_by(Lead.created_at.desc()).offset(offset).limit(page_size).all()
    
    return LeadListResponse(
        items=leads,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("/", response_model=LeadResponse, status_code=201)
async def create_lead(
    lead: LeadCreate,
    db: Session = Depends(get_db)
):
    """创建新的客户线索"""
    # 验证来源是否存在
    source = db.query(LeadSource).filter(LeadSource.id == lead.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="线索来源不存在")
    
    db_lead = Lead(**lead.model_dump())
    db.add(db_lead)
    db.commit()
    db.refresh(db_lead)
    return db_lead


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: int,
    db: Session = Depends(get_db)
):
    """获取单个客户线索详情"""
    lead = db.query(Lead).options(joinedload(Lead.source)).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: int,
    lead_update: LeadUpdate,
    db: Session = Depends(get_db)
):
    """更新客户线索"""
    db_lead = db.query(Lead).options(joinedload(Lead.source)).filter(Lead.id == lead_id).first()
    if not db_lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    
    update_data = lead_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_lead, field, value)
    
    db.commit()
    db.refresh(db_lead)
    return db_lead


@router.delete("/{lead_id}", response_model=MessageResponse)
async def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db)
):
    """删除客户线索"""
    db_lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not db_lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    
    db.delete(db_lead)
    db.commit()
    return {"message": "线索已成功删除"}