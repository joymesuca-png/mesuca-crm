"""
外贸获客系统 - 获客采集 API 路由

核心原则：真实采集必须返回真实数据。
- 采集前检查网络连通性，被墙直接返回失败原因
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
    max_results: int = Field(5, ge=1, le=100, description="最大采集数量")
    deep_mine: bool = Field(False, description="是否深度挖掘公司网站获取邮箱/电话")
    simulate: bool = Field(False, description="（仅测试）显式使用模拟数据，不进行真实采集")


class B2BCaptureRequest(BaseModel):
    """B2B 平台采集请求"""
    platform: str = Field(..., description="平台名称：alibaba/globalsources/made-in-china/tradekey")
    keyword: str = Field(..., min_length=1, description="搜索关键词")
    source_id: int = Field(..., description="线索来源 ID")
    max_results: int = Field(5, ge=1, le=100)
    simulate: bool = Field(False, description="（仅测试）显式使用模拟数据，不进行真实采集")


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


# ============ 反爬限制常量 ============

_DEEP_MINE_MAX = 10
_NORMAL_MAX = 30


# ============ API 端点 ============

@router.get("/connectivity")
async def check_connectivity():
    """快速检查采集源网络连通性（4 秒超时）"""
    from app.services.scraper import check_connectivity as do_check
    import os
    result = do_check()
    reachable = [k for k, v in result.items() if v.get("reachable")]
    unreachable = [k for k, v in result.items() if not v.get("reachable")]
    proxy = os.getenv("SCRAPER_PROXY_URL", "")
    if proxy:
        if not reachable:
            msg = f"已配置代理 {proxy}，但所有境外采集源仍不可达。请检查代理是否正常运行。"
        else:
            msg = f"代理 {proxy} 工作正常！可用的采集源：{', '.join(reachable)}"
    else:
        if not reachable:
            msg = "所有境外采集源均不可达。服务器可能位于境内网络，境外网站被防火墙拦截。请配置代理 SCRAPER_PROXY_URL 或使用测试模式。"
        else:
            msg = f"可用的采集源：{', '.join(reachable)}。不可用：{', '.join(unreachable) if unreachable else '无'}"
    return {
        "sources": result,
        "timestamp": datetime.now(UTC).isoformat(),
        "message": msg,
        "proxy_configured": bool(proxy),
        "proxy_url": proxy or None,
    }


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


# ──────────────── 搜索引擎采集 ────────────────

@router.post("/search", response_model=CaptureTaskResponse)
async def start_search_capture(
    req: SearchCaptureRequest,
    db: Session = Depends(get_db)
):
    source = db.query(LeadSource).filter(LeadSource.id == req.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="线索来源不存在")

    effective_max = req.max_results
    if req.deep_mine and effective_max > _DEEP_MINE_MAX:
        effective_max = _DEEP_MINE_MAX
    elif not req.deep_mine and effective_max > _NORMAL_MAX:
        effective_max = _NORMAL_MAX

    task = _add_task("search", req.keyword)

    # ── 模拟数据模式 ──
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

    # ── 连通性预检 ──
    from app.services.scraper import check_connectivity as do_check
    connectivity = do_check()
    baidu_ok = connectivity.get("baidu", {}).get("reachable", False)
    google_ok = connectivity.get("google", {}).get("reachable", False)
    bing_ok = connectivity.get("bing", {}).get("reachable", False)
    yp_ok = connectivity.get("yellow_pages", {}).get("reachable", False)

    if not baidu_ok and not google_ok and not bing_ok and not yp_ok:
        task["status"] = "failed"
        task["message"] = (
            "采集失败：百度、Google、Bing 均不可达。请检查网络连接。"
        )
        task["new_leads"] = 0
        task["total_collected"] = 0
        return CaptureTaskResponse(**task)

    # ── 真实采集 ──
    from app.services.scraper import collect_search_engine, enrich_lead_with_website
    leads_data = []
    error_reason = None

    try:
        leads_data = collect_search_engine(req.keyword, req.country, effective_max)
        task["real_data"] = True

        if leads_data and req.deep_mine:
            for i, lead in enumerate(leads_data[:_DEEP_MINE_MAX]):
                leads_data[i] = enrich_lead_with_website(lead)
    except Exception as e:
        error_reason = f"采集引擎异常: {str(e)}"
        logger.error(error_reason)

    if leads_data and len(leads_data) >= 3:
        saved = _save_leads(leads_data, req.source_id)
        task["status"] = "completed"
        task["message"] = f"真实采集完成！共获取 {len(leads_data)} 条线索，新增 {saved} 条"
        task["new_leads"] = saved
        task["total_collected"] = len(leads_data)
    elif leads_data and len(leads_data) > 0:
        saved = _save_leads(leads_data, req.source_id)
        task["status"] = "partial"
        task["message"] = f"部分成功：仅获取到 {len(leads_data)} 条真实线索（新增 {saved} 条）。建议缩小采集范围或使用更具体的关键词"
        task["new_leads"] = saved
        task["total_collected"] = len(leads_data)
    else:
        reason = error_reason or "搜索引擎未返回有效结果，可能被反爬机制拦截"
        task["status"] = "failed"
        task["message"] = f"采集失败：{reason}。建议：添加目标国家筛选，或使用更具体的关键词"
        task["new_leads"] = 0
        task["total_collected"] = 0

    return CaptureTaskResponse(**task)


# ──────────────── B2B 平台采集 ────────────────

@router.post("/b2b", response_model=CaptureTaskResponse)
async def start_b2b_capture(
    req: B2BCaptureRequest,
    db: Session = Depends(get_db)
):
    source = db.query(LeadSource).filter(LeadSource.id == req.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="线索来源不存在")

    effective_max = min(req.max_results, _NORMAL_MAX)
    task = _add_task("b2b", req.keyword, req.platform)

    # ── 模拟数据模式 ──
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

    # ── 连通性预检 ──
    from app.services.scraper import check_connectivity as do_check
    connectivity = do_check()
    _platform_to_conn = {
        "alibaba": ["alibaba", "1688"], "globalsources": ["alibaba"],
        "made-in-china": ["made_in_china"], "tradekey": ["alibaba"],
    }
    conn_keys = _platform_to_conn.get(req.platform.lower(), [req.platform.lower()])
    reachable = any(connectivity.get(k, {}).get("reachable", False) for k in conn_keys)

    if not reachable:
        task["status"] = "failed"
        task["message"] = (
            f"采集失败：平台 {req.platform} 不可达。请检查网络连接。"
        )
        task["new_leads"] = 0
        task["total_collected"] = 0
        return CaptureTaskResponse(**task)

    # ── 真实采集 ──
    from app.services.scraper import collect_b2b
    leads_data = []
    error_reason = None

    try:
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
        task["message"] = f"部分成功：仅获取到 {len(leads_data)} 条真实线索（新增 {saved} 条）。建议更换平台或使用更具体的关键词"
        task["new_leads"] = saved
        task["total_collected"] = len(leads_data)
    else:
        reason = error_reason or f"平台 {req.platform} 未返回有效结果，可能被反爬机制拦截"
        task["status"] = "failed"
        task["message"] = f"采集失败：{reason}。建议更换平台（如阿里巴巴国际站），或使用更具体的关键词"
        task["new_leads"] = 0
        task["total_collected"] = 0

    return CaptureTaskResponse(**task)


# ──────────────── 任务管理 ────────────────

@router.get("/tasks", response_model=List[CaptureTaskResponse])
async def list_tasks():
    return [CaptureTaskResponse(**t) for t in _task_store]


@router.delete("/tasks")
async def clear_tasks():
    _task_store.clear()
    return {"message": "任务历史已清空"}