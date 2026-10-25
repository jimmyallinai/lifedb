"""Importer registry. Adding a platform = one importer class + one entry
here (and one row in registry.json). Core never changes.
"""

from __future__ import annotations

from ..importers.chatgpt_export import ChatGPTExportImporter
from ..importers.doubao_file import DoubaoFileImporter
from ..importers.generic_file import GenericFileImporter
from .base import Importer

IMPORTERS: dict[str, Importer] = {
    ChatGPTExportImporter.name: ChatGPTExportImporter(),
    DoubaoFileImporter.name: DoubaoFileImporter(),
    GenericFileImporter.name: GenericFileImporter(),
}

# Declared roadmap (status shown by `lifedb-import list`). Not implemented;
# listed so users can see the intended coverage and its honest status.
PLANNED: list[dict] = [
    {"name": "bilibili-api", "platform": "bilibili", "entry_kind": "qr",
     "status": "planned", "note": "QR login + Web API pull (slice 2)"},
    {"name": "wizard", "platform": "-", "entry_kind": "qr",
     "status": "planned", "note": "one-command multi-platform QR marathon (slice 3)"},
    {"name": "douban", "platform": "douban", "entry_kind": "profile",
     "status": "planned", "note": "browser profile reuse; user logs in on the official page"},
    {"name": "wechat-parse", "platform": "wechat", "entry_kind": "localdb",
     "status": "planned", "note": "parses an already-decrypted export file only; decryption is out of scope"},
    {"name": "kimi-file", "platform": "kimi", "entry_kind": "file",
     "status": "planned", "note": "single-conversation export format not yet fixed; not supported yet"},
]


def get(name: str) -> Importer:
    try:
        return IMPORTERS[name]
    except KeyError:
        raise SystemExit(f"unknown importer: {name} (see `lifedb-import list`)")
