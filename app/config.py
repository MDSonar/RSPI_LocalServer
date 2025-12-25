import os
import sys
import logging
from pathlib import Path
from typing import Optional
import yaml
from functools import lru_cache

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Config:
    """Load and cache configuration from YAML."""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load(self, config_path: Optional[str] = None):
        if self._config is not None:
            return self._config
        
        if config_path is None:
            # Look for config in common locations
            possible_paths = [
                Path(__file__).parent.parent / "config" / "config.yaml",
                Path("/etc/rspi-localserver/config.yaml"),
                Path.home() / ".rspi-localserver" / "config.yaml",
            ]
            for p in possible_paths:
                if p.exists():
                    config_path = p
                    break
            
            if config_path is None:
                logger.warning("No config found; using defaults")
                self._config = self._default_config()
                return self._config
        
        try:
            with open(config_path, "r") as f:
                self._config = yaml.safe_load(f)
                logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._config = self._default_config()
        
        return self._config
    
    @staticmethod
    def _default_config():
        return {
            "server": {
                "host": "0.0.0.0",
                "port": 8080,
                "workers": 1,
                "worker_class": "uvicorn.workers.UvicornWorker",
                "timeout": 30,
                "keepalive": 5,
            },
            "storage": {
                "base_path": "/media/usb",
                "max_upload_mb": 500,
                "max_files_per_dir": 5000,
                "allowed_extensions": [],
            },
            "auth": {
                "enabled": False,
                "username": "admin",
                "password": "admin123",
            },
            "ui": {
                "title": "RSPI File Manager",
                "refresh_interval_ms": 2000,
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        }
    
    def get(self, key: str, default=None):
        if self._config is None:
            self.load()
        keys = key.split(".")
        val = self._config
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default


@lru_cache(maxsize=1)
def get_config() -> Config:
    config = Config()
    config.load()
    return config
