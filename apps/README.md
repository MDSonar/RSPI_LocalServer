# RSPI LocalServer Apps Structure

## Directory Layout

```
apps/
├── core/                   # Core apps (always installed)
│   ├── systeminfo/
│   │   ├── manifest.json
│   │   └── systeminfo.html
│   └── taskmanager/
│       ├── manifest.json
│       └── taskmanager.html
└── optional/               # Optional apps (on-demand installation)
   ├── filemanager/
   │   ├── manifest.json
   │   ├── filemanager.html
   │   └── file_manager.py
   └── videoplayer/
      ├── manifest.json
      └── videoplayer.html
```

## Installation Flow

### Initial Setup (git clone)
When users run `git clone` and `sudo ./install.sh`:
- Only **dashboard** and **core apps** (systeminfo, taskmanager) are copied to `/opt/rspi-localserver/`
- File Manager, Video Player, and other optional apps remain in the GitHub repo
- Disk usage: ~5-10MB (vs 50-100MB+ with all apps)

### On-Demand Installation
When user clicks "Install" on an optional app:
1. Frontend calls `/api/apps/install` with app_id
2. Backend downloads files from GitHub using direct URL fetch:
   - `apps/optional/{app_id}/manifest.json`
   - Each file listed in manifest
3. Files saved to `/opt/rspi-localserver/apps/optional/{app_id}/`
4. App marked as installed in `apps_state.json`
5. User can immediately launch the app

### App Manifest Format

```json
{
  "name": "App Display Name",
  "version": "1.0.0",
  "description": "Short description",
  "files": [
    "app.html",
    "app_module.py"
  ],
  "dependencies": ["psutil", "other-package"],
  "route": "/apps/appname"
}
```

## Creating New Apps

1. **Create app directory:**
   ```bash
   mkdir -p apps/optional/myapp
   ```

2. **Add manifest.json:**
   ```json
   {
     "name": "My App",
     "version": "1.0.0",
     "description": "What it does",
     "files": ["myapp.html"],
     "dependencies": [],
     "route": "/apps/myapp"
   }
   ```

3. **Create HTML file(s)** with UI

4. **Add route in main.py:**
   ```python
   @app.get("/apps/myapp", response_class=HTMLResponse)
   async def myapp_app(authorization: str = None):
       verify_auth(authorization)
       for category in ["core", "optional"]:
           ui_path = APPS_DIR / category / "myapp" / "myapp.html"
           if ui_path.exists():
               return ui_path.read_text()
       return "<h1>My App</h1><p>Not installed</p>"
   ```

5. **Update dashboard.html** to add tile

6. **Commit to GitHub** - app auto-downloadable on install

## GitHub Configuration

Update `GITHUB_RAW_BASE` in `main.py`:
```python
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/YOUR_USERNAME/RSPI_LocalServer/main/apps"
```

Replace `YOUR_USERNAME` with your GitHub username.

## Benefits

- **Minimal clone size**: Only core system + dashboard
- **Faster installs**: No downloading unused apps
- **Modular architecture**: Easy to add/remove apps
- **Bandwidth efficient**: Only download what's needed
- **Storage friendly**: Perfect for Pi with limited SD card space


git clone --no-checkout https://github.com/MDSonar/RSPI_LocalServer.git
cd RSPI_LocalServer
git sparse-checkout init --cone
git sparse-checkout set app apps/core apps/README.md install.sh requirements.txt
git checkout main
sudo ./install.sh