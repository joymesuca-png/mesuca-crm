"""
外贸获客系统 - 主应用入口
"""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import get_settings
from app.core.database import engine, Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="外贸客户获取系统 - 从多渠道获取潜在客户信息",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 全局异常处理 ============

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={"error": "Validation Error", "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred"}
    )


# ============ 生命周期事件 ============

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    logger.info("正在启动应用...")
    # 仅开发环境自动创建表，生产环境使用 Alembic 迁移
    if settings.DEBUG:
        from app.models import lead  # noqa: F401
        Base.metadata.create_all(bind=engine)
        logger.info("开发模式：已自动创建数据库表")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    logger.info("正在关闭应用...")


# ============ 路由 ============

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "欢迎使用外贸获客系统 API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


# 导入并注册路由
from app.api import leads
app.include_router(leads.router, prefix=f"{settings.API_V1_PREFIX}/leads", tags=["leads"])