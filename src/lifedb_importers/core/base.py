"""Three-stage importer contract (v3 spec, frozen): auth -> pull -> normalize.

Differences between platforms are only allowed inside each stage.
- auth():      resolve where the data comes from (export file / QR login /
               local db path). Produces a context dict. File importers never
               touch credentials; login importers store sessions ONLY in the
               vault (~/.lifedb/creds, 0700/0600).
- pull():      fetch/copy raw payloads under <out>/raw/<platform>/, honoring
               the watermark (--since). Read-only: no write requests to any
               platform, ever.
- normalize(): raw payloads -> unified records (core.schema). Must count
               everything it saw: kept + skipped == total, or reconciliation
               fails the run.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PullResult:
    raw_paths: list[Path]
    source_units: int          # top-level units in the raw payload (e.g. conversations)
    detail: dict = field(default_factory=dict)


@dataclass
class NormalizeResult:
    records: list[dict]        # unified records (not yet deduplicated/sharded)
    units_seen: int            # top-level units parsed
    items_seen: int            # raw items seen (kept + skipped)
    items_skipped: int


class Importer(abc.ABC):
    name: str = ""             # CLI name, e.g. "chatgpt-export"
    platform: str = ""         # record platform tag, e.g. "chatgpt"
    display_name: str = ""
    entry_kind: str = "file"   # file | qr | localdb | profile
    status: str = "ready"      # ready | beta | planned
    calibration: str = ""      # honesty note: what the parser was verified against

    @abc.abstractmethod
    def auth(self, *, source: str | None = None, **kwargs) -> dict:
        """Resolve the data source. Returns a context dict for pull()."""

    @abc.abstractmethod
    def pull(self, ctx: dict, raw_dir: Path, *, since: str | None = None) -> PullResult:
        """Land raw payloads in raw_dir and report what was landed."""

    @abc.abstractmethod
    def normalize(self, pull: PullResult) -> NormalizeResult:
        """Parse raw payloads into unified records with full counting."""
