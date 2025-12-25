import base64
import logging
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from .config import get_config
from .file_manager import FileManager

logger = logging.getLogger(__name__)

app = FastAPI(title="RSPI File Manager", version="1.0.0")

# Configure CORS for LAN access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize file manager
file_manager = FileManager()


def verify_auth(authorization: str = None):
    """Simple Basic Auth verification."""
    config = get_config()
    if not config.get("auth.enabled", False):
        return True
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        scheme, credentials = authorization.split()
        if scheme.lower() != "basic":
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        decoded = base64.b64decode(credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
        
        expected_user = config.get("auth.username", "admin")
        expected_pass = config.get("auth.password", "admin123")
        
        if username != expected_user or password != expected_pass:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        return True
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/", response_class=HTMLResponse)
async def root(authorization: str = None):
    """Serve the main UI."""
    verify_auth(authorization)
    ui_path = Path(__file__).parent / "static" / "index.html"
    if ui_path.exists():
        return ui_path.read_text()
    return "<h1>RSPI File Manager</h1><p>UI not found</p>"


@app.get("/api/config")
async def get_app_config(authorization: str = None):
    """Get UI configuration."""
    verify_auth(authorization)
    config = get_config()
    return {
        "title": config.get("ui.title", "RSPI File Manager"),
        "refreshInterval": config.get("ui.refresh_interval_ms", 2000),
    }


@app.get("/api/browse")
async def browse(path: str = "", authorization: str = None):
    """List directory contents."""
    verify_auth(authorization)
    
    result = file_manager.list_directory(path)
    if result is None:
        raise HTTPException(status_code=404, detail="Path not found or not a directory")
    
    return result


@app.post("/api/upload")
async def upload(
    path: str = Form(""),
    file: UploadFile = File(...),
    authorization: str = None,
):
    """Upload a file to the specified path."""
    verify_auth(authorization)
    
    try:
        file_bytes = await file.read()
        success = file_manager.upload_file(path, file.filename, file_bytes)
        
        if not success:
            raise HTTPException(status_code=400, detail="Upload failed")
        
        return {"message": "File uploaded successfully", "filename": file.filename}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mkdir")
async def mkdir(path: str, name: str, authorization: str = None):
    """Create a new folder."""
    verify_auth(authorization)
    
    if not name:
        raise HTTPException(status_code=400, detail="Folder name is required")
    
    success = file_manager.create_folder(path, name)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to create folder")
    
    return {"message": "Folder created successfully"}


@app.post("/api/rename")
async def rename(path: str, new_name: str, authorization: str = None):
    """Rename a file or folder."""
    verify_auth(authorization)
    
    if not new_name:
        raise HTTPException(status_code=400, detail="New name is required")
    
    success = file_manager.rename_item(path, new_name)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to rename")
    
    return {"message": "Item renamed successfully"}


@app.post("/api/delete")
async def delete(path: str, authorization: str = None):
    """Delete a file or folder."""
    verify_auth(authorization)
    
    success = file_manager.delete_item(path)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete")
    
    return {"message": "Item deleted successfully"}


@app.get("/api/download")
async def download(path: str, authorization: str = None):
    """Download a file."""
    verify_auth(authorization)
    
    file_path = file_manager.get_file_path(path)
    if file_path is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@app.post("/api/eject")
async def eject(path: str, authorization: str = None):
    """Eject/unmount a USB drive."""
    verify_auth(authorization)
    
    import subprocess
    from pathlib import Path
    
    # Get the full mount path
    base_path = Path(file_manager.validator.base_path)
    target_path = (base_path / path).resolve()
    
    # Verify it's within base_path
    try:
        target_path.relative_to(base_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Check if it's a mount point
    result = subprocess.run(
        ["mountpoint", "-q", str(target_path)],
        capture_output=True
    )
    
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail="Not a mount point")
    
    # Unmount via the helper script
    subprocess.run(
        ["/usr/local/bin/usb-mount.sh", "remove", str(target_path)],
        capture_output=True
    )
    
    return {"message": "Drive ejected successfully"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    config = get_config()
    host = config.get("server.host", "0.0.0.0")
    port = config.get("server.port", 8080)
    uvicorn.run(app, host=host, port=port)
