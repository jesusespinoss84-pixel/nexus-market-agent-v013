from __future__ import annotations
import json, threading, uuid
from datetime import datetime, timezone
from pathlib import Path

class PaperBrokerQueue:
    """Small auditable queue for IBKR PAPER only. Never authorizes LIVE accounts."""
    def __init__(self, root):
        self.path=Path(root)/"storage"/"ibkr_paper_orders.json"
        self.lock=threading.RLock()
    def _load(self):
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception: return []
    def _save(self, rows):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.path.write_text(json.dumps(rows[-500:],ensure_ascii=False,indent=2),encoding="utf-8")
    def prepare(self, payload):
        now=datetime.now(timezone.utc).isoformat(); oid=uuid.uuid4().hex[:12]
        row={"id":oid,"created_utc":now,"updated_utc":now,"status":"PREPARED","paper_only":True,
             "real_trading":False,"manual_confirmation":True,"bridge_dispatched":False,
             "symbol":str(payload.get("symbol") or "").upper().strip(),"side":str(payload.get("side") or "BUY").upper().strip(),
             "quantity":float(payload.get("quantity") or 0),"order_type":str(payload.get("order_type") or "LMT").upper().strip(),
             "limit_price":float(payload.get("limit_price") or 0),"tws_reference_price":float(payload.get("tws_reference_price") or 0),
             "tws_reference_source":str(payload.get("tws_reference_source") or "MANUAL_TWS_PRICE").upper().strip(),"tif":str(payload.get("tif") or "DAY").upper().strip(),
             "currency":str(payload.get("currency") or "USD").upper(),"exchange":str(payload.get("exchange") or "SMART").upper(),
             "reason":str(payload.get("reason") or "IBKR_PAPER_CONTROLLED_TEST")[:300]}
        with self.lock:
            rows=self._load(); rows.append(row); self._save(rows)
        return row
    def confirm(self, oid):
        with self.lock:
            rows=self._load(); found=None
            for r in rows:
                if r.get('id')==oid and r.get('status')=='PREPARED':
                    r['status']='CONFIRMED_FOR_PAPER'; r['confirmed_utc']=datetime.now(timezone.utc).isoformat(); r['updated_utc']=r['confirmed_utc']; found=dict(r); break
            self._save(rows)
        return found
    def next_for_bridge(self):
        with self.lock:
            rows=self._load(); found=None
            for r in rows:
                if r.get('status')=='CONFIRMED_FOR_PAPER' and not r.get('bridge_dispatched'):
                    r['bridge_dispatched']=True; r['status']='DISPATCHED_TO_PAPER_BRIDGE'; r['updated_utc']=datetime.now(timezone.utc).isoformat(); found=dict(r); break
            self._save(rows)
        return found
    def result(self, oid, payload):
        allowed={'status','ibkr_order_id','filled','remaining','avg_fill_price','last_fill_price','error_code','error_message','event_utc','event_type','tws_raw_status','tws_warning_text','why_held','perm_id','execution_state','exec_id','shares','price'}
        with self.lock:
            rows=self._load(); found=None
            for r in rows:
                if r.get('id')==oid:
                    event={k:payload[k] for k in allowed if k in payload}
                    event['received_utc']=datetime.now(timezone.utc).isoformat()
                    r.setdefault('events',[]).append(event)
                    r['events']=r['events'][-100:]
                    for k in allowed:
                        if k in payload: r[k]=payload[k]
                    r['updated_utc']=event['received_utc']; found=dict(r); break
            self._save(rows)
        return found
    def recover_from_tws(self, payload):
        """Upsert an existing IBKR PAPER order discovered after a Bridge/TWS restart."""
        ibkr_id=int(payload.get('ibkr_order_id') or 0)
        perm_id=int(payload.get('perm_id') or 0)
        if ibkr_id <= 0 and perm_id <= 0: return None
        now=datetime.now(timezone.utc).isoformat()
        with self.lock:
            rows=self._load(); found=None
            for r in rows:
                if (ibkr_id and int(r.get('ibkr_order_id') or 0)==ibkr_id) or (perm_id and int(r.get('perm_id') or 0)==perm_id):
                    found=r; break
            if found is None:
                rid=f"recovered-{perm_id or ibkr_id}"
                found={"id":rid,"created_utc":now,"updated_utc":now,"status":"TWS_RECOVERED_OPEN_ORDER",
                       "paper_only":True,"real_trading":False,"manual_confirmation":False,"bridge_dispatched":True,
                       "recovered_from_tws":True,"recovery_source":"TWS_OPEN_ORDERS_ON_STARTUP"}
                rows.append(found)
            allowed={'symbol','side','quantity','order_type','limit_price','tif','currency','exchange','ibkr_order_id','perm_id','tws_raw_status','tws_warning_text','transmit','filled','remaining','avg_fill_price','execution_state'}
            for k in allowed:
                if k in payload: found[k]=payload[k]
            found['status']=str(payload.get('status') or found.get('status') or 'TWS_RECOVERED_OPEN_ORDER')
            found['updated_utc']=now
            event={k:payload[k] for k in allowed if k in payload}
            event.update({'event_type':'RECOVERED_FROM_TWS','received_utc':now,'status':found['status']})
            found.setdefault('events',[]).append(event); found['events']=found['events'][-100:]
            self._save(rows)
            return dict(found)

    def latest(self, n=20):
        with self.lock: return list(reversed(self._load()[-n:]))
