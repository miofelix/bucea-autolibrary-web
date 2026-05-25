# AutoLibrary

> Inspired by [KenanZhu/AutoLibrary](https://github.com/KenanZhu/AutoLibrary)

AutoLibrary 已从旧版桌面端 PySide6 + Selenium/WebDriver 项目重构为现代 Web 项目。旧桌面端源码、模板、批处理、浏览器驱动和旧发布流程已清理，不再作为当前项目的一部分。

新版主要解决原项目的两个部署与使用痛点：

- 不再依赖 Selenium、WebDriver、Chromedriver 或本机浏览器驱动，避免浏览器版本、驱动版本和系统环境不匹配导致的启动失败。
- 不再局限于原有桌面端运行环境；通过 Docker 镜像部署，支持 macOS、Windows 和 Linux 使用同一套启动方式。

目标架构：

```text
Vue3 + Vite + TypeScript 管理面板
        |
        | REST / SSE
        v
FastAPI 后端
        |
        | SQLModel / SQLite
        v
本地数据与运行日志
        |
        | httpx.AsyncClient，纯 HTTP，低频请求
        v
学校图书馆系统
```

## Docker 快速部署（推荐）

推荐使用 Docker 部署。普通用户不需要 clone 项目，也不需要安装 Python、Node.js 或本地构建前后端；只需要安装 Docker，一行命令即可启动：

```bash
docker run -d \
  --name autolibrary \
  --restart unless-stopped \
  -p 3000:8000 \
  -v ./data:/app/data \
  miofelix/bucea-autolibrary-web:latest
```

所有配置项均有内置默认值，无需额外配置文件。如需覆盖默认值，通过 `-e` 传入环境变量即可，也可使用 `--env-file .env` 批量加载。

默认访问地址：

```text
http://127.0.0.1:3000
```

### Docker 部署管理

已发布到 Docker Hub 的单个镜像：`miofelix/bucea-autolibrary-web`。用户不需要 Dockerfile，也不需要本地构建镜像。

日常查看和控制：

```bash
docker ps -a --filter name=autolibrary    # 查看容器状态
docker logs -f autolibrary                # 查看实时日志
docker restart autolibrary                # 重启容器
docker stop autolibrary                   # 停止容器（保留数据）
docker start autolibrary                  # 重新启动已存在的容器
docker rm autolibrary                     # 删除容器（数据在 ./data 不受影响）
```

更新到已发布的新镜像：

```bash
docker pull miofelix/bucea-autolibrary-web:latest
docker rm -f autolibrary
docker run -d \
  --name autolibrary \
  --restart unless-stopped \
  -p 3000:8000 \
  -v ./data:/app/data \
  miofelix/bucea-autolibrary-web:latest
```

固定版本或回滚版本：

```bash
docker pull miofelix/bucea-autolibrary-web:0.1.0
docker rm -f autolibrary
docker run -d --name autolibrary --restart unless-stopped -p 3000:8000 \
  --env-file .env \
  -e AUTO_LIBRARY_DATABASE_URL=sqlite:////app/data/autolibrary.db \
  -v ./data:/app/data \
  miofelix/bucea-autolibrary-web:0.1.0
```

数据和配置：

- `data/`：SQLite 数据库和运行数据，需要备份。

迁移到另一台机器时，复制 `data/` 目录即可。排查问题时，先运行 `docker ps -a`，再运行 `docker logs autolibrary`。

单容器说明：FastAPI 监听 8000（容器内），同时提供 `/api` 和前端静态页面。SQLite 文件挂载到宿主机 `./data`。镜像不包含 Selenium、Playwright、Chromedriver 或任何浏览器。

### 可选环境变量

所有配置项均有内置默认值，无需设置即可正常使用。如需覆盖，通过 `docker run -e` 或 `--env-file .env` 传入。完整列表见 `.env.example`。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `AUTO_LIBRARY_SECRET_KEY` | `autolibrary` | 加密图书馆账号密码的密钥 |
| `AUTO_LIBRARY_APP_ENV` | `development` | 运行环境标识 |
| `AUTO_LIBRARY_LOGIN_URL` | `http://10.1.20.7/login` | 图书馆登录入口 |
| `AUTO_LIBRARY_DATABASE_URL` | `sqlite:///./data/autolibrary.db` | 数据库连接地址 |
| `ALLOW_LIVE_TEST` | `true` | 是否允许低频只读 live test |
| `ALLOW_MUTATION_TEST` | `true` | 是否允许写操作 live test |
| `AUTO_LIBRARY_ENABLE_CAPTCHA_OCR` | `true` | 是否启用验证码 OCR |
| `AUTO_LIBRARY_MAX_LOGIN_RETRIES` | `3` | 自动登录最大重试次数 |

如需修改对外端口，修改 `docker run` 中 `-p` 的宿主机端口即可。

## 为什么不使用 WebDriver

新架构禁止 Selenium、Playwright、WebDriver 和真实浏览器自动化。原因：

- 浏览器驱动重、脆弱，部署复杂。
- DOM 点击流程不适合服务端任务调度。
- WebDriver 自动化容易误触真实写操作。
- 验证码、风控、访问控制不应被自动绕过。
- 纯 HTTP 客户端更容易审计、限速、测试和脱敏。

登录会话由后端自动建立：验证码默认通过 `ddddocr` 自动识别并随登录请求提交，识别失败会自动刷新验证码重试。
关闭 `AUTO_LIBRARY_ENABLE_CAPTCHA_OCR` 会使自动登录不可用；前端不再提供人工验证码输入流程。
速率限制（≥3s 查询 / ≥1s 翻页 / ≥60s 提交）始终生效，OCR 不影响请求频率门控。

## 本地开发（可选）

只有需要修改源码或运行测试时，才需要使用本地开发方式。

后端：

```bash
cd backend
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn app.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认开发地址是 `http://127.0.0.1:3000` 或 Vite 输出的本地地址。开发环境通过 Vite proxy 访问后端 `/api`，前端不直接访问图书馆系统。

## 测试

后端：

```bash
cd backend
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
```

前端：

```bash
cd frontend
npm run build
```

当前测试覆盖：

- health check / 账号管理 API / 密码加密 / 日志脱敏 / HAR 脱敏解析
- LibraryClient（httpx MockTransport 模拟 16 个图书馆接口）
- `/api/library/*` 路由（含写操作门禁断言）
- HTML 解析器（座位、时间、房间、历史、CSRF / userInfo）
- 限速器（fake clock）
- 任务 / 作业 / SSE 日志总线（含 blocked_need_user_confirmation 状态机）
- Vue3/Vite/TypeScript 前端生产构建

mock 测试只证明代码结构正确，不证明真实图书馆接口正确。任何 live / mutation 测试都需 `ALLOW_LIVE_TEST` / `ALLOW_MUTATION_TEST` 显式开启。

## 安全声明

本项目仅用于个人学习和已授权账号的低频自动化辅助，不得滥用。

禁止：

- 绕过验证码。
- 绕过频率限制。
- 绕过权限控制。
- 对学校系统进行高频请求。
- 未确认接口时执行真实请求。
- 未确认风险时执行预约、签到、续约、取消等写操作。
- 在日志或 API 响应中暴露密码、Cookie、Token、Session。

## 需要确认的信息

当前仍需确认：

- `POST /selfRes` 是否已经创建真实预约。
- `POST /reservation/cancel` 是否已经取消真实预约。
- `SYNCHRONIZER_TOKEN`、`SYNCHRONIZER_URI`、`authid` 的来源和刷新规则。
- 验证码、房间、座位查询、时间查询、预约历史的响应 body 结构。
- 签到、续约的 HAR/curl。

## 免责声明

本项目仅用于学习、研究和个人授权账号的正常访问辅助。使用者应遵守学校图书馆系统规则，不得影响图书馆系统稳定性，不得干扰他人正常使用。任何真实写操作必须由使用者确认并自行承担责任。
