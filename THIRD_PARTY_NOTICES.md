# Third-Party Notices

This project's own code is MIT licensed (see LICENSE). The components
below are third-party works used under their own licenses.

## Tencent Hy-Memory (MemHub) — Apache License 2.0

- Copyright 2026 Tencent ("One Memory"). All rights reserved.
- Upstream: https://github.com/Tencent-Hunyuan/Hy-Memory
- License text: `third_party/tencent-hy-memory/LICENSE`; upstream NOTICE:
  `third_party/tencent-hy-memory/NOTICE`.
- Used in: `src/lifedb_importers/importers/chatgpt_export.py` (export
  decoding semantics adapted, changes marked in the file header) and
  `src/lifedb_importers/core/memhub.py` (generic-export record shape).
- Changes made: re-implementation against the lifedb unified record
  schema; added kept/skipped accounting for reconciliation. No upstream
  code runs at runtime; the Python standard library is the only dependency.
