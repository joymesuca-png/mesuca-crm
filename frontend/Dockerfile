# 前端构建镜像
FROM node:18-alpine AS builder

WORKDIR /app

# 复制 package.json (如果存在)
COPY package*.json ./
RUN npm install || echo "No package.json, skipping install"

# 复制源代码
COPY . .

# 构建前端 (如果是 Vue/React 项目)
RUN npm run build || echo "No build script, skipping build"

# 生产环境镜像
FROM nginx:alpine

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物或静态文件
COPY --from=builder /app/dist /usr/share/nginx/html 2>/dev/null || \
COPY --from=builder /app/build /usr/share/nginx/html 2>/dev/null || \
COPY . /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
