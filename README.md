# 外贸获客系统

一个基于 Python FastAPI 的外贸客户获取系统，支持从多种渠道采集潜在客户信息。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      应用服务层                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 任务调度 │ │ 渠道管理 │ │ 数据处理 │ │  CRM     │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                     采集执行层                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │搜索引擎  │ │ B2B 平台  │ │ 海关数据 │ │ 地图获客 │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                     数据存储层                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │PostgreSQL│ │ MongoDB  │ │  Redis   │ │Elasticsearch    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## 技术栈

### 后端
- **框架**: FastAPI + Uvicorn
- **数据库**: PostgreSQL (关系型), MongoDB (文档型)
- **缓存/队列**: Redis + Celery
- **搜索**: Elasticsearch
- **爬虫**: Playwright
- **ORM**: SQLAlchemy 2.0

### 前端 (待开发)
- Vue 3 + TypeScript
- Element Plus
- Axios

### 部署
- Docker + Docker Compose
- Nginx (反向代理)

## 快速开始

### 环境要求
- Python 3.12+
- Docker & Docker Compose
- Node.js 18+ (前端开发)

### 使用 Docker Compose 启动（推荐）

```bash
cd docker
docker-compose up -d
```

服务将运行在：
- API: http://localhost:8000
- API 文档：http://localhost:8000/docs
- PostgreSQL: localhost:5432
- MongoDB: localhost:27017
- Redis: localhost:6379
- Elasticsearch: localhost:9200

### 本地开发

#### 1. 安装依赖
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件配置数据库连接等
```

#### 3. 启动服务
```bash
# 启动 API 服务
uvicorn app.main:app --reload

# 启动 Celery Worker (新终端)
celery -A app.core.celery_app worker --loglevel=info
```

## 项目结构

```
backend/
├── app/
│   ├── api/           # API 路由
│   ├── core/          # 核心配置
│   ├── models/        # 数据模型
│   ├── schemas/       # Pydantic 模式
│   ├── services/      # 业务逻辑
│   ├── tasks/         # Celery 任务
│   ├── utils/         # 工具函数
│   └── main.py        # 应用入口
├── tests/             # 测试文件
├── requirements.txt   # Python 依赖
└── Dockerfile         # Docker 配置

docker/
└── docker-compose.yml # Docker Compose 配置
```

## 核心功能模块

### 1. 多渠道采集引擎
- 搜索引擎获客 (Google, Bing)
- B2B 平台采集 (阿里巴巴，Global Sources)
- 海关数据导入
- 地图获客 (Google Maps)

### 2. 数据清洗验证
- 邮箱格式验证
- 域名有效性检查
- 数据去重合并
- 标准化处理

### 3. 客户管理中心
- 线索公海池
- 客户跟进记录
- 标签分类管理
- 线索评分系统

### 4. 营销触达
- 邮件营销集成
- WhatsApp 批量发送
- 营销活动追踪

## API 使用示例

### 创建线索来源
```bash
curl -X POST "http://localhost:8000/api/v1/leads/sources" \
  -H "Content-Type: application/json" \
  -d '{"name": "Google Search", "type": "search_engine"}'
```

### 获取线索列表
```bash
curl "http://localhost:8000/api/v1/leads/?page=1&page_size=20&country=USA"
```

### 创建新客户线索
```bash
curl -X POST "http://localhost:8000/api/v1/leads/" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "ABC Company",
    "email": "contact@abc.com",
    "country": "USA",
    "source_id": 1
  }'
```

## 开发路线图

### 第一阶段 (MVP)
- [x] 项目初始化
- [x] 基础架构搭建
- [ ] 实现搜索引擎爬虫
- [ ] 基础 CRUD API
- [ ] 简单的前端界面

### 第二阶段
- [ ] B2B 平台采集
- [ ] 邮箱验证服务
- [ ] 数据去重算法
- [ ] Celery 异步任务优化

### 第三阶段
- [ ] 完整 CRM 功能
- [ ] 邮件营销模块
- [ ] 数据分析报表
- [ ] 用户权限管理

## 注意事项

1. **合规性**: 确保爬取行为符合目标网站的 robots.txt 和相关法规
2. **反爬虫**: 实施请求限流、IP 轮换、User-Agent 池等策略
3. **数据安全**: 敏感信息加密存储，定期备份数据
4. **性能优化**: 对大数据量查询建立索引，使用缓存

## License

MIT License
