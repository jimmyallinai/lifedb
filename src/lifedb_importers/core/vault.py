"""Credential vault: ~/.lifedb/creds/<platform>.json

- directory mode 0700, files mode 0600, both set explicitly via os.open /
  os.chmod (never rely on umask).
- stores ONLY session material an importer needs (e.g. session cookies for
  QR-login importers). Passwords are never stored, never handled: users type
  passwords only on the platform's own pages (see docs/safety position in
  README / A1 feasibility裁决).
- log redaction: values of sensitive keys are masked before anything is
  printed.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

SENSITIVE_KEYS = (
    "SESSDATA", "bili_jct", "dbcl2", "uamtk", "pt_key", "pt_pin",
    "sessionid", "sid_tt", "session", "cookie", "token", "password",
)

_MASK_PATTERNS = [
    re.compile(rf"({re.escape(key)}\s*[=:]\s*)[^\s;,&\"']+", re.IGNORECASE)
    for key in SENSITIVE_KEYS
]


def redact(text: str) -> str:
    out = text
    for pattern in _MASK_PATTERNS:
        out = pattern.sub(r"\1***", out)
    return out


def vault_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".lifedb" / "creds"


def ensure_vault(home: Path | None = None) -> Path:
    path = vault_dir(home)
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    os.chmod(path, 0o700)
    return path


def save_credential(platform: str, data: dict, home: Path | None = None) -> Path:
    directory = ensure_vault(home)
    target = directory / f"{platform}.json"
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    os.chmod(target, 0o600)
    return target


def load_credential(platform: str, home: Path | None = None) -> dict | None:
    target = vault_dir(home) / f"{platform}.json"
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))
