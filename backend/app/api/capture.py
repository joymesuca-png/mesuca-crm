"""
外贸获客系统 - 获客采集 API 路由

核心原则：真实采集必须返回真实数据。
- 网络不可用 / 被反爬拦截 → 任务标记为 failed，明确告知原因
- 部分成功（数量不足）→ 任务标记为 partial，保存已有数据并提示
- 模拟数据仅在用户显式开启 simulate=true 时生成（用于测试/演示）
"""
from fastapi import APIRouter, Depends, HTTPException, Query
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
    simulate: bool = Field(False, description="（仅测试）显式使用模拟数据，不进行真实采集")


class B2BCaptureRequest(BaseModel):
    """B2B 平台采集请求"""
    platform: str = Field(..., description="平台名称：alibaba/globalsources/made-in-china/tradekey")
    keyword: str = Field(..., min_length=1, description="搜索关键词")
    source_id: int = Field(..., description="线索来源 ID")
    max_results: int = Field(20, ge=1, le=100)
    simulate: bool = Field(False, description="（仅测试）显式使用模拟数据，不进行真实采集")


class CaptureTaskResponse(BaseModel):
    """采集任务响应"""
    id: str
    type: str
    keyword: str
    platform: Optional[str] = None
    status: str  # running / completed / partial / failed
    created_at: str
    message: str
    real_data: bool = False
    new_leads: int = 0
    total_collected: int = 0


class CaptureStatsResponse(BaseModel):
    """采集统计"""
    total_tasks: int
    running_tasks: int
    completed_tasks: int
    partial_tasks: int
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
        "new_leads": 0,
        "total_collected": 0,
    }
    _task_store.append(task)
    return task


def _save_leads(leads_data: List[dict], source_id: int) -> int:
    """将采集结果保存到数据库，返回新增数量"""
    if not leads_data:
        return 0
    saved = 0
    db = SessionLocal()
    _valid_fields = {
        "company_name", "contact_name", "email", "phone", "website",
        "country", "state", "city", "address", "industry",
        "product_interest", "lead_score", "source_id", "source_url",
        "original_data", "status", "owner_id",
    }
    try:
        for data in leads_data:
            data["source_id"] = source_id
            if data.get("social_links"):
                import json
                social_json = json.dumps(data["social_links"], ensure_ascii=False)
                existing = data.get("original_data", "") or ""
                data["original_data"] = (existing + f" | social: {social_json}").strip(" | ")
            clean_data = {k: v for k, v in data.items() if k in _valid_fields}

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
    partial = sum(1 for t in _task_store if t["status"] == "partial")
    failed = sum(1 for t in _task_store if t["status"] == "failed")

    return CaptureStatsResponse(
        total_tasks=len(_task_store),
        running_tasks=running,
        completed_tasks=completed,
        partial_tasks=partial,
        failed_tasks=failed,
        total_leads_today=0,
        recent_tasks=[CaptureTaskResponse(**t) for t in _task_store[-10:]]
    )


# ── 反爬限制常量 ──
_DEEP_MINE_MAX = 10     # 深度挖掘时最多采集 10 条（避免触发反爬）
_NORMAL_MAX = 30         # 普通采集单次最多 30 条
_ANTI_SCRAPE_TIPS = [
    "请尝试缩小采集数量（建议 ≤ 10 条），避免触发反爬机制",
    "请尝试添加目标国家筛选，缩小搜索范围",
    "请尝试使用更具体的关键词（如 'LED bulb manufacturer' 替代 'LED'）",
    "请等待 1-2 分钟后重试，避免频繁请求被封锁",
    "深度挖掘已开启时会自动限制采集数量 ≤ 10 条",
]


@router.post("/search", response_model=CaptureTaskResponse)
async def start_search_capture(
    req: SearchCaptureRequest,
    db: Session = Depends(get_db)
):
    """启动搜索引擎采集任务。

    核心规则：
    - 默认只进行真实采集，不生成任何模拟数据
    - 被反爬 / 无结果时返回明确失败原因
    - 部分结果也会保存，但标记为 partial 状态
    - 仅当 simulate=true 时使用模拟数据（测试/演示用）
    """
    source = db.query(LeadSource).filter(LeadSource.id == req.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="线索来源不存在")

    # ── 反爬限制：深度挖掘时自动限制采集数量 ──
    effective_max = req.max_results
    if req.deep_mine and effective_max > _DEEP_MINE_MAX:
        effective_max = _DEEP_MINE_MAX
        logger.info(f"深度挖掘已开启，采集数量自动限制为 {effective_max} 条")
    elif not req.deep_mine and effective_max > _NORMAL_MAX:
        effective_max = _NORMAL_MAX

    task = _add_task("search", req.keyword)

    # ── 显式模拟数据模式 ──
    if req.simulate:
        task["real_data"] = False
        from app.services.simulator import simulate_search_results
        leads_data = simulate_search_results(req.keyword, req.country, req.source_id, req.max_results)
        saved = _save_leads(leads_data, req.source_id)
        task["status"] = "completed"
        task["message"] = f"[模拟数据] 已生成 {len(leads_data)} 条测试线索，新增 {saved} 条（仅供测试，非真实客户）"
        task["new_leads"] = saved
        task["total_collected"] = len(leads_data)
        return CaptureTaskResponse(**task)

    # ── 真实采集 ──
    leads_data = []
    error_reason = None

    try:
        from app.services.scraper import collect_search_engine, enrich_lead_with_website
        leads_data = collect_search_engine(req.keyword, req.country, effective_max)
        task["real_data"] = True

        if leads_data and req.deep_mine:
            logger.info(f"开始深度挖掘 {min(len(leads_data), _DEEP_MINE_MAX)} 个公司网站...")
            for i, lead in enumerate(leads_data[:_DEEP_MINE_MAX]):
                leads_data[i] = enrich_lead_with_website(lead)
    except Exception as e:
        error_reason = f"采集引擎异常: {str(e)}"
        logger.error(error_reason)

    # ── 结果判定 ──
    if leads_data and len(leads_data) >= 3:
        # 足够的结果
        saved = _save_leads(leads_data, req.source_id)
        task["status"] = "completed"
        task["message"] = f"真实采集完成！共获取 {len(leads_data)} 条线索，新增 {saved} 条"
        task["new_leads"] = saved
        task["total_collected"] = len(leads_data)
    elif leads_data and len(leads_data) > 0:
        # 部分结果（数量不足，但保存已有的）
        saved = _save_leads(leads_data, req.source_id)
        task["status"] = "partial"
        task["message"] = (
            f"部分成功：仅获取到 {len(leads_data)} 条真实线索（新增 {saved} 条）。"
            f"建议：{_ANTI_SCRAPE_TIPS[0]}"
        )
        task["new_leads"] = saved
        task["total_collected"] = len(leads_data)
    else:
        # 无结果
        reason = error_reason or "搜索引擎未返回有效结果，可能被反爬机制拦截"
        task["status"] = "failed"
        task["message"] = (
            f"采集失败：{reason}。"
            f"建议：{_ANTI_SCRAPE_TIPS[1]}；{_ANTI_SCRAPE_TIPS[2]}"
        )
        task["new_leads"] = 0
        task["total_collected"] = 0

    return CaptureTaskResponse(**task)


@router.post("/b2b", response_model=CaptureTaskResponse)
async def start_b2b_capture(
    req: B2BCaptureRequest,
    db: Session = Depends(get_db)
):
    """启动 B2B 平台采集任务。

    核心规则同搜索引擎采集。
    """
    source = db.query(LeadSource).filter(LeadSource.id == req.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="线索来源不存在")

    effective_max = min(req.max_results, _NORMAL_MAX)
    task = _add_task("b2b", req.keyword, req.platform)

    # ── 显式模拟数据模式 ──
    if req.simulate:
        task["real_data"] = False
        from app.services.simulator import simulate_b2b_results
        leads_data = simulate_b2b_results(req.platform, req.keyword, req.source_id, req.max_results)
        saved = _save_leads(leads_data, req.source_id)
        task["status"] = "completed"
        task["message"] = f"[模拟数据] 已生成 {len(leads_data)} 条测试线索，新增 {saved} 条（仅供测试，非真实客户）"
        task["new_leads"] = saved
        task["total_collected"] = len(leads_data)
        return CaptureTaskResponse(**task)

    # ── 真实采集 ──
    leads_data = []
    error_reason = None

    try:
        from app.services.scraper import collect_b2b
        leads_data = collect_b2b(req.platform, req.keyword, effective_max)
        task["real_data"] = True
    except Exception as e:
        error_reason = f"B2B 采集异常: {str(e)}"
        logger.error(error_reason)

    if leads_data and len(leads_data) >= 2:
        saved = _save_leads(leads_data, req.source_id)
        task["status"] = "completed"
        task["message"] = f"B2B 真实采集完成！共获取 {len(leads_data)} 条，新增 {saved} 条"
        task["new_leads"] = saved
        task["total_collected"] = len(leads_data)
    elif leads_data and len(leads_data) > 0:
        saved = _save_leads(leads_data, req.source_id)
        task["status"] = "partial"
        task["message"] = (
            f"部分成功：仅获取到 {len(leads_data)} 条真实线索（新增 {saved} 条）。"
            f"建议：尝试更换平台或使用更具体的关键词"
        )
        task["new_leads"] = saved
        task["total_collected"] = len(leads_data)
    else:
        reason = error_reason or f"平台 {req.platform} 未返回有效结果，可能被反爬机制拦截"
        task["status"] = "failed"
        task["message"] = (
            f"采集失败：{reason}。"
            f"建议：尝试更换平台（如阿里巴巴国际站），或使用更具体的关键词"
        )
        task["new_leads"] = 0
        task["total_collected"] = 0

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