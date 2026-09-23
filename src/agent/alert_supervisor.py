from __future__ import annotations
import json, threading
from datetime import datetime, timezone
from pathlib import Path

class AlertSupervisor:
    _lock = threading.RLock()

    def __init__(self, root, settings):
        self.root = Path(root)
        self.s = settings
        self.path = self.root / "storage" / "alert_supervisor_state.json"

    def _read(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def state(self):
        with self._lock:
            return self._read()

    def update(self, **kw):
        with self._lock:
            d = self._read()
            d.update(kw)
            self._write(d)
            return d

    def new_trade_events(self, events):
        with self._lock:
            d = self._read()
            idx = int(d.get("trade_event_index", 0))
            # Storage may have been reset/trimmed.
            if idx > len(events):
                idx = 0
            fresh = events[idx:]
            d["trade_event_index"] = len(events)
            self._write(d)
            return fresh

    def status_transition(self, key, value):
        with self._lock:
            d = self._read()
            old = d.get(key)
            d[key] = value
            self._write(d)
            return old, value, old != value
