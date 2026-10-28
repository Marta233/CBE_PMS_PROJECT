"""
upload_guard.py - everything that must be true about an uploaded file BEFORE
any parser touches it.

    data = await read_capped(file, max_bytes)      # size limit, streamed
    check_signature(".xlsx", data)                 # real type == extension
    check_archive_safety(".xlsx", data)            # zip bombs, macros, path tricks
    digest = sha256_hex(data)                      # for traceability / duplicate warning
    scan = scan_bytes(data)                        # ClamAV (INSTREAM), no extra package

Settings (environment variables):
    PMS_MAX_UPLOAD_MB   default 20
    PMS_VIRUS_SCAN      required | optional | off      default optional
                          required : scanner unreachable  -> upload refused (503)
                          optional : scanner unreachable  -> accepted, logged "unscanned"
                          off      : no scan (development)
    PMS_CLAMAV_HOST     default 127.0.0.1
    PMS_CLAMAV_PORT     default 3310
    PMS_CLAMAV_TIMEOUT  default 30   (seconds)
"""
from __future__ import annotations

import hashlib
import os
import socket
import struct
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

CHUNK = 1024 * 1024  # 1 MiB

ZIP_TYPES = {".xlsx", ".docx"}
OLE_TYPES = {".xls", ".doc"}
TEXT_TYPES = {".csv", ".txt"}
OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")

MAX_ZIP_ENTRIES = 5000
MAX_UNCOMPRESSED_BYTES = 300 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


class UploadRejected(Exception):
    """Raised for any reason an upload must be refused. status_code is HTTP."""

    def __init__(self, status_code: int, message: str, kind: str = "rejected"):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.kind = kind


# ------------------------------------------------------------------ settings
def max_upload_bytes() -> int:
    try:
        mb = float(os.getenv("PMS_MAX_UPLOAD_MB", "20"))
    except ValueError:
        mb = 20.0
    return int(mb * 1024 * 1024)


def scan_mode() -> str:
    mode = os.getenv("PMS_VIRUS_SCAN", "optional").strip().lower()
    return mode if mode in ("required", "optional", "off") else "optional"


# ------------------------------------------------------------------ size cap
async def read_capped(upload, max_bytes: Optional[int] = None) -> bytes:
    """Read an UploadFile in chunks and stop as soon as the cap is exceeded."""
    cap = max_bytes if max_bytes is not None else max_upload_bytes()
    buf = bytearray()
    while True:
        chunk = await upload.read(CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > cap:
            raise UploadRejected(
                413, f"File is larger than the {cap // (1024 * 1024)} MB limit.", "too_large")
    if not buf:
        raise UploadRejected(422, "The uploaded file is empty.", "empty")
    return bytes(buf)


# ------------------------------------------------------------ type checking
def check_signature(suffix: str, data: bytes) -> None:
    """The first bytes must match what the extension claims."""
    s = suffix.lower()
    if s in ZIP_TYPES:
        ok = data[:4] == b"PK\x03\x04"
    elif s == ".pdf":
        ok = data[:1024].lstrip().startswith(b"%PDF")
    elif s in OLE_TYPES:
        ok = data[:8] == OLE_MAGIC
    elif s in TEXT_TYPES:
        ok = b"\x00" not in data[:4096]
    else:
        ok = False
    if not ok:
        raise UploadRejected(
            415, f"The content of this file does not match its '{s}' extension.", "bad_signature")


def check_archive_safety(suffix: str, data: bytes) -> None:
    """xlsx/docx are zip files: refuse macros, zip bombs and path tricks."""
    if suffix.lower() not in ZIP_TYPES:
        return
    try:
        zf = zipfile.ZipFile(BytesIO(data))
        infos = zf.infolist()
    except zipfile.BadZipFile:
        raise UploadRejected(415, "The file is not a valid Office document (corrupt zip).", "bad_zip")

    if len(infos) > MAX_ZIP_ENTRIES:
        raise UploadRejected(422, "The document contains too many internal parts.", "zip_bomb")

    total = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/"):
            raise UploadRejected(422, "The document contains an unsafe internal path.", "unsafe_path")
        if name.lower().endswith("vbaproject.bin"):
            raise UploadRejected(422, "Documents with macros are not accepted.", "macro")
        total += info.file_size
        if info.compress_size and info.file_size / max(info.compress_size, 1) > MAX_COMPRESSION_RATIO \
                and info.file_size > 10 * 1024 * 1024:
            raise UploadRejected(422, "The document looks like a decompression bomb.", "zip_bomb")
    if total > MAX_UNCOMPRESSED_BYTES:
        raise UploadRejected(422, "The document expands to an unreasonable size.", "zip_bomb")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------- virus scan
@dataclass
class ScanResult:
    status: str        # clean | infected | unscanned | error
    detail: str = ""


def _clamd_instream(data: bytes, host: str, port: int, timeout: float) -> str:
    """Talk the clamd INSTREAM protocol directly - no third-party package needed."""
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall(b"zINSTREAM\0")
        for i in range(0, len(data), CHUNK):
            part = data[i:i + CHUNK]
            s.sendall(struct.pack("!L", len(part)) + part)
        s.sendall(struct.pack("!L", 0))
        resp = b""
        while True:
            piece = s.recv(4096)
            if not piece:
                break
            resp += piece
            if resp.endswith(b"\0") or resp.endswith(b"\n"):
                break
    return resp.strip(b"\0\n ").decode("utf-8", "replace")


def scan_bytes(data: bytes) -> ScanResult:
    """
    Scan with ClamAV. Never raises: the caller decides what to do from
    (status, scan_mode()). 'infected' must always block.
    """
    mode = scan_mode()
    if mode == "off":
        return ScanResult("unscanned", "virus scan disabled (PMS_VIRUS_SCAN=off)")
    host = os.getenv("PMS_CLAMAV_HOST", "127.0.0.1")
    try:
        port = int(os.getenv("PMS_CLAMAV_PORT", "3310"))
        timeout = float(os.getenv("PMS_CLAMAV_TIMEOUT", "30"))
    except ValueError:
        port, timeout = 3310, 30.0
    try:
        reply = _clamd_instream(data, host, port, timeout)
    except Exception as exc:  # unreachable, timeout, protocol error
        return ScanResult("error", f"scanner unreachable at {host}:{port} ({exc})")
    if reply.endswith("OK"):
        return ScanResult("clean", reply)
    if "FOUND" in reply:
        return ScanResult("infected", reply)
    return ScanResult("error", f"unexpected scanner reply: {reply!r}")


def enforce_scan(result: ScanResult) -> None:
    """Apply the policy. Raises UploadRejected when the upload must stop."""
    if result.status == "infected":
        raise UploadRejected(422, f"Virus detected - upload blocked ({result.detail}).", "infected")
    if result.status == "error" and scan_mode() == "required":
        raise UploadRejected(
            503, "Virus scanner is unavailable and scanning is required. Try again later.",
            "scanner_down")