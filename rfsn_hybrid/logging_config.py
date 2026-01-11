"""
Structured logging configuration.

Emits both human-readable and JSON logs for debugging.
JSON logs include:
- Timestamp
- Level
- Subsystem
- Conversation ID
- NPC ID
- Sequence number
- Event type
- Latency metrics
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional


class StructuredLogRecord(logging.LogRecord):
    """Extended log record with structured fields."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.convo_id: Optional[str] = None
        self.npc_id: Optional[str] = None
        self.seq: Optional[int] = None
        self.subsystem: str = "general"
        self.event_type: Optional[str] = None
        self.latency_ms: Optional[float] = None
        self.extra_data: Dict[str, Any] = {}


class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add structured fields if present
        if hasattr(record, "subsystem"):
            log_data["subsystem"] = record.subsystem
        if hasattr(record, "convo_id") and record.convo_id:
            log_data["convo_id"] = record.convo_id
        if hasattr(record, "npc_id") and record.npc_id:
            log_data["npc_id"] = record.npc_id
        if hasattr(record, "seq") and record.seq is not None:
            log_data["seq"] = record.seq
        if hasattr(record, "event_type") and record.event_type:
            log_data["event"] = record.event_type
        if hasattr(record, "latency_ms") and record.latency_ms is not None:
            log_data["latency_ms"] = record.latency_ms
        if hasattr(record, "extra_data") and record.extra_data:
            log_data.update(record.extra_data)
        
        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


class HumanFormatter(logging.Formatter):
    """Human-readable format with colors."""
    
    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"
    
    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        level = record.levelname[:4]
        
        # Build prefix with structured data
        prefix_parts = [f"{timestamp} {level}"]
        
        if hasattr(record, "subsystem") and record.subsystem != "general":
            prefix_parts.append(f"[{record.subsystem}]")
        if hasattr(record, "npc_id") and record.npc_id:
            prefix_parts.append(f"npc={record.npc_id}")
        if hasattr(record, "convo_id") and record.convo_id:
            prefix_parts.append(f"convo={record.convo_id[:8]}")
        
        prefix = " ".join(prefix_parts)
        message = record.getMessage()
        
        # Add latency if present
        if hasattr(record, "latency_ms") and record.latency_ms is not None:
            message = f"{message} ({record.latency_ms:.1f}ms)"
        
        line = f"{prefix}: {message}"
        
        if self.use_colors and sys.stderr.isatty():
            color = self.COLORS.get(record.levelname, "")
            line = f"{color}{line}{self.RESET}"
        
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        
        return line


class StructuredLogger(logging.Logger):
    """Logger with structured logging methods."""
    
    def __init__(self, name: str, level: int = logging.NOTSET):
        super().__init__(name, level)
    
    def _log_structured(
        self,
        level: int,
        msg: str,
        convo_id: Optional[str] = None,
        npc_id: Optional[str] = None,
        seq: Optional[int] = None,
        subsystem: str = "general",
        event_type: Optional[str] = None,
        latency_ms: Optional[float] = None,
        **extra,
    ) -> None:
        """Log with structured data."""
        record = self.makeRecord(
            self.name, level, "", 0, msg, (), None
        )
        record.convo_id = convo_id
        record.npc_id = npc_id
        record.seq = seq
        record.subsystem = subsystem
        record.event_type = event_type
        record.latency_ms = latency_ms
        record.extra_data = extra
        self.handle(record)
    
    def event(
        self,
        event_type: str,
        msg: str,
        **kwargs,
    ) -> None:
        """Log an event."""
        self._log_structured(
            logging.INFO,
            msg,
            event_type=event_type,
            **kwargs,
        )
    
    def latency(
        self,
        operation: str,
        latency_ms: float,
        **kwargs,
    ) -> None:
        """Log a latency measurement."""
        self._log_structured(
            logging.DEBUG,
            f"{operation} completed",
            latency_ms=latency_ms,
            **kwargs,
        )


def configure_logging(
    level: str = "INFO",
    log_dir: Optional[str] = None,
    json_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files
        json_file: Path for JSON logs (in log_dir if relative)
        max_bytes: Max size per log file
        backup_count: Number of backup files to keep
    """
    # Set custom logger class
    logging.setLoggerClass(StructuredLogger)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Console handler (human-readable)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(HumanFormatter())
    root_logger.addHandler(console)
    
    # File handlers
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        
        # Human-readable log file
        human_path = os.path.join(log_dir, "rfsn.log")
        human_handler = RotatingFileHandler(
            human_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        human_handler.setFormatter(HumanFormatter(use_colors=False))
        root_logger.addHandler(human_handler)
        
        # JSON log file
        json_path = json_file or os.path.join(log_dir, "rfsn.json.log")
        if not os.path.isabs(json_path):
            json_path = os.path.join(log_dir, json_path)
        
        json_handler = RotatingFileHandler(
            json_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger."""
    return logging.getLogger(name)  # type: ignore
