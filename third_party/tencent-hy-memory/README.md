# Third-party provenance: Tencent Hy-Memory

- Upstream: https://github.com/Tencent-Hunyuan/Hy-Memory (memhub/)
- License: Apache License 2.0 — full text in `LICENSE` next to this file;
  upstream attribution in `NOTICE` ("One Memory, Copyright 2026 Tencent").
- What we used: the ChatGPT/Claude export decoding semantics implemented in
  `memhub/apps/core/src/one_memory/imports/chat_exports.py` (fetched from
  the upstream `main` branch on 2026-10-25), and the generic-export record
  shape defined by `memhub/apps/core/src/one_memory/imports/sources/exported.py`
  (`parse_export_record`).
- How we used it: `src/lifedb_importers/importers/chatgpt_export.py`
  re-implements those semantics for the lifedb record schema (file header
  marks the adaptation); `src/lifedb_importers/core/memhub.py` emits the
  generic-export shape. No upstream code is imported at runtime and no
  upstream files are vendored beyond the LICENSE/NOTICE copies required
  for attribution.
