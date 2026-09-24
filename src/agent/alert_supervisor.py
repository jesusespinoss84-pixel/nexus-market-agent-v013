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
        # Persistent de-duplication by event fingerprint. This prevents the same
        # PAPER entry/exit from being sent twice when multiple scheduler jobs
        # call the dispatcher or when the event file is trimmed/reset.
        with self._lock:
            d = self._read()
            seen = list(d.get("trade_event_seen", []))
            seen_set = set(seen)
            fresh = []
            for ev in events:
                key = "|".join(str(ev.get(k, "")) for k in
                               ("t", "type", "symbol", "opened_utc", "closed_utc", "exit_reason"))
                if key and key not in seen_set:
                    fresh.append(ev)
                    seen.append(key)
                    seen_set.add(key)
            d["trade_event_seen"] = seen[-4000:]
            d["trade_event_index"] = len(events)  # kept for backward diagnostics
            self._write(d)
            return fresh

    def status_transition(self, key, value):
        with self._lock:
            d = self._read()
            old = d.get(key)
            d[key] = value
            self._write(d)
            return old, value, old != value
