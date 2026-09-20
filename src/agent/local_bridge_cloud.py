from __future__ import annotations
import hmac, json, os, threading
from datetime import datetime, timezone
from pathlib import Path

class LocalBridgeCloudState:
    def __init__(self, root):
        self.path=Path(root)/"storage"/"local_bridge_latest.json"
        self.lock=threading.RLock()
    def accept(self, token, payload):
        expected=os.getenv("NEXUS_RENDER_BRIDGE_TOKEN","").strip()
        if not expected:return False,"SERVER_TOKEN_NOT_CONFIGURED"
        if not token or not hmac.compare_digest(str(token),expected):return False,"UNAUTHORIZED"
        if not isinstance(payload,dict):return False,"INVALID_PAYLOAD"
        safe={"received_utc":datetime.now(timezone.utc).isoformat(),
              "bridge_version":str(payload.get("bridge_version") or ""),
              "connected":bool(payload.get("connected")),
              "mode":"IBKR_TWS_PAPER_READ_ONLY",
              "order_transmission_available":False,"account_number_exposed":False,
              "account":payload.get("account") if isinstance(payload.get("account"),dict) else {},
              "positions":payload.get("positions") if isinstance(payload.get("positions"),list) else [],
              "source_last_update_utc":payload.get("last_update_utc")}
        with self.lock:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            self.path.write_text(json.dumps(safe,ensure_ascii=False,indent=2),encoding="utf-8")
        return True,safe
    def latest(self):
        try:
            with self.lock:return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:return None
    def status(self,legacy=None):
        d=self.latest()
        if not d:
            out=dict(legacy or {});out.update({"local_bridge":False,"local_bridge_connected":False,
            "local_bridge_message":"Esperando primer reporte seguro desde la PC.","live_order_transmission":False})
            return out
        out=dict(legacy or {});out.update({"provider":"IBKR","enabled":True,"mode":"TWS_PAPER_READ_ONLY",
        "connected":bool(d.get("connected")),"authenticated":bool(d.get("connected")),"account_configured":True,
        "local_bridge":True,"local_bridge_connected":bool(d.get("connected")),
        "local_bridge_received_utc":d.get("received_utc"),
        "local_bridge_message":"TWS Paper conectado mediante NEXUS Local Broker Bridge.",
        "live_order_transmission":False,"manual_confirmation_required":True,"account_number_exposed":False})
        return out
