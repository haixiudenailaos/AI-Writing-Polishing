# 字见润新（AI 写作润色器）

> 一款面向小说与长文本创作的 AI 润色与辅助工具，支持桌面应用与 Web 端，提供批量润色、知识库检索、风格预设、弱网优化等能力。

## 功能特性
- 桌面端（PySide6）：类 VSCode 界面、批量润色、文件管理、风格编辑、主题与 UI 增强
- AI 润色与预测：基于可配置模型与提示词，支持局部润色与剧情预测
- 知识库：支持历史、大纲、人物设定多知识库，混合检索（向量 + BM25）与时序增强
- 导出与自动保存：实时自动保存与目录导出，支持多文档格式（docx/epub/pdf/rtf/odf）
- Web API：FastAPI 提供统一接口与 WebSocket 推送，弱网场景 gzip 压缩优化
- Web 前端：Vue3 + Vite + Pinia + Axios，提供浏览器端润色体验
- 预设风格：内置多种文案风格（如专业编剧、游戏文案、小红书达人、大厂外宣等）
- 构建与发布：提供跨平台打包脚本、预发布检查、Vercel 配置与 CI 工作流

## 技术栈
- 桌面端：`Python 3.10+`、`PySide6`、`requests`、`python-dotenv`
- 文档处理：`python-docx`、`ebooklib`、`beautifulsoup4`、`PyPDF2`、`striprtf`、`odfpy`、`reportlab`
- 后端：`FastAPI`、`Uvicorn`、`Pydantic`、`CORS/GZip Middleware`
- 前端：`Vue 3`、`Vite`、`Pinia`、`Axios`
- 版本与发布：`Git`、`GitHub Actions`、`Vercel`

## 目录结构
- `app/` 桌面端源码（PySide6），含 UI 组件、配置、文本处理与 API 客户端
- `web/backend/` FastAPI 后端入口与业务集成（复用 `app/` 逻辑）
- `web/frontend/` Vue3 前端（Vite 项目），脚手架与页面组件
- `app_data/` 应用数据（知识库、配置迁移备份等）
- `build_*.py` 跨平台打包脚本（含无控制台版本）
- `pre_deploy_check.py` 推送前检查脚本
- `push_to_github.bat` / `push_to_github.sh` GitHub 推送辅助脚本
- `.github/workflows/test.yml` CI 工作流示例
- `.env`、`vercel.json` 环境与部署配置
- `version_info.txt` 版本信息文件

## 快速开始

### 桌面应用
1. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```
2. 运行应用
   ```bash
   python app/main.py
   ```

### Web 后端
1. 安装依赖
   ```bash
   pip install -r web/backend/requirements.txt
   ```
2. 启动服务（默认本地）
   ```bash
   uvicorn web.backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Web 前端
1. 安装依赖
   ```bash
   cd web/frontend
   npm install
   ```
2. 开发模式
   ```bash
   npm run dev
   ```

## 配置说明
- 环境变量：在根目录 `.env` 设置 API Key、Base URL、模型等敏感配置
- 应用配置：`app/config_manager.py` 管理 `AppConfig`（API、风格、主题、导出、工作区、知识库等）
- API 客户端：`app/api_client.py` 统一调用与异常处理
- 预设风格：`web/backend/preset_styles.py` 与 `app/config_manager.py` 的 `PRESET_STYLES`

## 版本信息
- `version_info.txt`：记录版本与编码等元信息（如 `# UTF-8`）
- 桌面端版本字段：`app/config_manager.py:AppConfig.version`
- Git 标签：例如 `v1.2`（见 `.git/refs/tags/v1.2`）与分支 `V1.3`

## 推送到 GitHub
- 已配置远程：`origin = https://github.com/haixiudenailaos/AI-Writing-Polishing.git`
- 当前分支：`V1.3`（跟踪 `origin/V1.3`）
- 直接推送：
  ```bash
  git add .
  git commit -m "docs: 更新 README"
  git push
  ```
- 辅助脚本（Windows）：双击 `push_to_github.bat`，按界面提示完成推送
- 辅助脚本（Mac/Linux）：运行 `./push_to_github.sh`

## 构建与发布
- Windows 无控制台：`python build_noconsole.py`
- macOS：`python build_macos.py`
- 通用打包：`python build_all.py`、`python build_console.py`
- 构建校验：`python verify_build.py`

## CI/CD
- 工作流示例：`.github/workflows/test.yml`，可扩展构建、测试与发布流程
- 部署：`vercel.json` 与 `.vercelignore` 可用于前端/后端在 Vercel 的部署

## 贡献与问题反馈
- Issue 模板：`.github/ISSUE_TEMPLATE/bug_report.md` 与 `feature_request.md`
- 欢迎通过 Issue 与 PR 贡献代码与建议

## 许可证
- 本项目遵循 `LICENSE` 文件所述的开源许可

