# BidPivot — 极智标枢·标书智造平台

基于 LLM 与多智能体协作的标书自动生成平台。

## 功能特性

- **智能生成**：上传招标文件 → AI 解析生成大纲 → 多 Agent 并行写作 → 汇总校验
- **知识驱动**：私有/全局知识库，RAG 检索增强，数字溯源高亮
- **在线编辑**：Tiptap 富文本编辑器，对话式 AI 修改，版本对比
- **多格式导出**：DOCX、PDF 导出，支持自定义排版模板
- **竞品分析**：竞品资料管理，差异化分析报告
- **丢标分析**：评标结果解析，三层分析（原因/改进/策略）
- **系统管理**：模型配置、用户管理、审计日志、Token 统计

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Ant Design Vue + Vben Admin + Tiptap |
| 后端 | Python FastAPI + SQLAlchemy + Celery |
| AI 编排 | LangGraph + LangChain |
| 向量库 | Qdrant |
| 数据库 | PostgreSQL 15+ |
| 缓存/队列 | Redis |
| 文件存储 | MinIO |
| 容器化 | Docker Compose / Kubernetes |

## 前端技术栈

- **Vue 3** + **TypeScript** - 核心框架
- **Ant Design Vue** - UI 组件库
- **Vben Admin** - 布局框架（侧边栏、顶部导航、面包屑）
- **Tiptap** - 富文本编辑器
- **Pinia** - 状态管理
- **Axios** - HTTP 客户端

## 快速开始

### Docker Compose（推荐）

```bash
git clone <repo-url>
cd BidPivot
cp .env.example .env
docker-compose up -d          # PostgreSQL / Redis / Qdrant / MinIO / backend / celery
# 后端会执行 alembic upgrade head
cd vben-admin && pnpm install
pnpm --filter @bidpivot/frontend dev
# 前端: http://localhost:5173
# 后端 API: http://localhost:8000/docs
```

### 手动启动（开发环境）

```bash
docker-compose up -d postgres redis qdrant minio

cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

cd ../vben-admin && pnpm install && pnpm --filter @bidpivot/frontend dev

celery -A app.celery_app worker --loglevel=info
```

### 测试脚本（一键启动）

```bash
./test.sh        # Linux/Mac
.\test.ps1       # Windows
./stop.sh        # 停止
```

## 开发指南

前端是 Vben Admin monorepo 的子应用，统一使用 pnpm：

```bash
cd vben-admin
pnpm install
pnpm --filter @bidpivot/frontend dev        # http://localhost:5173
pnpm --filter @bidpivot/frontend build
pnpm --filter @bidpivot/frontend typecheck
pnpm --filter @bidpivot/frontend test
```

### 更新前端 API 类型

后端启动后执行：

```bash
python scripts/generate-openapi-types.py
# 输出 vben-admin/apps/bidpivot-frontend/src/types/openapi.ts
```

### 运行测试

```bash
# 后端
cd backend && pytest

# 浏览器 smoke（需先启动前端 5173 与后端 8000）
cd test && CHROME_PATH=/usr/bin/google-chrome pnpm test
```

## 项目结构

```
BidPivot/
├── backend/          # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/   # API 端点
│   │   ├── models/   # 数据库模型
│   │   ├── schemas/  # Pydantic 模式
│   │   ├── services/ # 业务逻辑
│   │   │   └── agents/ # AI Agent
│   │   └── tasks/    # Celery 任务
│   └── alembic/      # 数据库迁移
├── frontend/         # Vue 3 前端
│   └── src/
│       ├── api/      # API 调用
│       ├── components/ # 组件
│       ├── views/    # 页面
│       └── stores/   # 状态管理
├── k8s/              # Kubernetes 配置
├── docker/           # Docker 配置
├── docs/             # 文档
├── test.sh           # 测试启动脚本
└── docker-compose.yml
```

## 文档

- [操作手册](docs/operation-manual.md)
- [部署文档](docs/deployment.md)
- [API 文档](http://localhost:8000/docs)

## 许可证

MIT License
