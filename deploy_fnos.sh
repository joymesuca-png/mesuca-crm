#!/bin/bash

# ==========================================
# 飞牛OS (fnOS) 外贸获客系统一键部署脚本
# ==========================================
# 用法：bash deploy.sh
# ==========================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  外贸获客系统 (Mesuca CRM) 部署脚本${NC}"
echo -e "${GREEN}=========================================${NC}"

# 配置变量
PROJECT_DIR="/volume1/docker/mesuca-crm"
REPO_URL="https://github.com/joymesuca-png/mesuca-crm.git"
ENV_FILE=".env"

# 1. 检查 Docker 是否安装
echo -e "${YELLOW}[1/6] 检查 Docker 环境...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误：未检测到 Docker，请先在飞牛OS应用中心安装 Docker${NC}"
    exit 1
fi
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误：未检测到 Docker Compose${NC}"
    exit 1
fi
echo -e "${GREEN}Docker 环境检查通过${NC}"

# 2. 创建项目目录并克隆代码
echo -e "${YELLOW}[2/6] 准备项目目录...${NC}"
if [ -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}目录 $PROJECT_DIR 已存在，跳过克隆${NC}"
    cd "$PROJECT_DIR"
    # 如果是 git 仓库，尝试拉取最新代码
    if [ -d ".git" ]; then
        echo "拉取最新代码..."
        git pull || echo -e "${YELLOW}拉取失败，请手动检查${NC}"
    fi
else
    mkdir -p "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    echo "正在克隆代码库..."
    git clone "$REPO_URL" .
fi

# 3. 生成环境变量文件
echo -e "${YELLOW}[3/6] 生成配置文件 (.env)...${NC}"
if [ ! -f "$ENV_FILE" ]; then
    # 生成随机密码
    DB_PASS=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 16)
    SECRET_KEY=$(openssl rand -hex 32)
    
    cat > $ENV_FILE <<EOF
# 项目配置
PROJECT_NAME=mesuca-crm
ENVIRONMENT=production
BACKEND_PORT=8000
FRONTEND_PORT=3000

# 数据库配置
POSTGRES_USER=lead_admin
POSTGRES_PASSWORD=${DB_PASS}
POSTGRES_DB=lead_capture

MONGO_INITDB_ROOT_USERNAME=mongo_admin
MONGO_INITDB_ROOT_PASSWORD=${DB_PASS}

REDIS_PASSWORD=${DB_PASS}

# 安全配置
SECRET_KEY=${SECRET_KEY}

# Elasticsearch 配置
ELASTICSEARCH_HOST=elasticsearch
ES_JVM_HEAP=1g

# 邮件配置 (请根据实际情况修改)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_NAME="Mesuca CRM"
SMTP_FROM_EMAIL=noreply@mesuca.com
EOF
    echo -e "${GREEN}配置文件已生成：$PROJECT_DIR/$ENV_FILE${NC}"
    echo -e "${YELLOW}注意：请编辑 $ENV_FILE 文件，修改 SMTP 邮件配置为您的真实邮箱信息！${NC}"
else
    echo -e "${GREEN}配置文件已存在，跳过生成${NC}"
fi

# 4. 调整 Elasticsearch 内存设置 (防止启动失败)
echo -e "${YELLOW}[4/6] 优化 Elasticsearch 配置...${NC}"
# 确保 ES 堆内存不超过物理内存的50%，这里默认设为 1g 以适应大多数 NAS 环境
sed -i 's/ES_JVM_HEAP=.*/ES_JVM_HEAP=1g/' $ENV_FILE || true
echo -e "${GREEN}Elasticsearch 内存限制已设置为 1GB${NC}"

# 5. 构建并启动服务
echo -e "${YELLOW}[5/6] 构建 Docker 镜像 (首次运行可能需要 5-10 分钟)...${NC}"
docker-compose up -d --build

# 6. 检查服务状态
echo -e "${YELLOW}[6/6] 检查服务运行状态...${NC}"
sleep 5
docker-compose ps

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}=========================================${NC}"

# 获取本机 IP
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${YELLOW}访问地址：${NC}"
echo -e "  前端界面: http://${LOCAL_IP}:3000"
echo -e "  API 文档: http://${LOCAL_IP}:8000/docs"
echo -e "  Celery 监控: 查看日志 docker-compose logs -f worker"
echo ""
echo -e "${YELLOW}重要提示：${NC}"
echo -e "  1. 首次启动后，请等待 1-2 分钟让数据库初始化完成。"
echo -e "  2. 请务必修改 .env 文件中的 SMTP 配置，否则邮件功能无法使用。"
echo -e "  3. 如果遇到 Elasticsearch 启动失败，请尝试增加 ES_JVM_HEAP 值或检查内存。"
echo -e "  4. 默认管理员账号请在数据库中查看或通过 API 注册 (如果开启了注册)。"
echo ""
echo -e "查看日志命令: cd $PROJECT_DIR && docker-compose logs -f"
echo -e "重启服务命令: cd $PROJECT_DIR && docker-compose restart"
