# lifedb-importers

**把你散在各平台的人生数据，用数据层直取拿回本地，变成任何 AI 都能调用的统一记忆格式。**

> Take your own data back from the platforms — at the data layer, not via
> screen scraping — into one local, unified JSONL format that any personal
> agent can read. Local-first, read-only, no telemetry.

## 为什么现在做这件事

个人智能体（personal agent）正在成为主流的交互形态：你不再逐个打开 App，而是让一个 Agent 替你读、替你记、替你办。而 Agent 的能力上限，不取决于模型有多聪明，取决于它能拿到多少**你的**上下文——你聊过什么、收藏过什么、买过什么、写过什么。一个对你的过去一无所知的 Agent，再强大也只是个通用聊天机器人。

问题是，这些数据不在你手里。它们散落在几十个平台上，锁在各家服务器和 App 里。平台设置里的“个人信息下载”大多只是合规摆设：给你一份账号基本信息，真正的历史——聊天记录、收藏、浏览足迹、消费、创作——拿不出来；少数能导出的，也各是各的格式，彼此不通。数据是你产生的，却以平台的格式、躺在平台的服务器上、按平台的规矩决定你能不能看。

这件事的分量会随个人智能体普及而变重。谁的记忆完整，谁的 Agent 就真的懂谁；记忆层会成为每个人的个人资产和护城河——而现在，这层资产的地基还握在平台手里：它们可以随时改接口、关导出、封账号，你的历史说没就没。

所以本项目只做一件事：**把数据层补上。**逐个平台把你自己的历史拿回本地，存成开放的统一格式（JSONL），留在你自己的硬盘上，任何模型、任何 Agent 都能读，不绑任何一家厂商。数据主权不是口号，是格式、位置和可迁移性：文件在本地、格式是开放的、换任何工具都能接着用。

现有的记忆类工具大多解决的是“数据进来之后”的事——它们假设数据已经在本地了（比如 AI 编程工具的会话文件）。而国内平台的数据还卡在“进不来”这一步：没有官方导出层，就没有后面的一切。这一层没人做，因为它不性感：要逐平台适配、跟风控和格式变更长期纠缠。本项目做的就是这层地基，从最拿不到数据的中国平台开始。

> In the age of personal agents, your memory is your moat — but it is locked inside platforms. This project is the data layer that brings it home: local files, an open format, readable by any agent.

## 三原则（先于快速开始）

1. **本地运行**：全部处理在你自己的机器上完成；无服务器、无回传、无遥测。
2. **只读**：代码层面不向任何平台发写请求；只处理**你自己**的数据。
3. **低频**：网络型 importer 内置随机间隔限速（禁止固定节奏），遇 403 立即停手，不硬碰风控。

安全立场（写在明处）：本工具**从不收集账号密码**——多数平台的账密登录已被滑块/短信/设备验证锁死，给了密码也省不掉任何一步；需要登录的平台一律走扫码（验证由你手机上已登录的 App 完成）或浏览器 profile 复用（密码只出现在平台官网页面上）。会话只存本地 `~/.lifedb/creds/`（目录 0700 / 文件 0600），发布前有自动扫描脚本保证仓库零个人数据（`./prepublish_scan.sh`）。

## 为什么是数据层直取

| 路线 | 保真度 | 历史回溯 | 结构化 | 代价 |
|---|---|---|---|---|
| **数据层直取（本项目）** | 最高（源数据本身） | 全历史 | 原生结构化 | 逐平台适配 |
| 浏览器捕获（Supermemory 等） | 中（只抓流过 UI 的） | 无（装上才开始） | 半结构化 | 通用、近零适配 |
| 屏幕捕获（Screenpipe） | 低（像素/音频，有损） | 无，只能向前积累 | 无（事后转写） | 万能、隐私代价最大 |

统一契约：每个 importer 实现 `auth / pull / normalize` 三段，输出统一 JSONL（按月分片、稳定 ID = 平台 + 源内 ID 的哈希、幂等重跑字节一致），每步做**三数对账**（源单元数 / 解析单元数 / 落盘数+跳过数），对不上立即失败、绝不静默吞数据。

## 快速开始

```bash
pip install -e .            # 纯标准库，零第三方依赖
lifedb-import list

# ChatGPT：设置 -> 数据控制 -> 导出，拿到 zip 后：
lifedb-import import chatgpt-export --source ~/Downloads/chatgpt-export.zip --out ./out
# chatgpt-export: units=74 records=... skipped=... -> OK; report=out/reports/chatgpt-export.json

# 顺带产出 MemHub 可导入的 generic-export JSONL：
lifedb-import import chatgpt-export --source export.zip --out ./out --to memhub

# 豆包（本地 chats.jsonl / 通用 JSON 导出文件）：
lifedb-import import doubao-file --source chats.jsonl --out ./out

# 任意平台的导出文件 + 一份字段映射（见 templates/mapping.example.json）：
lifedb-import import generic-file --source export.csv --mapping mapping.json --out ./out
```

输出结构：

```
out/
  raw/<platform>/         # 原件落盘（增量拉取的依据）
  data/<platform>/YYYY-MM.jsonl   # 统一记录（一行一条消息）
  memhub/<platform>.jsonl         # --to memhub 时的下游格式
  reports/<importer>.json         # 对账报告
```

## Importer 清单

| importer | 平台 | 入口 | 状态 |
|---|---|---|---|
| chatgpt-export | ChatGPT | 官方导出文件 | ✅ ready |
| doubao-file | 豆包 | 本地文件 | 🟡 beta（主格式已验，通用格式待校准） |
| generic-file | 任意平台 | 导出 JSON/JSONL/CSV + 字段映射 | ✅ ready |
| bilibili-api | B站 | 扫码 | planned（切片 2） |
| wizard | 多平台 | 一条命令扫码马拉松 | planned（切片 3） |
| douban | 豆瓣 | 浏览器 profile 复用 | planned |
| wechat-parse | 微信 | 已解密文件解析半段 | planned |
| kimi-file | Kimi | 单会话导出 | planned（格式未定，未假装支持） |

## 模板（贡献新平台从这里开始）

- `templates/importer-template/`：新平台 importer 脚手架——三段契约代码骨架、本 importer 的 README 模板、合成 fixture 模板、测试模板，照着填即可，步骤与硬规矩写在该目录的 README 里。
- `templates/mapping.example.json`：`generic-file` 的字段映射示例。平台能导出 JSON/CSV 时，先用映射顶上，不必等专用 importer。

## 与 MemHub（腾讯 Hy-Memory）的关系：上下游，不是竞品

MemHub 打通的是**本地 AI 工具**（Codex / Cursor / WorkBuddy 等）的会话文件；本项目打通的是**服务器端平台**（数据在平台服务器上、无官方导出层）。两者可叠加：`--to memhub` 把本项目的记录转成 MemHub 的 generic-export 规范 JSONL，MemHub 可直接当下游记忆层导入。ChatGPT 导出解析的语义借鉴自 Hy-Memory 的开源实现（Apache-2.0），见 `THIRD_PARTY_NOTICES.md`。

## 测试

```bash
python -m unittest discover -s tests -v   # 合成 fixture，全假数据
./prepublish_scan.sh                       # 发布前个人数据扫描，必须零命中
```

## License

自有代码 MIT（见 LICENSE）；第三方组件见 THIRD_PARTY_NOTICES.md。
