"""
Admin endpoints for importing nginx access logs into Higashi Analytics.

POST /api/admin/import/upload        — multipart file upload
POST /api/admin/import/ssh/discover  — auto-find log files on a remote server
POST /api/admin/import/ssh           — pull + import a specific log file
GET/POST/DELETE /api/admin/import/profiles — saved pull targets (secrets stay server-side)
"""

import json
import os
import shlex
import stat
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from typing import Optional

from config import get_settings
from database import AsyncSessionLocal
from models.import_cursor import ImportCursor
from models.pull_profile import PullProfile
from models.site import Site
from routers.auth import require_admin
from services.log_importer import import_log_file
from services import secret_box

router = APIRouter()
settings = get_settings()

KNOWN_SERVERS = []
if settings.sftp_host:
    KNOWN_SERVERS = [
        {
            "label": "stevenhigashi.com",
            "host": settings.sftp_host,
            "port": settings.sftp_port,
            "username": settings.sftp_user_stevenhigashi,
            "password": settings.sftp_password_stevenhigashi,
            "domain": "stevenhigashi.com",
            # Paths as configured on the cloudanalyst install; blank means
            # manual import only, and _sync_loop skips the entry.
            "log_path": "/home/example.hosting.invalid/site-one/logs/access.log",
        },
        {
            "label": "cloudanalyst.net",
            "host": settings.sftp_host,
            "port": settings.sftp_port,
            "username": settings.sftp_user_cloudanalyst,
            "password": settings.sftp_password,
            "domain": "cloudanalyst.net",
            "log_path": "/home/example.hosting.invalid/site-two/logs/access.log",
        },
    ]


async def _import_with_optional_detection(**kwargs) -> dict:
    """Compose core import with the removable, after-the-fact analysis layer."""
    rows: list[dict] = []
    try:
        from services.walk_detection import analyze_windows
        from routers.walk_detection import persist_detection_results
    except ImportError:
        analyze_windows = persist_detection_results = None

    result = await import_log_file(
        **kwargs,
        request_observer=rows.append if analyze_windows else None,
    )
    if not analyze_windows or not persist_detection_results:
        return result

    try:
        detections = analyze_windows(rows)
        stored = await persist_detection_results(
            settings.database_url,
            uuid.UUID(result["site_id"]),
            detections,
        )
        result["walk_detection"] = {
            "windows_analyzed": stored,
            "walk_windows": sum(item.verdict == "walk_detected" for item in detections),
            "suspicious_windows": sum(item.verdict == "suspicious" for item in detections),
            "max_score": max((item.score for item in detections), default=0),
        }
    except Exception as exc:
        # Analysis is diagnostic and must never turn a valid log import into a
        # failed ingestion. Surface the local error without sending telemetry.
        result["walk_detection"] = {"error": str(exc)}
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _friendly_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if any(k in msg for k in (
        "authentication failed", "permission denied", "publickey",
        "bad password", "invalid password", "login incorrect", "no matching",
    )):
        return "These credentials don't work — double-check your username and password."
    if "connection refused" in msg:
        return "Connection refused — check the host address and port number."
    if any(k in msg for k in ("no address", "name or service not known", "nodename", "getaddrinfo")):
        return "Host not found — check the server address for typos."
    if any(k in msg for k in ("timed out", "timeout")):
        return "Connection timed out — the server didn't respond."
    if "no such file" in msg:
        return "File not found at that path."
    return str(exc)


def _build_connect_kwargs(
    host: str, port: int, username: str,
    password: Optional[str], private_key: Optional[str],
) -> tuple[dict, Optional[str]]:
    kwargs: dict = {"host": host, "port": port, "username": username, "known_hosts": None}
    key_path = None
    if private_key:
        fd, key_path = tempfile.mkstemp(suffix=".pem")
        try:
            os.write(fd, private_key.encode())
        finally:
            os.close(fd)
        os.chmod(key_path, stat.S_IRUSR | stat.S_IWUSR)
        kwargs["client_keys"] = [key_path]
    elif password:
        kwargs["password"] = password
    else:
        raise HTTPException(status_code=422, detail="Provide either a password or a private key.")
    return kwargs, key_path


# Find active and rotated logs. Rotated forms vary by distro:
#   access.log, access.log.1, access.log.2.gz, access.log-20260514.gz, etc.
_DISCOVER_CMD = (
    "find /logs /var/log/nginx /var/log/apache2 /home "
    r"-maxdepth 7 \( -name 'access.log*' -o -name '*.access.log*' \) "
    "-readable 2>/dev/null | sort | head -200"
)


def _is_log_name(name: str) -> bool:
    return "access.log" in name and not name.endswith((".bak", ".tmp"))


async def _discover_via_ssh(conn) -> list[str]:
    async with conn.create_process(_DISCOVER_CMD, encoding="utf-8") as process:
        stdout, _ = await process.communicate()
    paths = [p.strip() for p in (stdout or "").splitlines() if p.strip()]
    # Dedupe while preserving order
    seen = set()
    out = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


async def _discover_via_sftp(conn) -> list[str]:
    paths = []
    async with conn.start_sftp_client() as sftp:
        for d in ("/logs", "/var/log/nginx", "/var/log/apache2"):
            try:
                for name in sorted(await sftp.listdir(d)):
                    if _is_log_name(name):
                        paths.append(f"{d}/{name}")
            except Exception:
                continue
    return paths


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SSHCredentials(BaseModel):
    host: Optional[str] = None
    port: int = 22
    username: Optional[str] = None
    password: Optional[str] = None
    private_key: Optional[str] = None
    profile_id: Optional[str] = None


class PullProfileRequest(BaseModel):
    label: str
    host: str
    port: int = 22
    username: str
    auth_mode: str = "password"
    password: Optional[str] = None      # blank keeps the stored secret
    private_key: Optional[str] = None
    domain: Optional[str] = None
    log_paths: list[str] = []


def _profile_public(p: PullProfile) -> dict:
    return {
        "id": p.id, "label": p.label, "host": p.host, "port": p.port,
        "username": p.username, "auth_mode": p.auth_mode, "domain": p.domain or "",
        "log_paths": json.loads(p.log_paths or "[]"), "has_secret": bool(p.secret_enc),
    }


async def _resolve_credentials(body: SSHCredentials) -> tuple[str, int, str, Optional[str], Optional[str]]:
    """Return host, port, username, password, private_key for a pull.

    A saved profile pins its own host: a stored secret is only ever sent to the
    server it was saved for. The env fallback password is likewise only used
    against the env-configured host.
    """
    if body.profile_id:
        async with AsyncSessionLocal() as db:
            p = await db.get(PullProfile, body.profile_id)
        if not p:
            raise HTTPException(status_code=404, detail="Saved profile not found.")
        password = body.password if p.auth_mode == "password" else None
        private_key = body.private_key if p.auth_mode == "key" else None
        if not (password or private_key) and p.secret_enc:
            try:
                secret = secret_box.decrypt(p.secret_enc)
            except Exception:
                raise HTTPException(status_code=409, detail="The saved login can't be read any more — enter it again and re-save the profile.")
            if p.auth_mode == "key":
                private_key = secret
            else:
                password = secret
        return p.host, p.port, p.username, password, private_key

    host = body.host or settings.sftp_host
    username = body.username or ""
    password = body.password
    if not password and not body.private_key and settings.sftp_host and host == settings.sftp_host:
        password = settings.sftp_password
    return host, body.port, username, password, body.private_key


class SSHImportRequest(SSHCredentials):
    log_path: str
    domain: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/cursors")
async def list_cursors(_=Depends(require_admin)):
    """Return all import cursors so the UI can show last-imported timestamps."""
    from sqlalchemy import select as sa_select
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(sa_select(ImportCursor))).scalars().all()
        # Attach site domain for each cursor
        site_ids = {str(r.site_id) for r in rows if r.site_id}
        site_uuid_ids = []
        for site_id in site_ids:
            try:
                site_uuid_ids.append(uuid.UUID(site_id))
            except ValueError:
                continue
        sites = {}
        if site_uuid_ids:
            site_rows = (await db.execute(
                sa_select(Site).where(Site.id.in_(site_uuid_ids))
            )).scalars().all()
            sites = {str(s.id): s.domain for s in site_rows}
    return [
        {
            "log_path":       r.log_path,
            "site_domain":    sites.get(str(r.site_id), r.site_id),
            "last_line_at":   r.last_line_at.isoformat() if r.last_line_at else None,
            "last_run_at":    r.last_run_at.isoformat()  if r.last_run_at  else None,
            "total_imported": r.total_imported,
        }
        for r in rows
    ]


@router.get("/profiles")
async def list_profiles(_=Depends(require_admin)):
    from sqlalchemy import select as sa_select
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(sa_select(PullProfile).order_by(PullProfile.label))).scalars().all()
    return [_profile_public(p) for p in rows]


@router.post("/profiles")
async def save_profile(body: PullProfileRequest, _=Depends(require_admin)):
    from sqlalchemy import select as sa_select
    label = body.label.strip()[:120]
    if not label or not body.host.strip() or not body.username.strip():
        raise HTTPException(status_code=422, detail="Label, host and username are required.")
    if body.auth_mode not in ("password", "key"):
        raise HTTPException(status_code=422, detail="auth_mode must be 'password' or 'key'.")
    secret = (body.password if body.auth_mode == "password" else body.private_key) or ""

    async with AsyncSessionLocal() as db:
        p = (await db.execute(sa_select(PullProfile).where(PullProfile.label == label))).scalar_one_or_none()
        if p is None:
            p = PullProfile(label=label)
            db.add(p)
        target_changed = (p.host, p.port, p.username, p.auth_mode) != (body.host.strip(), body.port, body.username.strip(), body.auth_mode)
        p.host, p.port, p.username, p.auth_mode = body.host.strip(), body.port, body.username.strip(), body.auth_mode
        p.domain = (body.domain or "").strip()
        p.log_paths = json.dumps([x for x in body.log_paths if isinstance(x, str)][:50])
        if secret.strip():
            p.secret_enc = secret_box.encrypt(secret)
        elif target_changed:
            # Never carry a stored secret over to a different server or account.
            p.secret_enc = None
        await db.commit()
        await db.refresh(p)
        return _profile_public(p)


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str, _=Depends(require_admin)):
    async with AsyncSessionLocal() as db:
        p = await db.get(PullProfile, profile_id)
        if p:
            await db.delete(p)
            await db.commit()
    return {"ok": True}


@router.get("/servers")
async def list_servers(_=Depends(require_admin)):
    return [
        {"label": s["label"], "host": s["host"], "port": s["port"],
         "username": s["username"], "domain": s["domain"], "log_path": s["log_path"]}
        for s in KNOWN_SERVERS
    ]


@router.post("/upload")
async def import_upload(
    file: UploadFile = File(...),
    domain: str = Form(...),
    _=Depends(require_admin),
):
    suffix = os.path.splitext(file.filename or ".log")[1] or ".log"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
        content = await file.read()
        tmp.write(content)

    try:
        result = await _import_with_optional_detection(
            filepath=tmp_path, domain=domain, db_url=settings.database_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return result


@router.post("/ssh/discover")
async def import_ssh_discover(body: SSHCredentials, _=Depends(require_admin)):
    """Connect and auto-discover nginx access logs. Tries SSH exec, falls back to SFTP."""
    try:
        import asyncssh as _asyncssh
    except ImportError:
        raise HTTPException(status_code=503, detail="asyncssh not installed.")

    host, port, username, password, private_key = await _resolve_credentials(body)

    if not host or not username:
        raise HTTPException(status_code=422, detail="Host and username are required.")

    connect_kwargs, key_path = _build_connect_kwargs(host, port, username, password, private_key)

    try:
        async with _asyncssh.connect(**connect_kwargs) as conn:
            paths = await _discover_via_ssh(conn)
            method = "ssh"
            if not paths:
                paths = await _discover_via_sftp(conn)
                method = "sftp"
            return {
                "method": method,
                "logs": [{"path": p, "name": p.split("/")[-1]} for p in paths],
            }
    except _asyncssh.Error as exc:
        raise HTTPException(status_code=502, detail=_friendly_error(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_friendly_error(exc))
    finally:
        if key_path:
            try:
                os.unlink(key_path)
            except OSError:
                pass


@router.post("/ssh")
async def import_ssh(body: SSHImportRequest, _=Depends(require_admin)):
    """SFTP-pull a specific log file and import it."""
    try:
        import asyncssh as _asyncssh
    except ImportError:
        raise HTTPException(status_code=503, detail="asyncssh not installed.")

    host, port, username, password, private_key = await _resolve_credentials(body)

    if not host or not username:
        raise HTTPException(status_code=422, detail="Host and username are required.")

    connect_kwargs, key_path = _build_connect_kwargs(host, port, username, password, private_key)

    tmp_path: Optional[str] = None
    try:
        async with _asyncssh.connect(**connect_kwargs) as conn:
            # Preserve .gz suffix so the importer can detect rotated/compressed
            # logs and use gzip.open transparently.
            suffix = ".log.gz" if body.log_path.endswith(".gz") else ".log"
            fd2, tmp_path = tempfile.mkstemp(suffix=suffix)
            os.close(fd2)
            fetched = False

            # Try SFTP first (works when not chrooted)
            try:
                async with conn.start_sftp_client() as sftp:
                    await sftp.get(body.log_path, tmp_path)
                fetched = True
            except Exception:
                pass

            # Fall back to SSH exec cat (works on chrooted servers like Cloudways)
            if not fetched:
                async with conn.create_process(
                    f"cat {shlex.quote(body.log_path)}", encoding=None
                ) as proc:
                    stdout, stderr = await proc.communicate()
                if proc.exit_status != 0:
                    detail = (stderr or b"").decode(errors="replace").strip()
                    if not detail:
                        detail = f"cat exited with code {proc.exit_status}"
                    raise HTTPException(
                        status_code=502,
                        detail=f"SSH read failed: {detail}",
                    )
                with open(tmp_path, "wb") as f:
                    f.write(stdout or b"")

        result = await _import_with_optional_detection(
            filepath=tmp_path, domain=body.domain, db_url=settings.database_url,
            log_path=body.log_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except _asyncssh.Error as exc:
        raise HTTPException(status_code=502, detail=_friendly_error(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_friendly_error(exc))
    finally:
        if key_path:
            try:
                os.unlink(key_path)
            except OSError:
                pass
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return result
