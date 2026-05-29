# AI 试卷批改系统

基于 AI 视觉模型的智能试卷批改工具。上传学生作答的试卷图片，自动识别版面结构、逐题批改打分，并生成教师口吻的评语。

## 功能

- **版面分析** — 自动识别试卷的大题/小题/作答区结构，支持分批分析处理大题量试卷
- **智能批改** — 对照参考答案逐题判断对错、打分、生成评语
- **答案提取** — 从答案图片或文本中自动提取参考答案
- **试卷模板** — 保存已分析的试卷版面 + 参考答案为模板，批量批改多个学生
- **批量批改** — 一次上传多份学生答卷，按模板依次自动批改（SSE 实时进度）
- **交互修正** — 批改结果可逐题手动修正对错、分数、答案、评语
- **历史记录** — 所有批改记录持久化存储，支持查看和删除
- **提示词管理** — 在线编辑版面分析 / AI 批改 / 答案提取的提示词
- **SVG 批改叠层** — 批改结果以 SVG 标注覆盖在学生答题图片上

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python FastAPI + Uvicorn |
| 前端 | Vue 3 (Composition API) + TypeScript |
| UI 库 | Element Plus |
| 构建 | Vite |
| 数据库 | SQLite |
| AI | 火山引擎豆包视觉模型 (OpenAI 兼容接口) |
| 包管理 | pnpm (前端) / pip (后端) |

## 快速开始

### 1. 配置环境变量

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`，填入 API 密钥和模型端点 ID：

```
API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
API_KEY=your_api_key_here
EP_ID=ep-xxxxxxxxxxxxxx
```

### 2. 启动后端

```bash
pip install -r backend/requirements.txt
python run.py
```

后端运行在 `http://localhost:8000`，首次启动会自动创建 SQLite 数据库和存储目录。

### 3. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

前端运行在 `http://localhost:5173`，开发服务器自动代理 `/api` 和 `/static` 到后端 `:8000`。

### 生产构建

```bash
cd frontend
pnpm build
```

构建产物输出到 `frontend/dist/`。

## 使用流程

1. 打开首页，点击「新建模板」上传一张空白试卷图片
2. AI 自动分析版面结构（大题 → 小题 → 作答区）
3. 可上传答案图片或手动输入参考答案
4. 在「上传学生答卷」步骤上传学生作答图片（可多选）
5. 点击「开始批改」，SSE 实时推送批改进度
6. 批改完成后逐题查看结果，支持手动修正

## 项目结构

```
├── run.py                    # 后端启动入口
├── backend/
│   ├── main.py               # FastAPI 应用初始化
│   ├── config.py             # 配置加载（环境变量 + 路径）
│   ├── database.py           # SQLite 数据库 CRUD + 默认种子数据
│   ├── models.py             # Pydantic 数据模型
│   ├── routers/              # API 路由
│   │   ├── analysis.py       # 版面分析
│   │   ├── grading.py        # AI 批改（含 SSE 流式）
│   │   ├── templates.py      # 试卷模板管理
│   │   ├── prompts.py        # 提示词管理
│   │   └── history.py        # 历史记录
│   ├── analysis/
│   │   ├── engine.py         # AI 版面分析引擎
│   │   └── grading_engine.py # AI 批改引擎 + 答案提取
│   └── storage/              # 运行时数据（gitignored）
│       ├── app.db            # SQLite 数据库
│       ├── uploads/          # 上传的试卷图片
│       ├── annotated/        # 标注后的图片
│       ├── grading_uploads/  # 批改用图片
│       └── answer_keys/      # 答案图片
├── frontend/
│   ├── src/
│   │   ├── views/            # 页面组件
│   │   ├── components/       # 通用组件
│   │   ├── stores/           # Pinia 状态管理
│   │   ├── api/              # Axios API 客户端
│   │   ├── utils/            # 工具函数（SSE、图片压缩）
│   │   ├── types/            # TypeScript 类型定义
│   │   ├── router/           # 路由配置
│   │   └── styles/           # 全局样式
│   └── vite.config.ts        # Vite 配置（代理 :8000）
└── AGENTS.md                 # 开发参考文档
```

## 提示词管理

访问 `/prompts` 页面可在线编辑三类提示词：

- **版面分析提示词** — 控制 AI 如何识别试卷结构，支持 `{img_w}`、`{img_h}` 占位符
- **批改提示词** — 控制 AI 如何批改，支持 `{standard_answers_section}`、`{layout_json}`、`{subject}` 占位符
- **答案提取提示词** — 控制 AI 如何从答案图片提取参考答案

数据库中未存储的学科/学段组合会自动回退到代码中内置的默认提示词。

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analyze` | 上传图片进行版面分析 |
| POST | `/api/grade/stream` | SSE 流式批改（分析 + 批改） |
| POST | `/api/grade/with-template/{template_id}/stream` | 基于模板批量批改 |
| GET | `/api/grade/{grading_id}` | 获取批改结果 |
| PUT | `/api/grade/{grading_id}` | 手动修正批改结果 |
| DELETE | `/api/grade/{grading_id}` | 删除批改记录 |
| GET/POST/PUT/DELETE | `/api/templates` | 模板管理 |
| GET/PUT | `/api/prompts` | 提示词管理 |
| GET/DELETE | `/api/history` | 历史记录 |

## 注意事项

- 上传图片建议使用扫描仪扫描，若用相机拍摄请确保拍到试卷四条边、尽量正对减少倾斜
- 前端自动压缩大图片（>1MB 质量 0.5，>5MB 质量 0.7，>10MB 拒绝上传）
- AI 批改耗时较长，前端 axios 超时 360s，后端 AI 调用超时 300s
- `backend/storage/` 目录为运行时数据，已加入 `.gitignore`，部署时需保留或重新生成
