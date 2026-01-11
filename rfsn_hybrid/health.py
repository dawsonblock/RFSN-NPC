"""
Health check utilities for monitoring system status.

Provides:
- Component health checks
- Dependency verification
- System diagnostics
"""
from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Status of a health check."""
    name: str
    healthy: bool
    message: str = ""
    latency_ms: float = 0.0
    details: Dict = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health."""
    healthy: bool
    checks: List[HealthStatus]
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            "healthy": self.healthy,
            "timestamp": self.timestamp,
            "checks": [
                {
                    "name": c.name,
                    "healthy": c.healthy,
                    "message": c.message,
                    "latency_ms": round(c.latency_ms, 2),
                    **c.details,
                }
                for c in self.checks
            ],
        }


class HealthChecker:
    """
    Runs health checks on system components.
    
    Example:
        >>> checker = HealthChecker()
        >>> checker.add_check("model", check_model_loaded)
        >>> health = checker.run_all()
        >>> print(health.healthy)
    """
    
    def __init__(self):
        self._checks: Dict[str, Callable[[], HealthStatus]] = {}
        self._add_default_checks()
    
    def _add_default_checks(self) -> None:
        """Add default system checks."""
        self.add_check("python_version", self._check_python_version)
        self.add_check("dependencies", self._check_dependencies)
        self.add_check("disk_space", self._check_disk_space)
    
    def add_check(
        self,
        name: str,
        check_fn: Callable[[], HealthStatus],
    ) -> None:
        """Add a health check."""
        self._checks[name] = check_fn
    
    def run_check(self, name: str) -> HealthStatus:
        """Run a single health check."""
        if name not in self._checks:
            return HealthStatus(
                name=name,
                healthy=False,
                message=f"Unknown check: {name}",
            )
        
        start = time.perf_counter()
        try:
            status = self._checks[name]()
            status.latency_ms = (time.perf_counter() - start) * 1000
            return status
        except Exception as e:
            return HealthStatus(
                name=name,
                healthy=False,
                message=f"Check failed: {str(e)}",
                latency_ms=(time.perf_counter() - start) * 1000,
            )
    
    def run_all(self) -> SystemHealth:
        """Run all health checks."""
        checks = [self.run_check(name) for name in self._checks]
        all_healthy = all(c.healthy for c in checks)
        
        return SystemHealth(
            healthy=all_healthy,
            checks=checks,
            timestamp=datetime.now().isoformat(),
        )
    
    def _check_python_version(self) -> HealthStatus:
        """Check Python version is compatible."""
        version = sys.version_info
        required = (3, 9)
        
        healthy = version >= required
        return HealthStatus(
            name="python_version",
            healthy=healthy,
            message=f"Python {version.major}.{version.minor}.{version.micro}",
            details={
                "version": f"{version.major}.{version.minor}.{version.micro}",
                "required": f"{required[0]}.{required[1]}+",
            },
        )
    
    def _check_dependencies(self) -> HealthStatus:
        """Check required dependencies are installed."""
        missing = []
        optional_missing = []
        
        # Required
        try:
            import llama_cpp
            llama_version = getattr(llama_cpp, "__version__", "unknown")
        except ImportError:
            missing.append("llama-cpp-python")
            llama_version = None
        
        # Optional
        try:
            import faiss
            faiss_available = True
        except ImportError:
            faiss_available = False
            optional_missing.append("faiss-cpu")
        
        try:
            import fastapi
            api_available = True
        except ImportError:
            api_available = False
            optional_missing.append("fastapi")
        
        healthy = len(missing) == 0
        
        return HealthStatus(
            name="dependencies",
            healthy=healthy,
            message="OK" if healthy else f"Missing: {', '.join(missing)}",
            details={
                "llama_cpp": llama_version,
                "faiss_available": faiss_available,
                "api_available": api_available,
                "optional_missing": optional_missing,
            },
        )
    
    def _check_disk_space(self) -> HealthStatus:
        """Check available disk space."""
        import shutil
        
        path = os.getcwd()
        try:
            usage = shutil.disk_usage(path)
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            
            # Warn if less than 1GB free
            healthy = free_gb > 1.0
            
            return HealthStatus(
                name="disk_space",
                healthy=healthy,
                message=f"{free_gb:.1f}GB free of {total_gb:.1f}GB",
                details={
                    "free_gb": round(free_gb, 2),
                    "total_gb": round(total_gb, 2),
                    "percent_used": round(100 * usage.used / usage.total, 1),
                },
            )
        except Exception as e:
            return HealthStatus(
                name="disk_space",
                healthy=True,  # Non-critical
                message=f"Could not check: {e}",
            )


def check_model_health(model_path: str) -> HealthStatus:
    """Check if model file is accessible and valid."""
    if not model_path:
        return HealthStatus(
            name="model",
            healthy=False,
            message="No model path configured",
        )
    
    if not os.path.exists(model_path):
        return HealthStatus(
            name="model",
            healthy=False,
            message=f"Model not found: {model_path}",
        )
    
    size_bytes = os.path.getsize(model_path)
    size_gb = size_bytes / (1024**3)
    
    return HealthStatus(
        name="model",
        healthy=True,
        message=f"Model ready ({size_gb:.2f}GB)",
        details={
            "path": model_path,
            "size_gb": round(size_gb, 2),
        },
    )


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get the global health checker."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def run_health_checks() -> SystemHealth:
    """Run all health checks and return status."""
    return get_health_checker().run_all()
