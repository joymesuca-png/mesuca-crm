"""
外贸获客系统 - 主应用入口
"""
import logging
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
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
    logger.info("=" * 50)
    logger.info(f"应用启动中: {settings.APP_NAME} v1.0.0")
    logger.info(f"数据库类型: {settings.DATABASE_TYPE}")

    from app.core.database import engine, Base, DATABASE_URL
    logger.info(f"数据库连接: {DATABASE_URL}")

    try:
        from app.models import lead  # noqa: F401
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        # 不阻止启动，允许应用运行后手动修复

    logger.info("=" * 50)


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
from app.api import leads, capture
app.include_router(leads.router, prefix=f"{settings.API_V1_PREFIX}/leads", tags=["leads"])
app.include_router(capture.router, prefix=f"{settings.API_V1_PREFIX}/capture", tags=["capture"])