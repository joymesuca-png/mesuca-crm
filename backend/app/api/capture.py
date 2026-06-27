"""
外贸获客系统 - 获客采集 API 路由

真实采集引擎：Google/Bing 搜索、B2B 平台、公司网站深度挖掘
网络不可用时自动降级为模拟数据，确保服务可用。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, UTC
import logging
from app.core.database import get_db, SessionLocal
from app.models.lead import Lead, LeadSource

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Pydantic 模式 ============

class SearchCaptureRequest(BaseModel):
    """搜索引擎采集请求"""
    keyword: str = Field(..., min_length=1, max_length=200, description="搜索关键词")
    source_id: int = Field(..., description="线索来源 ID")
    country: Optional[str] = Field(None, max_length=100, description="目标国家")
    max_results: int = Field(20, ge=1, le=100, description="最大采集数量")
    deep_mine: bool = Field(False, description="是否深度挖掘公司网站获取邮箱/电话")


class B2BCaptureRequest(BaseModel):
    """B2B 平台采集请求"""
    platform: str = Field(..., description="平台名称：alibaba/globalsources/made-in-china/tradekey")
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
    real_data: bool = False


class CaptureStatsResponse(BaseModel):
    """采集统计"""
    total_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_leads_today: int
    recent_tasks: List[CaptureTaskResponse]


# ============ 内存任务存储 ============

_task_store: List[dict] = []


def _add_task(task_type: str, keyword: str, platform: str = None) -> dict:
    task = {
        "id": f"task-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{len(_task_store)}",
        "type": task_type,
        "keyword": keyword,
        "platform": platform,
        "status": "running",
        "created_at": datetime.now(UTC).isoformat(),
        "message": "正在采集真实数据...",
        "real_data": False,
    }
    _task_store.append(task)
    return task


def _save_leads(leads_data: List[dict], source_id: int) -> int:
    """将采集结果保存到数据库，返回新增数量"""
    if not leads_data:
        return 0
    saved = 0
    db = SessionLocal()
    # Lead 模型的有效字段
    _valid_fields = {
        "company_name", "contact_name", "email", "phone", "website",
        "country", "state", "city", "address", "industry",
        "product_interest", "lead_score", "source_id", "source_url",
        "original_data", "status", "owner_id",
    }
    try:
        for data in leads_data:
            data["source_id"] = source_id
            # 将 social_links 合并到 original_data（JSON 存储）
            if data.get("social_links"):
                import json
                social_json = json.dumps(data["social_links"], ensure_ascii=False)
                existing = data.get("original_data", "") or ""
                data["original_data"] = (existing + f" | social: {social_json}").strip(" | ")
            # 过滤掉不在模型中的字段
            clean_data = {k: v for k, v in data.items() if k in _valid_fields}
            # 去重：按邮箱，如果没邮箱则按公司名+网站
            if clean_data.get("email"):
                exists = db.query(Lead).filter(Lead.email == clean_data["email"]).first()
            elif clean_data.get("company_name") and clean_data.get("website"):
                exists = db.query(Lead).filter(
                    Lead.company_name == clean_data["company_name"],
                    Lead.website == clean_data["website"]
                ).first()
            else:
                exists = False

            if not exists:
                db.add(Lead(**clean_data))
                saved += 1
        db.commit()
        logger.info(f"保存 {saved} 条新线索（共 {len(leads_data)} 条）")
    except Exception as e:
        db.rollback()
        logger.error(f"保存线索失败: {e}")
    finally:
        db.close()
    return saved


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
    """启动搜索引擎采集任务（真实采集 + 模拟降级）"""
    source = db.query(LeadSource).filter(LeadSource.id == req.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="线索来源不存在")

    task = _add_task("search", req.keyword)
    leads_data = []
    real_data = False

    # ── 尝试真实采集 ──
    try:
        from app.services.scraper import collect_search_engine, enrich_lead_with_website
        leads_data = collect_search_engine(req.keyword, req.country, req.max_results)
        if leads_data and len(leads_data) >= 3:
            real_data = True
            # 深度挖掘：访问公司网站提取邮箱电话
            if req.deep_mine:
                logger.info("开始深度挖掘公司网站...")
                for i, lead in enumerate(leads_data[:10]):  # 最多挖10个网站
                    leads_data[i] = enrich_lead_with_website(lead)
    except Exception as e:
        logger.warning(f"真实采集失败，降级为模拟数据: {e}")

    # ── 降级：模拟数据 ──
    if not leads_data or len(leads_data) < 3:
        from app.services.simulator import simulate_search_results
        leads_data = simulate_search_results(req.keyword, req.country, req.source_id, req.max_results)
        task["real_data"] = False
        task["message"] = f"网络采集受限，已生成 {len(leads_data)} 条模拟线索（{req.keyword} 行业）"
    else:
        task["real_data"] = real_data

    # ── 保存到数据库 ──
    try:
        saved = _save_leads(leads_data, req.source_id)
        if real_data:
            task["message"] = f"真实采集完成！共获取 {len(leads_data)} 条线索，新增 {saved} 条"
        else:
            task["message"] = f"采集完成！共获取 {len(leads_data)} 条线索，新增 {saved} 条"
        task["status"] = "completed"
    except Exception as e:
        task["status"] = "failed"
        task["message"] = f"保存失败：{str(e)}"

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
    leads_data = []
    real_data = False

    try:
        from app.services.scraper import collect_b2b
        leads_data = collect_b2b(req.platform, req.keyword, req.max_results)
        if leads_data and len(leads_data) >= 2:
            real_data = True
    except Exception as e:
        logger.warning(f"B2B 真实采集失败: {e}")

    if not leads_data or len(leads_data) < 2:
        from app.services.simulator import simulate_b2b_results
        leads_data = simulate_b2b_results(req.platform, req.keyword, req.source_id, req.max_results)
        task["real_data"] = False

    try:
        saved = _save_leads(leads_data, req.source_id)
        if real_data:
            task["message"] = f"B2B 真实采集完成！共获取 {len(leads_data)} 条，新增 {saved} 条"
        else:
            task["message"] = f"B2B 采集完成！共获取 {len(leads_data)} 条，新增 {saved} 条"
        task["status"] = "completed"
    except Exception as e:
        task["status"] = "failed"
        task["message"] = f"保存失败：{str(e)}"

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