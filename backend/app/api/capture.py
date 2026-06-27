"""
外贸获客系统 - 获客采集 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, UTC
import random
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

# 各地区数据
_CITIES = {
    "USA": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Miami", "Seattle", "Boston"],
    "UK": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Bristol", "Liverpool"],
    "Germany": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne", "Stuttgart"],
    "France": ["Paris", "Lyon", "Marseille", "Toulouse", "Bordeaux", "Lille"],
    "Japan": ["Tokyo", "Osaka", "Nagoya", "Yokohama", "Kyoto", "Fukuoka"],
    "Canada": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"],
    "Australia": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "Brazil": ["Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador"],
    "India": ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad"],
}

_FIRST_NAMES = ["James", "Sarah", "Michael", "Emma", "David", "Lisa", "Robert", "Anna",
                "Daniel", "Sophia", "Thomas", "Olivia", "William", "Emily", "Kevin", "Grace",
                "Ryan", "Linda", "Jason", "Jessica", "Brian", "Amanda", "Chris", "Nancy"]

_LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Wilson", "Taylor",
               "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson",
               "Garcia", "Martinez", "Robinson", "Clark", "Lewis", "Lee", "Walker", "Hall"]

# 公司后缀，按国家匹配
_CO_SUFFIX = {
    "USA": ["Inc.", "LLC", "Corp.", "Ltd.", "Group"],
    "UK": ["Ltd.", "PLC", "Group", "Holdings", "International"],
    "Germany": ["GmbH", "AG", "KG", "Group", "International"],
    "France": ["SARL", "SAS", "SA", "Group", "International"],
    "Japan": ["Co., Ltd.", "KK", "Corp.", "Group", "International"],
    "default": ["Co., Ltd.", "Group", "International", "Trading", "Corp."]
}

# 行业关键词映射
_INDUSTRY_MAP = {
    "light": "Lighting & Electrical",
    "led": "Lighting & Electrical",
    "lamp": "Lighting & Electrical",
    "auto": "Auto Parts & Accessories",
    "car": "Auto Parts & Accessories",
    "toy": "Toys & Hobbies",
    "toki": "Toys & Hobbies",
    "doll": "Toys & Hobbies",
    "figure": "Toys & Hobbies",
    "fashion": "Apparel & Fashion",
    "clothing": "Apparel & Fashion",
    "garment": "Apparel & Fashion",
    "bag": "Bags & Luggage",
    "shoe": "Footwear",
    "electronic": "Consumer Electronics",
    "phone": "Consumer Electronics",
    "computer": "IT & Technology",
    "software": "IT & Technology",
    "machine": "Industrial Machinery",
    "tool": "Hardware & Tools",
    "furniture": "Furniture & Home",
    "home": "Home & Garden",
    "kitchen": "Kitchen & Dining",
    "food": "Food & Beverage",
    "drink": "Food & Beverage",
    "medical": "Medical Devices",
    "health": "Health & Beauty",
    "beauty": "Health & Beauty",
    "cosmetic": "Health & Beauty",
    "sport": "Sports & Outdoors",
    "fitness": "Sports & Outdoors",
    "chemical": "Chemicals & Materials",
    "plastic": "Plastics & Rubber",
    "metal": "Metals & Mining",
    "steel": "Metals & Mining",
    "textile": "Textiles & Fabrics",
    "fabric": "Textiles & Fabrics",
    "paper": "Packaging & Printing",
    "pack": "Packaging & Printing",
    "solar": "Renewable Energy",
    "energy": "Renewable Energy",
    "default": "General Trade",
}


def _guess_industry(keyword: str) -> str:
    """根据关键词推测行业"""
    kw = keyword.lower()
    for key, industry in _INDUSTRY_MAP.items():
        if key in kw:
            return industry
    return _INDUSTRY_MAP["default"]


def _gen_company_name(keyword: str, i: int) -> str:
    """根据关键词生成相关的公司名"""
    kw = keyword.strip().title()
    # 多种命名模式，随机选取
    patterns = [
        f"{kw} {_random_pick(['International', 'Group', 'Trading', 'Industries', 'Products', 'Solutions', 'Hub', 'Zone', 'World', 'Direct', 'Express', 'Pro', 'Elite', 'Premium', 'Global', 'Supply', 'Link', 'Plus', 'Max', 'Star'])}",
        f"{_random_pick(['Best', 'Prime', 'Apex', 'Nova', 'Ultra', 'Mega', 'Top', 'First', 'Royal', 'Sunrise', 'Pacific', 'Atlantic', 'Golden', 'Silver', 'Diamond', 'Crystal', 'Bright', 'Smart', 'Eco', 'True'])} {kw}",
        f"{kw} {_random_pick(['Source', 'Line', 'Net', 'Way', 'Port', 'Trade', 'Mart', 'Expo'])}",
        f"{_random_pick(['New', 'Modern', 'Advanced', 'Creative', 'Dynamic', 'United', 'Superior', 'Innovative'])} {kw}",
        f"{kw} {_random_pick(['Manufacturing', 'Trading', 'Import & Export', 'Distribution', 'Supply Chain'])}",
    ]
    return f"{random.choice(patterns)} {_random_pick(_CO_SUFFIX.get('default', _CO_SUFFIX['default']), i)}"


def _random_pick(arr: list, i: int = 0) -> str:
    """随机选取数组元素"""
    return arr[random.randint(0, len(arr) - 1)]


def _simulate_search_results(keyword: str, country: str, source_id: int, count: int) -> list:
    """模拟搜索引擎采集结果 — 公司名和行业匹配关键词"""
    countries = [country] if country else list(_CITIES.keys())
    industry = _guess_industry(keyword)
    # 每次运行使用不同的随机种子，确保重复采集不重复
    batch_id = datetime.now(UTC).strftime("%m%d%H%M") + str(random.randint(100, 999))
    
    results = []
    for i in range(count):
        c = random.choice(countries)
        comp_name = _gen_company_name(keyword, i)
        first = random.choice(_FIRST_NAMES)
        last = random.choice(_LAST_NAMES)
        contact = f"{first} {last}"
        # 用关键词 + 批次ID + 序号 生成唯一邮箱，确保每次采集不重复
        email_slug = keyword.lower().replace(" ", "")[:10]
        domain = comp_name.lower().split()[0]
        email = f"{first.lower()}.{last.lower()}.{email_slug}{batch_id}.{i}@{domain}.com"
        
        results.append({
            "company_name": comp_name,
            "contact_name": contact,
            "email": email,
            "phone": f"+1-{random.randint(200, 999)}-{random.randint(1000, 9999)}",
            "website": f"https://www.{domain}.com",
            "country": c,
            "city": random.choice(_CITIES.get(c, ["City"])),
            "industry": industry,
            "product_interest": keyword,
            "lead_score": round(random.randint(40, 95) + random.randint(0, 9) * 0.1, 1),
            "source_id": source_id,
            "source_url": f"https://www.google.com/search?q={keyword}+{industry}",
            "status": "new"
        })
    return results


def _simulate_b2b_results(platform: str, keyword: str, source_id: int, count: int) -> list:
    """模拟 B2B 平台采集结果"""
    results = _simulate_search_results(keyword, "default", source_id, count)
    for r in results:
        r["source_url"] = f"https://www.{platform}.com/search?q={keyword}"
        r["lead_score"] = round(random.randint(50, 90) + random.randint(0, 9) * 0.1, 1)
    return results