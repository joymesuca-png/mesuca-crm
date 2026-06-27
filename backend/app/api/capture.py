"""
外贸获客系统 - 获客采集 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, UTC
import json
from app.core.database import get_db
from app.core.database import SessionLocal
from app.models.lead import Lead, LeadSource

router = APIRouter()


# ============ Pydantic 模式 ============

class SearchCaptureRequest(BaseModel):
    """搜索引擎采集请求"""
    keyword: str = Field(..., min_length=1, max_length=200, description="搜索关键词")
    source_id: int = Field(..., description="线索来源 ID")
    country: Optional[str] = Field(None, max_length=100, description="目标国家")
    max_results: int = Field(20, ge=1, le=100, description="最大采集数量")


class B2BCaptureRequest(BaseModel):
    """B2B 平台采集请求"""
    platform: str = Field(..., description="平台名称：alibaba/globalsources/made-in-china 等")
    keyword: str = Field(..., min_length=1, description="搜索关键词")
    source_id: int = Field(..., description="线索来源 ID")
    max_results: int = Field(20, ge=1, le=100)


class CaptureTaskResponse(BaseModel):
    """采集任务响应"""
    id: str
    type: str
    keyword: str
    platform: Optional[str] = None
    status: str
    created_at: str
    message: str


class CaptureStatsResponse(BaseModel):
    """采集统计"""
    total_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_leads_today: int
    recent_tasks: List[CaptureTaskResponse]


# ============ 内存任务存储（后续可迁移到 Redis/DB） ============

# 模拟任务存储
_task_store: List[dict] = []


def _add_task(task_type: str, keyword: str, platform: str = None) -> dict:
    task = {
        "id": f"task-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{len(_task_store)}",
        "type": task_type,
        "keyword": keyword,
        "platform": platform,
        "status": "running",
        "created_at": datetime.now(UTC).isoformat(),
        "message": "任务已启动，正在采集数据..."
    }
    _task_store.append(task)
    return task


# ============ API 端点 ============

@router.get("/stats", response_model=CaptureStatsResponse)
async def get_capture_stats():
    """获取采集任务统计"""
    running = sum(1 for t in _task_store if t["status"] == "running")
    completed = sum(1 for t in _task_store if t["status"] == "completed")
    failed = sum(1 for t in _task_store if t["status"] == "failed")
    
    return CaptureStatsResponse(
        total_tasks=len(_task_store),
        running_tasks=running,
        completed_tasks=completed,
        failed_tasks=failed,
        total_leads_today=0,
        recent_tasks=[CaptureTaskResponse(**t) for t in _task_store[-10:]]
    )


@router.post("/search", response_model=CaptureTaskResponse)
async def start_search_capture(
    req: SearchCaptureRequest,
    db: Session = Depends(get_db)
):
    """启动搜索引擎采集任务"""
    # 验证来源
    source = db.query(LeadSource).filter(LeadSource.id == req.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="线索来源不存在")
    
    task = _add_task("search", req.keyword)
    
    # 模拟采集：生成一些演示数据
    try:
        simulated_leads = _simulate_search_results(req.keyword, req.country, req.source_id, req.max_results)
        db2 = SessionLocal()
        try:
            for lead_data in simulated_leads:
                existing = db2.query(Lead).filter(Lead.email == lead_data["email"]).first()
                if not existing:
                    db2.add(Lead(**lead_data))
            db2.commit()
        finally:
            db2.close()
        
        task["status"] = "completed"
        task["message"] = f"采集完成！共获取 {len(simulated_leads)} 条线索"
    except Exception as e:
        task["status"] = "failed"
        task["message"] = f"采集失败：{str(e)}"
    
    return CaptureTaskResponse(**task)


@router.post("/b2b", response_model=CaptureTaskResponse)
async def start_b2b_capture(
    req: B2BCaptureRequest,
    db: Session = Depends(get_db)
):
    """启动 B2B 平台采集任务"""
    source = db.query(LeadSource).filter(LeadSource.id == req.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="线索来源不存在")
    
    task = _add_task("b2b", req.keyword, req.platform)
    
    try:
        simulated_leads = _simulate_b2b_results(req.platform, req.keyword, req.source_id, req.max_results)
        db2 = SessionLocal()
        try:
            for lead_data in simulated_leads:
                existing = db2.query(Lead).filter(Lead.email == lead_data["email"]).first()
                if not existing:
                    db2.add(Lead(**lead_data))
            db2.commit()
        finally:
            db2.close()
        
        task["status"] = "completed"
        task["message"] = f"B2B 采集完成！共获取 {len(simulated_leads)} 条线索"
    except Exception as e:
        task["status"] = "failed"
        task["message"] = f"采集失败：{str(e)}"
    
    return CaptureTaskResponse(**task)


@router.get("/tasks", response_model=List[CaptureTaskResponse])
async def list_tasks():
    """获取所有采集任务列表"""
    return [CaptureTaskResponse(**t) for t in _task_store]


@router.delete("/tasks")
async def clear_tasks():
    """清空任务历史"""
    _task_store.clear()
    return {"message": "任务历史已清空"}


# ============ 模拟数据生成 ============

def _simulate_search_results(keyword: str, country: str, source_id: int, count: int) -> list:
    """模拟搜索引擎采集结果"""
    industries = ["Electronics", "Home & Garden", "Fashion", "Auto Parts", "Machinery"]
    countries = [country] if country else ["USA", "UK", "Germany", "France", "Japan"]
    first_names = ["James", "Sarah", "Michael", "Emma", "David", "Lisa", "Robert", "Anna"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Wilson", "Taylor", "Anderson"]
    
    results = []
    for i in range(min(count, len(companies))):
        # 模拟重名检测
        contact = f"{_pick(first_names, i)} {_pick(last_names, i)}"
        company = _pick(companies, i)
        coin = ["ltd", "inc", "corp", "llc"] if country and country.lower() == "usa" else ["Co., Ltd.", "Group", "International", "Trading"]
        comp_name = f"{company} {_pick(coin, i)}"
        
        results.append({
            "company_name": comp_name,
            "contact_name": contact,
            "email": f"{contact.lower().replace(' ', '.')}@{company.lower().replace(' ', '')}.com",
            "phone": f"+1-{_rand(200, 999)}-{_rand(1000, 9999)}",
            "website": f"https://www.{company.lower().replace(' ', '')}.com",
            "country": _pick(countries, i),
            "city": _pick(["New York", "London", "Berlin", "Paris", "Tokyo", "Los Angeles", "Chicago", "Houston"], i),
            "industry": _pick(industries, i),
            "product_interest": keyword,
            "lead_score": round(_rand(40, 95) + _rand(0, 9) * 0.1, 1),
            "source_id": source_id,
            "source_url": f"https://www.google.com/search?q={keyword}+{industry}",
            "status": "new"
        })
    return results


def _simulate_b2b_results(platform: str, keyword: str, source_id: int, count: int) -> list:
    """模拟 B2B 平台采集结果"""
    results = _simulate_search_results(keyword, None, source_id, count)
    for r in results:
        r["source_url"] = f"https://www.{platform}.com/search?q={keyword}"
        r["lead_score"] = round(_rand(50, 90) + _rand(0, 9) * 0.1, 1)
    return results


# 预置数据
companies = [
    "TechVision", "GlobalTrade", "Sunrise", "OceanBridge", "SmartHome",
    "EuroParts", "GreenLight", "BlueOcean", "StarLink", "PowerMax",
    "EcoProducts", "MegaDeal", "PrimeSource", "FirstChoice", "TopGear",
    "AlphaTech", "BestSupply", "QuickShip", "GoldStar", "NewWave",
    "DirectLink", "ProMarket", "SkyHigh", "WorldClass", "UltraGoods",
    "SpeedTrade", "ValuePlus", "NextGen", "ClearPath", "BrightIdea"
]

_rand = lambda lo, hi: __import__('random').randint(lo, hi)
_pick = lambda arr, i: arr[i % len(arr)]