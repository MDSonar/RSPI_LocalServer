# AI Agent Instructions for RSPI LocalServer

## Project Overview

**RSPI LocalServer** is a lightweight, LAN-only web file manager for Raspberry Pi 4B (1GB RAM) with minimal dependencies. Single FastAPI service with vanilla frontend; no database or multi-user complexity.

### Core Architecture: Modular Monolith

```
FastAPI Routes (main.py) → FileManager (file_manager.py) → PathValidator + Config
```

- **No state persistence** – all operations are immediate filesystem I/O
- **Singleton pattern** – `Config` class lazy-loads YAML config once, cached for performance
- **Single worker** – Gunicorn + UvicornWorker; set `workers: 1` in config to preserve 1GB RAM

## Critical Modules & Key Patterns

### `config.py` – Singleton Config Loader

**Pattern:** Lazy singleton with multi-location search.

**Key behavior:**
- Searches in order: `./config/config.yaml` (dev) → `/etc/rspi-localserver/config.yaml` (prod) → `~/.rspi-localserver/config.yaml` (override)
- Falls back to hardcoded defaults if none found
- Use `get_config().get("key.subkey", default)` for dot-notation access

**Example:** `max_mb = get_config().get("storage.max_upload_mb", 500)`

### `file_manager.py` – Path Safety & File Operations

**Two classes:**

1. **`PathValidator`** – Prevents directory traversal attacks
   - Constructor: `PathValidator(base_path)` where base_path is typically `/media/usb`
   - Method: `safe_path(user_path)` → returns `Path` or `None` if outside base_path
   - Algorithm: Normalize user input, resolve absolute path, validate with `.relative_to(base_path)`
   - **Critical:** Always validate user paths via `safe_path()` before any filesystem operation

2. **`FileManager`** – Core operations (browse, upload, mkdir, rename, delete)
   - Initializes with config-driven settings: `max_upload_mb`, `max_files`, `allowed_extensions`
   - Methods return `Optional[Dict]` or `bool`; `None`/`False` signals error (logged, never raises)
   - **Upload safety:** Checks file size, extension whitelist (if configured), writes atomically
   - **Folder operations:** Sanitize names (remove `/`, `\`), check existence before modify

### `main.py` – FastAPI Routes & Auth

**Middleware:**
- CORS open for LAN (`allow_origins=["*"]`)
- Static files auto-served from `/app/static/`

**All API endpoints require optional auth:**
- Dependency: `verify_auth(authorization: str = None)` checks `config.auth.enabled`
- If enabled and invalid → `HTTPException(401)`
- Basic Auth format: `Authorization: Basic base64(username:password)`

**Key endpoints:**
- `GET /api/browse?path=subfolder` → Returns `{path, parent_path, folders: [...], files: [...]}`
- `POST /api/upload` → Form: `path`, `file` (multipart); size/extension validated in FileManager
- `POST /api/mkdir`, `/api/rename`, `/api/delete` → All use FileManager methods

## Developer Workflows

### Run Locally (Development)

```bash
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Deploy to Raspberry Pi

```bash
# On Pi
cd ~/RSPI_LocalServer
./install.sh
# Creates systemd service, installs to /etc/rspi-localserver/, runs as unprivileged `rspi` user

# Restart service after config changes
sudo systemctl restart rspi-localserver

# View logs
sudo journalctl -u rspi-localserver -f
```

### Update & Rollback

```bash
./update.sh  # Backup current version, pull new code, restart
./uninstall.sh  # Safe remove (keeps logs + config for re-deploy)
```

## Project-Specific Patterns & Conventions

### Error Handling Philosophy

- **FileManager methods return `Optional` results** – `None` or `False` for errors; always logged, never raised
- **API endpoints catch and return HTTP exceptions** – 400 (bad input), 401 (auth), 404 (not found), 500 (unexpected)
- **Fail gracefully** – Permission denied, missing path, etc. are logged and reported to UI, not crashes

### Path Handling

- **User-provided paths are always relative** – e.g., `"subfolder/file.txt"`
- **Validated via `PathValidator.safe_path()`** – prevents `../../../../etc/passwd` attacks
- **Absolute paths resolved once** – use `target.relative_to(base_path)` for display
- **Storage root is `/media/usb/`** – subdirs auto-detected as separate drives; no restart needed on plug/unplug

### Configuration Overrides

- **Development:** `./config/config.yaml` checked first
- **Production:** `/etc/rspi-localserver/config.yaml` installed by `install.sh`
- **User override:** `~/.rspi-localserver/config.yaml` takes precedence
- **Add new settings** to `Config._default_config()` as fallback; reference via `get_config().get("section.key", default)`

### Frontend Integration

- **Single-file HTML UI:** `app/static/index.html` (no build step, vanilla JS)
- **API base:** `/api/*` endpoints return JSON; UI polls `/api/browse` with auto-refresh interval from config
- **UI config:** `/api/config` provides dynamic settings (title, refresh interval)

## Dependency & Integration Notes

- **FastAPI** 0.104.1 – async framework, auto-docs at `/docs`
- **Gunicorn + Uvicorn** – production WSGI/ASGI, systemd-managed
- **PyYAML** 6.0.1 – config loading
- **Python 3.9+** – type hints, pathlib, async/await
- **No database** – filesystem is source of truth
- **LAN-only by default** – `0.0.0.0` on port 8080; use Basic Auth if internet-exposed

## Quick Troubleshooting Checklist

- **"Path not found"** → Check `base_path` in config, verify mount at `/media/usb`
- **Auth not working** → Ensure `auth.enabled: true` in config, use proper Basic Auth header
- **Upload fails** → Check `max_upload_mb`, `allowed_extensions` in config
- **Slow directory listing** → May hit `max_files_per_dir` limit (5000 default)
- **Permission denied on upload/delete** → File manager runs as `rspi` user; check `/media/usb` permissions
