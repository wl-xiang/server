# Server Manager

后台服务管理脚本：以守护方式启动任意前台命令，并提供停止、状态查询、日志查看、日志滚动、健康检查与日志清理能力。脚本仅使用 POSIX `sh` 语法，兼容 `dash` 与 `bash`，进程在 SSH 断连后继续常驻运行。

## 项目概况

- **进程保活**：`setsid` + `nohup` 回退，服务进入独立会话，SSH 断连不影响服务。
- **进程组管理**：停止时向整个进程组发信号，避免子进程（worker、包装脚本）残留占端口。
- **PID 身份校验**：PID 文件同时记录进程启动时间，防止 PID 复用后误杀无关进程。
- **启动判定**：至少做一次存活检查；配置健康检查后，启动必须在其就绪后才算成功。
- **并发保护**：启动/停止/重启/清理共用一把带持有者 PID 的锁，避免双实例。
- **日志追踪**：每次启动写入会话头、记录退出码与停止来源，按配置滚动备份。
- **配置隔离**：通过 `.env` 管理环境变量，代码与配置分离。
- **统一输出**：控制台输出为英文；仅在 TTY 下输出颜色（遵循 `NO_COLOR`）。

## 目录结构

```
.
├── server          # 服务管理脚本（主入口）
├── test_server.py  # 用于测试/演示的示例前台服务
├── .env.example    # 环境变量配置模板
├── .gitignore
└── README.md
```

运行时会在脚本目录（或 `STATE_DIR`）下产生：

```
server.pid          # PID 与进程元数据
.server.pid.lock    # 启动/停止/清理互斥锁（运行时短暂存在）
logs/server.log     # 当前日志
logs/server.log.bak.N
```

## 快速开始

```bash
cp .env.example .env
# 编辑 .env，填写 START_COMMAND
./server start
./server status
./server logs -f
./server stop
```

示例（不写 `.env`，直接命令行指定）：

```bash
./server start --command "python3 test_server.py"
```

## 命令说明

| 命令 | 说明 |
|------|------|
| `start` | 后台启动服务，包含启动前/后钩子与启动校验 |
| `stop` | 优雅停止（SIGTERM），超时后自动升级为 SIGKILL |
| `shutdown` | 立即强制停止（SIGKILL） |
| `restart` | 重启服务；未运行时直接启动，支持 `start` 同款选项 |
| `status` | 查看状态，退出码见下文 |
| `logs` | 查看日志，支持 `-n NUM` 与 `-f` |
| `clean` | 清理日志，支持 `-y` 与 `--dry-run` |
| `help` | 显示帮助 |

### status 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 运行中（配置了 `HEALTH_COMMAND` 且检查通过） |
| `1` | 运行中，但健康检查失败 |
| `3` | 未运行（LSB 约定） |

`status` 会额外显示记录的启动命令与日志路径；停止状态下会显示日志里最后一次退出码记录。

### start / restart 选项

| 选项 | 说明 |
|------|------|
| `-c, --command CMD` | 设置启动命令 |
| `-b, --before CMD` | 启动前执行的命令（失败则中止启动） |
| `-a, --after CMD` | 启动后执行的命令（失败仅告警） |
| `-h, --help` | 显示帮助 |

### logs 选项

| 选项 | 说明 |
|------|------|
| `-n, --lines NUM` | 只显示最后 NUM 行（必须是数字） |
| `-f, --follow` | 持续跟踪日志 |

默认输出整个日志文件（不是最后 10 行）。

### clean 选项

| 选项 | 说明 |
|------|------|
| `-y, --yes` | 跳过确认 |
| `-n, --dry-run` | 只列出将被删除的文件 |

服务运行时拒绝清理。标准输入为 TTY 且未指定 `-y` 时会要求确认；非交互环境（cron/CI）下直接执行。

## 环境变量配置

所有参数均可通过 `.env`、shell 环境变量或命令行设置。

| 变量 | 是否必填 | 默认值 | 说明 |
|------|----------|--------|------|
| `START_COMMAND` | 必填 | - | 启动命令，支持完整 shell 语法 |
| `BEFORE_COMMAND` | 可选 | 空 | 启动前执行的命令，非 0 退出则中止启动 |
| `AFTER_COMMAND` | 可选 | 空 | 启动后执行的命令，失败仅告警 |
| `HEALTH_COMMAND` | 可选 | 空 | 就绪/健康检查命令，退出 0 视为健康 |
| `LOG_DIR` | 可选 | `logs` | 日志目录，相对路径基于脚本目录 |
| `LOG_FILE_NAME` | 可选 | `server.log` | 日志文件名（不能含 `/` 或通配符） |
| `LOG_MAX_BACKUPS` | 可选 | `2` | 日志备份保留份数；`0` 表示不保留备份 |
| `STATE_DIR` | 可选 | 脚本目录 | PID 文件与锁文件目录，相对路径基于脚本目录 |
| `PID_FILE_NAME` | 可选 | `server.pid` | PID 文件名（不能含 `/` 或通配符） |
| `WORK_DIR` | 可选 | 脚本目录 | 服务与钩子的工作目录 |
| `START_WAIT` | 可选 | `1` | 启动后等待就绪的秒数 |
| `STOP_TIMEOUT` | 可选 | `30` | SIGTERM 后等待退出的秒数，超时升级为 SIGKILL |
| `HOOK_TIMEOUT` | 可选 | `0` | 钩子超时秒数；`0` 表示不限制（需要系统有 `timeout`） |

### 配置优先级

1. 命令行参数（`-c/-b/-a`）最高。
2. shell 环境变量次之。
3. `.env` 文件最低。

同一个键如果在 shell 中已经导出且非空，`.env` 不会覆盖它（符合常见 dotenv 约定）。空值视为未设置。

### `.env` 语法

- `KEY=VALUE`，键两侧与值两侧的空格/Tab 会被裁剪。
- 支持用一对单引号或双引号包裹整个值；引号会被去掉。
- 支持整行注释（`#` 开头）与行尾注释（`#` 前有空白时）。含 `#` 的命令请用引号包裹。
- 支持 CRLF（Windows）换行。
- 值按字面量读取，**不做**变量展开、命令替换或多行值。需要展开时在 shell 中 `export` 后再启动。
- 键必须匹配 `[A-Za-z_][A-Za-z0-9_]*`，非法行会被忽略。

### 配置示例

```bash
# .env
START_COMMAND=python3 test_server.py --port 8080
BEFORE_COMMAND=mkdir -p ./data && echo preparing   # 失败会中止启动
AFTER_COMMAND=
LOG_DIR=logs
LOG_FILE_NAME=server.log
LOG_MAX_BACKUPS=5
START_WAIT=3
STOP_TIMEOUT=20
HEALTH_COMMAND=python3 ./healthcheck.py 8080
```

## 日志管理

日志默认位于 `logs/server.log`。

### 日志滚动

每次 `start` 前自动滚动，最多保留 `LOG_MAX_BACKUPS` 份：

- `server.log` — 当前日志
- `server.log.bak.1` — 上一次运行
- `server.log.bak.2` — 上上次运行

`LOG_MAX_BACKUPS=0` 时旧日志直接删除、不留备份。滚动失败时不会截断现有日志，只会告警并继续追加，避免丢日志。

### 日志内容约定

每次启动都会写入会话头与生命周期标记，便于定位“哪次运行出的问题”：

```
===== 2026-10-21 10:00:00 | start | command: python3 app.py =====
===== [before hook] 2026-10-21 10:00:01 =====
...服务输出...
[manager] service exited with status 1 at 2026-10-21 10:05:33
[manager] service stopped by manager (SIGTERM) at 2026-10-21 10:10:02
```

- `service exited with status N`：服务自行退出（崩溃/正常结束）。
- `service stopped by manager (...)`：由 `stop`/`shutdown` 停止，括号内为最终信号。

### 清理日志

```bash
./server clean --dry-run   # 预览
./server clean -y          # 直接删除
```

> 服务运行时禁止清理；清理动作与启动/停止共用互斥锁，不会与启动竞态。

### 长跑服务的日志增长

脚本只在启动时滚动日志，不会限制单次运行期间的日志大小。长跑服务请配合系统 `logrotate` 使用 `copytruncate`（服务以 `>>` 追加写，兼容该模式），或自行控制日志输出量。

## 进程管理说明

### 启动

1. 获取互斥锁（锁文件内记录持有者 PID，可识别陈旧锁）。
2. 滚动并截断日志，写入会话头。
3. 执行 `BEFORE_COMMAND`，非 0 退出则中止并清理。
4. 使用 `setsid sh -c "<command>; 记录退出码"` 启动，脱离终端会话。
5. **立即写入 PID 文件**，再等待 `START_WAIT` 秒做存活/健康检查。
6. 检查失败时杀掉整个进程组、删除 PID 文件并回显日志尾部。

`START_WAIT=0` 时仍会做一次存活检查。配置 `HEALTH_COMMAND` 时，它作为就绪门禁：超时未通过则启动失败。

### 停止

- 优先向**进程组**发送信号；`setsid` 不可用时退化为只向主 PID 发送。
- `stop`：SIGTERM → 等待 `STOP_TIMEOUT` → 仍在运行则 SIGKILL。
- `shutdown`：直接 SIGKILL。
- 只有确认主进程与整个进程组都退出后才删除 PID 文件；否则保留 PID 文件并返回 1。

### PID 文件

第一行是 PID（兼容 `cat server.pid`），随后是元数据：

```
12345
start=123456789
pgid=12345
pgid_valid=1
cmd=python3 app.py
```

`start` 为 `/proc/<pid>/stat` 的进程启动时间，用于识别 PID 复用；`pgid_valid=1` 表示该进程是独立进程组首进程。

> 第一行的 PID 是**启动包装 shell** 的 PID（它同时是服务进程组的首进程），实际服务通常是它的子进程。这样既能记录退出码，又能通过进程组一次性停止整棵进程树。不要只凭这个 PID 判断业务进程是否健康，请使用 `status` 或 `HEALTH_COMMAND`。

> **升级提示**：旧版本写入的 PID 文件只有一行 PID，没有身份信息，脚本会按兼容模式直接信任它。升级后建议删除旧的 `server.pid`，避免把复用后的 PID 误认成服务进程。

### 并发与中断

- `start`/`stop`/`shutdown`/`restart`/`clean` 共用一把锁，任何时刻只允许一个状态变更操作。
- 启动窗口内收到 `INT`/`TERM`：脚本会杀掉刚启动的服务、删除 PID 文件、释放锁再退出。
- `HUP` 被捕获（不退出），SSH 断连不会让启动过程留下残留锁；子进程仍保持默认处置。

## 健康检查

配置 `HEALTH_COMMAND` 后：

- `start` 把它作为就绪门禁：`START_WAIT` 秒内未通过则判定启动失败。
- `status` 会执行它：通过返回 0，失败返回 1。

健康命令在 `WORK_DIR` 中执行，应尽量快速返回（脚本不对其额外设置超时）。示例：

```bash
HEALTH_COMMAND=python3 -c "import socket,sys; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',8080))"
```

## 生命周期钩子

- 钩子输出写入日志文件，并带独立的分节标记。
- `BEFORE_COMMAND` 失败会中止启动；`AFTER_COMMAND` 失败只告警（服务已在运行）。
- `HOOK_TIMEOUT > 0` 且系统提供 `timeout` 时，钩子会被强制超时。
- 钩子以 `sh -c` 执行，支持完整 shell 语法。**请确保 `.env` 与环境变量可信。**

## 兼容性

- `#!/bin/sh`，仅使用 POSIX 语法；已在 `dash` 与 `bash` 下完整跑通测试。
- 不依赖 `[[ ]]`、`BASH_SOURCE`、`echo -e`、`disown`、`local`。
- 进程身份校验依赖 `/proc`；非 Linux 平台自动退化为 `kill -0`（不校验启动时间）。
- 进程组信号依赖 `setsid`；系统没有 `setsid` 时退化为 `nohup` + 只向主 PID 发送信号，子进程清理能力随之下降。
- 通过符号链接调用时会解析真实路径，`.env`、日志与状态文件始终留在脚本真实目录。
- `LOG_DIR`、`STATE_DIR`、`WORK_DIR` 的相对路径均基于脚本目录，不受调用者当前目录影响。

## 已知限制

1. **仅支持前台运行型命令**。自行 `fork` 后退出的命令（如 `nginx` 默认模式）会被判定为启动失败，脚本会清理其残留进程组。请让服务保持前台运行（`daemon off` / `--foreground`）。
2. **不做自动重启/守护**。进程退出后状态变为 stopped，不会自动拉起。生产环境建议交给 systemd/supervisor，本脚本用于单机快捷启停与日志追踪。
3. **不支持 `reload`**。脚本没有统一的配置重载语义（不同服务对 `SIGHUP` 的处理不同），需要重载时请重启，或由业务侧自行提供信号/接口。
4. **单机单实例语义**。同一目录默认管理一个服务；需要多实例时，为每个实例设置不同的 `PID_FILE_NAME` 与 `LOG_FILE_NAME`（可选不同 `STATE_DIR`）。
5. **不处理服务内部自身的 daemon 化与进程组逃逸**（如子进程自行 `setsid`）。
6. **非 Linux 平台没有 PID 复用防护**。
7. 钩子与 `START_COMMAND` 具备完整 shell 执行能力，脚本本身不提供沙箱或权限隔离。

## 测试

仓库内提供了示例服务 `test_server.py`：

```bash
# 正常启动
./server start --command "python3 test_server.py"

# 带健康检查的启动（端口就绪后才算启动成功）
HEALTH_COMMAND="python3 -c 'import socket; s=socket.socket(); s.settimeout(1); s.connect((\"127.0.0.1\",8080))'" \
  ./server start --command "python3 test_server.py --port 8080"

# 模拟启动后很快崩溃（用足够的 START_WAIT 观察启动判定）
START_WAIT=3 ./server start --command "python3 test_server.py --crash-after 1"

# 模拟忽略 SIGTERM（用于验证 SIGKILL 升级）
STOP_TIMEOUT=2 ./server start --command "python3 test_server.py --ignore-term"
```

`test_server.py` 支持 `--port`、`--start-delay`、`--crash-after`、`--ignore-term`。
