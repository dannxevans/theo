"""
Database Log Handler for Debug Console

Captures application logs and stores them in the debug_logs table when debug mode is enabled.
Thread-safe and designed to work with both Flask dev server and Gunicorn.
"""

import logging
import threading
import time
import json
import re
import sqlite3
from datetime import datetime
from queue import Queue, Empty
from typing import Optional
from core.user_utils import DEFAULT_USER_ID


class DatabaseLogHandler(logging.Handler):
    """
    Custom logging handler that captures logs to database for the debug console.

    Features:
    - Only captures when debug_enabled preference is True
    - Buffers logs for batch insertion (performance optimization)
    - Thread-safe for Gunicorn workers
    - Caches debug_enabled preference to avoid excessive database hits
    - Extracts component tags from log messages (e.g., [AUTH], [ROUTER])
    """

    def __init__(self, memory_store, batch_size=10, flush_interval=5.0):
        """
        Initialize the database log handler.

        Args:
            memory_store: MemoryStore instance for database access
            batch_size: Number of logs to batch before writing (default: 10)
            flush_interval: Seconds between forced flushes (default: 5.0)
        """
        super().__init__()
        self.memory_store = memory_store
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Thread-safe queue for log buffering
        self.log_queue = Queue(maxsize=1000)  # Limit queue size to prevent memory issues

        # Cache for debug_enabled preference (refreshed every 30 seconds)
        self._debug_enabled_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 30  # seconds
        self._cache_lock = threading.Lock()

        # Circuit breaker to prevent log flooding
        self._dropped_logs = 0
        self._last_drop_warning = 0

        # Background thread for batch processing
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self._flush_thread.start()

    def _is_debug_enabled(self) -> bool:
        """
        Check if debug logging is enabled, with caching to reduce database load.

        Returns:
            True if debug_enabled preference is set to true, False otherwise
        """
        now = time.time()

        with self._cache_lock:
            # Return cached value if still valid
            if self._debug_enabled_cache is not None and (now - self._cache_timestamp) < self._cache_ttl:
                return self._debug_enabled_cache

            # Refresh cache
            try:
                prefs = self.memory_store.get_all(DEFAULT_USER_ID)
                enabled = str(prefs.get("debug_enabled", "false")).lower() == "true"
                self._debug_enabled_cache = enabled
                self._cache_timestamp = now
                return enabled
            except Exception as e:
                # On error, assume disabled and cache for shorter time
                # NOTE: Can't use logging.error here - would cause recursion!
                self._debug_enabled_cache = False
                self._cache_timestamp = now - self._cache_ttl + 5  # Retry in 5 seconds
                return False

    def invalidate_cache(self):
        """
        Force cache invalidation to immediately pick up debug_enabled changes.
        Should be called when the debug_enabled preference is toggled.
        """
        with self._cache_lock:
            self._cache_timestamp = 0
            self._debug_enabled_cache = None

    def _extract_component(self, message: str) -> Optional[str]:
        """
        Extract component tag from log message (e.g., [AUTH], [ROUTER]).

        Args:
            message: Log message string

        Returns:
            Component name without brackets, or None if no tag found
        """
        match = re.match(r'\[([A-Z_-]+)\]', message)
        if match:
            return match.group(1)
        return None

    def emit(self, record: logging.LogRecord):
        """
        Handle a log record by adding it to the queue.

        Args:
            record: LogRecord instance to be logged
        """
        # CRITICAL: Prevent infinite recursion - don't log our own messages
        if record.name == 'core.logging_handler' or '[DEBUG-HANDLER]' in record.getMessage():
            return

        # Skip noisy loggers that would flood the debug console
        # These generate excessive logs that aren't useful for debugging
        noisy_loggers = [
            'sqlalchemy.engine',      # Database queries (very verbose)
            'sqlalchemy.pool',        # Connection pool
            'sqlalchemy.orm',         # ORM internals
            'werkzeug',               # Flask HTTP request logs (already have access logs)
            'urllib3',                # HTTP client logs
            'botocore',               # AWS SDK logs
            's3transfer',             # S3 transfer logs
        ]

        for noisy in noisy_loggers:
            if record.name.startswith(noisy):
                return

        # Skip if debug mode is not enabled
        if not self._is_debug_enabled():
            return

        try:
            # Extract log information
            message = self.format(record)
            component = self._extract_component(record.getMessage())

            # Extract session_id from thread local if available
            session_id = getattr(threading.current_thread(), 'session_id', None)

            # Create log entry
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'source': 'backend',
                'component': component,
                'message': message,
                'raw_data': json.dumps({
                    'filename': record.filename,
                    'lineno': record.lineno,
                    'funcName': record.funcName,
                    'pathname': record.pathname
                }),
                'user_id': None,  # Could extract from flask.g if needed
                'session_id': session_id
            }

            # Add to queue (non-blocking)
            try:
                self.log_queue.put_nowait(log_entry)
            except:
                # Queue is full - drop this log to prevent memory issues
                # Track dropped logs and warn periodically (not too often to avoid spam)
                self._dropped_logs += 1
                now = time.time()
                if now - self._last_drop_warning > 60:  # Warn at most once per minute
                    self._last_drop_warning = now
                    # Use stderr directly to avoid recursion
                    import sys
                    print(f"[DEBUG-HANDLER] Warning: Log queue full, dropped {self._dropped_logs} logs",
                          file=sys.stderr)
                    self._dropped_logs = 0

        except Exception as e:
            # Don't let logging errors crash the application
            # NOTE: Don't use logging.error here - would cause recursion!
            self.handleError(record)

    def _flush_worker(self):
        """
        Background thread worker that processes log queue and writes to database.
        Flushes when batch_size is reached or after flush_interval seconds.
        """
        buffer = []
        last_flush = time.time()

        while self._running:
            try:
                # Try to get a log entry (blocking with timeout)
                try:
                    entry = self.log_queue.get(timeout=1.0)
                    buffer.append(entry)
                except Empty:
                    pass

                # Flush if batch size reached or interval elapsed
                now = time.time()
                should_flush = (
                    len(buffer) >= self.batch_size or
                    (buffer and (now - last_flush) >= self.flush_interval)
                )

                if should_flush:
                    self._flush_buffer(buffer)
                    buffer = []
                    last_flush = now

            except Exception as e:
                # Don't use logging.error - would cause recursion!
                # Use stderr directly
                import sys
                print(f"[DEBUG-HANDLER] Error in flush worker: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)

        # Final flush on shutdown
        if buffer:
            self._flush_buffer(buffer)

    def _flush_buffer(self, buffer: list):
        """
        Write buffered log entries to database.

        Args:
            buffer: List of log entry dictionaries to write
        """
        if not buffer:
            return

        try:
            # Get database path from SQLAlchemy engine URL
            db_url = str(self.memory_store.engine.url)
            # Extract path from sqlite:///path/to/db.db
            if db_url.startswith('sqlite:///'):
                db_path = db_url.replace('sqlite:///', '')
            else:
                # Fallback for relative paths like sqlite:///./data/theo.db
                db_path = db_url.split('sqlite:///')[-1]

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check if debug_logs table exists before trying to insert
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='debug_logs'")
            if not cursor.fetchone():
                # Table doesn't exist yet - skip logging
                # This prevents crashes during initial startup before migrations run
                conn.close()
                return

            # Batch insert
            cursor.executemany("""
                INSERT INTO debug_logs (timestamp, level, source, component, message, raw_data, user_id, session_id)
                VALUES (:timestamp, :level, :source, :component, :message, :raw_data, :user_id, :session_id)
            """, buffer)

            conn.commit()
            conn.close()

        except Exception as e:
            # Don't use logging.error - would cause recursion!
            # Use stderr directly
            import sys
            print(f"[DEBUG-HANDLER] Error flushing logs to database: {e}", file=sys.stderr)
            # Don't traceback here - would be too noisy, just log the error

    def close(self):
        """
        Clean shutdown of the log handler.
        """
        self._running = False
        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)
        super().close()
