# 新增一个平台 importer（模板说明）

照着填，不要从零摸索。已有实现是最好的参考：文件型看
`src/lifedb_importers/importers/doubao_file.py`，带树形会话的看
`chatgpt_export.py`，映射驱动的看 `generic_file.py`。

> 先问一句：这个平台真的需要专用 importer 吗？如果它能导出一份
> JSON/CSV 文件，先用 `generic-file` + `templates/mapping.example.json`
> 顶上；只有格式特殊（树形分支、专有容器）才写专用 importer。

## 步骤

1. **复制骨架**：`importer.py.tmpl` → `src/lifedb_importers/importers/<platform>_xxx.py`，
   按文件头注释逐段填 `auth / pull / normalize`。
2. **写本 importer 的 README 小节**（在本文件这个位置替换为以下结构）：
   - 平台与入口（file / qr / localdb / profile，数据具体从哪来）
   - 原件格式（字段结构、一个脱敏到只剩骨架的样例）
   - 校准状态（拿什么验过：真实样本还是仅合成 fixture——如实写，这是本仓的规矩）
   - 已知边界（数据不全的部分、平台风控、会话有效期）
3. **造合成 fixture**：按 `fixtures/example.json` 的结构放
   `tests/fixtures/<platform>/`，内容全假——真实 UID、号码、个人路径一律不许进，
   `./prepublish_scan.sh` 会拦。
4. **写测试**：`test_importer.py.tmpl` → `tests/test_<platform>.py`，
   对账计数、幂等重跑字节一致、关键字段抽查，三件缺一不可。
5. **登记**：`src/lifedb_importers/core/registry.py` 的 `IMPORTERS`（或从
   `PLANNED` 挪过来）+ 仓库根 `registry.json` 加一行 + 主 README 的
   Importer 清单表加一行。
6. **验收**：`python -m unittest discover -s tests` 全过，
   `./prepublish_scan.sh` 零命中，再提交。

## 硬规矩（与三原则同级）

- 只读：代码层面不对平台发任何写请求；只处理用户自己的数据。
- 从不收集账号密码：登录一律扫码或浏览器 profile 复用（密码只出现在平台官网）。
- 会话/cookie 只经 `core.vault` 存本地（0700/0600），不进仓、不进日志。
- 网络拉取用 `core.ratelimit` 随机间隔，禁止固定节奏；403 立即停手。
- 计数诚实：seen == kept + skipped，对账不过就是失败，不许放宽检查凑绿。
