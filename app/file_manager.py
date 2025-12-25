import os
import logging
from pathlib import Path
from typing import List, Dict, Optional
import mimetypes
from .config import get_config

logger = logging.getLogger(__name__)


class PathValidator:
    """Validate and sanitize file paths to prevent directory traversal attacks."""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path).resolve()
        # Ensure base path exists
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def safe_path(self, user_path: str) -> Optional[Path]:
        """
        Convert user-provided path to safe absolute path.
        Returns None if path is outside base_path (directory traversal attempt).
        """
        # Remove leading/trailing slashes and normalize
        user_path = user_path.strip("/").strip("\\")
        
        # Prevent empty or special patterns
        if not user_path or user_path in (".", "..", "~"):
            return self.base_path
        
        # Build target path
        target = (self.base_path / user_path).resolve()
        
        # Ensure target is within base_path
        try:
            target.relative_to(self.base_path)
        except ValueError:
            logger.warning(f"Path traversal attempt: {user_path}")
            return None
        
        return target
    
    def is_safe(self, path: Path) -> bool:
        """Check if path is within base_path."""
        try:
            path.resolve().relative_to(self.base_path)
            return True
        except ValueError:
            return False


class FileManager:
    """Handle file operations: browse, upload, download, mkdir, rename, delete."""
    
    def __init__(self):
        config = get_config()
        base_path = config.get("storage.base_path", "/media/usb")
        self.validator = PathValidator(base_path)
        self.max_upload_mb = config.get("storage.max_upload_mb", 500)
        self.max_files = config.get("storage.max_files_per_dir", 5000)
        self.allowed_extensions = config.get("storage.allowed_extensions", [])
    
    def list_directory(self, user_path: str = "") -> Optional[Dict]:
        """
        List files and folders in a directory.
        Returns dict with 'files', 'folders', 'path', 'parent_path'.
        """
        target = self.validator.safe_path(user_path)
        if target is None:
            return None
        
        if not target.exists():
            logger.warning(f"Path does not exist: {target}")
            return None
        
        if not target.is_dir():
            logger.warning(f"Path is not a directory: {target}")
            return None
        
        try:
            items = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            
            files = []
            folders = []
            count = 0
            
            for item in items:
                if count >= self.max_files:
                    logger.warning(f"Directory {target} exceeds max_files ({self.max_files})")
                    break
                
                try:
                    stat = item.stat()
                    entry = {
                        "name": item.name,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "is_dir": item.is_dir(),
                    }
                    
                    if item.is_dir():
                        entry["type"] = "folder"
                        folders.append(entry)
                    else:
                        entry["type"] = "file"
                        entry["mime"] = mimetypes.guess_type(item.name)[0] or "application/octet-stream"
                        files.append(entry)
                    
                    count += 1
                except OSError as e:
                    logger.warning(f"Could not stat {item}: {e}")
                    continue
            
            # Calculate relative path for display
            relative_path = str(target.relative_to(self.validator.base_path))
            if relative_path == ".":
                relative_path = ""
            
            # Parent path
            parent_path = ""
            if target != self.validator.base_path:
                parent_path = str(target.parent.relative_to(self.validator.base_path))
                if parent_path == ".":
                    parent_path = ""
            
            return {
                "path": relative_path,
                "parent_path": parent_path,
                "folders": folders,
                "files": files,
                "total_items": count,
            }
        
        except PermissionError:
            logger.error(f"Permission denied: {target}")
            return None
        except Exception as e:
            logger.error(f"Error listing directory {target}: {e}")
            return None
    
    def create_folder(self, folder_path: str, folder_name: str) -> bool:
        """Create a new folder. folder_path is relative, folder_name is the new folder name."""
        target = self.validator.safe_path(folder_path)
        if target is None or not target.is_dir():
            return False
        
        # Sanitize folder name
        folder_name = folder_name.strip().replace("/", "_").replace("\\", "_")
        if not folder_name or folder_name in (".", ".."):
            return False
        
        new_folder = target / folder_name
        
        try:
            new_folder.mkdir(exist_ok=False, mode=0o755)
            logger.info(f"Created folder: {new_folder}")
            return True
        except FileExistsError:
            logger.warning(f"Folder already exists: {new_folder}")
            return False
        except Exception as e:
            logger.error(f"Failed to create folder: {e}")
            return False
    
    def rename_item(self, item_path: str, new_name: str) -> bool:
        """Rename a file or folder."""
        target = self.validator.safe_path(item_path)
        if target is None or not target.exists():
            return False
        
        # Sanitize new name
        new_name = new_name.strip().replace("/", "_").replace("\\", "_")
        if not new_name or new_name in (".", ".."):
            return False
        
        new_path = target.parent / new_name
        
        try:
            target.rename(new_path)
            logger.info(f"Renamed {target} to {new_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to rename: {e}")
            return False
    
    def delete_item(self, item_path: str) -> bool:
        """Delete a file or (recursively) a folder."""
        target = self.validator.safe_path(item_path)
        if target is None or not target.exists():
            return False
        
        try:
            if target.is_file():
                target.unlink()
                logger.info(f"Deleted file: {target}")
            elif target.is_dir():
                import shutil
                shutil.rmtree(target)
                logger.info(f"Deleted folder: {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {target}: {e}")
            return False
    
    def get_file_path(self, file_path: str) -> Optional[Path]:
        """
        Get safe absolute path for a file (for download).
        """
        target = self.validator.safe_path(file_path)
        if target is None or not target.is_file():
            return None
        return target
    
    def upload_file(self, folder_path: str, file_name: str, file_bytes: bytes) -> bool:
        """
        Upload file to folder_path with given file_name.
        """
        target_folder = self.validator.safe_path(folder_path)
        if target_folder is None or not target_folder.is_dir():
            return False
        
        # Sanitize file name
        file_name = file_name.strip().replace("/", "_").replace("\\", "_")
        if not file_name:
            return False
        
        # Check extension if whitelist is set
        if self.allowed_extensions:
            ext = Path(file_name).suffix.lstrip(".").lower()
            if ext not in self.allowed_extensions:
                logger.warning(f"File extension not allowed: {ext}")
                return False
        
        # Check file size
        if len(file_bytes) > self.max_upload_mb * 1024 * 1024:
            logger.warning(f"File too large: {len(file_bytes)} bytes")
            return False
        
        file_path = target_folder / file_name
        
        try:
            file_path.write_bytes(file_bytes)
            logger.info(f"Uploaded file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return False
