# Verification log (aggregate counts only — no personal data)

## 2026-10-25 · chatgpt-export vs a real official export

Input: one real ChatGPT official export archive (kept outside this repo,
read-only). Ground truth from an independent earlier parse of the same
archive: 74 conversations, 3,662 mapping nodes.

| count | value | note |
|---|---|---|
| source units (conversations) | 74 | includes 1 empty `{}` placeholder entry shipped by the export itself |
| mapping nodes (independent count) | 3,662 | = 3,590 message-bearing + 72 structural (message = null) |
| items seen | 3,590 | message-bearing nodes |
| records written | 2,199 | user/assistant visible text |
| items skipped | 1,391 | 1,376 reasoning content (`thoughts` 678 + `reasoning_recap` 698, all assistant) + 15 empty text |
| reconciliation | OK | units match; seen = written + skipped |
| shards | 2026-08: 102 · 2026-09: 1,766 · 2026-10: 331 | |
| MemHub lane | 2,199 lines | every line parses as JSON with the required generic-export fields |

Found and fixed during this run: exports containing an empty placeholder
conversation crashed the parser; now counted as a zero-message unit
(regression test `test_empty_placeholder_conversation_tolerated`).

## doubao-file

Primary `chats.jsonl` shape verified against the offline HAR extractor
format from a real 12-conversation capture sample (synthetic fixture in
tests mirrors that shape). Workspace holds no full doubao export sample,
so volume/role coverage calibration is still open — status stays `beta`.
