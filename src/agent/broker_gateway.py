from __future__ import annotations
import json, os, ssl, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

class IBKRBrokerGateway:
    """V0.17 broker bridge. Read/preview only: NEXUS never transmits a live order."""
    def __init__(self, settings, root):
        self.cfg=settings.get('broker_gateway',{})
        self.root=Path(root)
        self.audit_path=self.root / self.cfg.get('audit_file','storage/broker_audit.json')
        self.base_url=os.getenv('NEXUS_IBKR_BASE_URL', self.cfg.get('base_url','https://localhost:5000/v1/api')).rstrip('/')
        self.account_id=os.getenv('NEXUS_IBKR_ACCOUNT_ID', self.cfg.get('account_id') or '').strip()
        self.verify_tls=bool(self.cfg.get('verify_tls',False))

    def _audit(self,event,details=None):
        rows=[]
        try: rows=json.loads(self.audit_path.read_text(encoding='utf-8'))
        except Exception: pass
        rows.append({'ts_utc':datetime.now(timezone.utc).isoformat(),'event':event,'details':details or {}})
        rows=rows[-int(self.cfg.get('audit_max',2000)):]
        self.audit_path.parent.mkdir(parents=True,exist_ok=True)
        self.audit_path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')

    def _request(self,path,method='GET',body=None,timeout=8):
        url=self.base_url+path
        data=None if body is None else json.dumps(body).encode('utf-8')
        req=urllib.request.Request(url,data=data,method=method,headers={'Content-Type':'application/json','Accept':'application/json'})
        ctx=None
        if url.startswith('https://') and not self.verify_tls:
            ctx=ssl._create_unverified_context()
        try:
            with urllib.request.urlopen(req,timeout=timeout,context=ctx) as r:
                raw=r.read().decode('utf-8','replace')
                return {'ok':True,'status':r.status,'data':json.loads(raw) if raw else {}}
        except urllib.error.HTTPError as e:
            try: msg=e.read().decode('utf-8','replace')
            except Exception: msg=str(e)
            return {'ok':False,'status':e.code,'error':msg[:800]}
        except Exception as e:
            return {'ok':False,'status':None,'error':str(e)[:800]}

    def status(self):
        enabled=bool(self.cfg.get('enabled',False))
        out={'provider':'IBKR','enabled':enabled,'mode':'READ_PREVIEW_ONLY','live_order_transmission':False,
             'manual_confirmation_required':True,'base_url':self.base_url,'account_configured':bool(self.account_id),
             'render_note':'Para cliente retail, Client Portal Gateway normalmente corre cerca del usuario; un Render público no puede alcanzar localhost de tu PC.'}
        if not enabled:
            out.update({'connected':False,'authenticated':False,'message':'Gateway deshabilitado. Configura IBKR antes de conectarlo.'});return out
        r=self._request('/iserver/auth/status')
        if r['ok']:
            d=r.get('data') or {};out.update({'connected':bool(d.get('connected',False)),'authenticated':bool(d.get('authenticated',False)),'message':'Sesión consultada correctamente.'})
        else:
            out.update({'connected':False,'authenticated':False,'message':'No se pudo alcanzar/autenticar IBKR Gateway.','error':r.get('error')})
        return out

    def accounts(self):
        r=self._request('/iserver/accounts')
        self._audit('ACCOUNTS_READ',{'ok':r.get('ok',False)})
        return r

    def preview(self, payload):
        """IBKR what-if only. No /orders live endpoint exists in NEXUS V0.17."""
        if not bool(self.cfg.get('enabled',False)): return {'ok':False,'error':'BROKER_GATEWAY_DISABLED'}
        account=(payload.get('account_id') or self.account_id).strip()
        if not account:return {'ok':False,'error':'IBKR_ACCOUNT_ID_REQUIRED'}
        conid=payload.get('conid'); side=str(payload.get('side','BUY')).upper(); qty=payload.get('quantity')
        if not conid or side not in ('BUY','SELL') or not qty:return {'ok':False,'error':'CONID_SIDE_QUANTITY_REQUIRED'}
        order={'conid':int(conid),'orderType':str(payload.get('order_type','LMT')).upper(),'side':side,'tif':str(payload.get('tif','DAY')).upper(),'quantity':float(qty)}
        if order['orderType']!='MKT':
            if payload.get('price') is None:return {'ok':False,'error':'PRICE_REQUIRED_FOR_NON_MARKET_PREVIEW'}
            order['price']=float(payload['price'])
        r=self._request(f'/iserver/account/{account}/orders/whatif','POST',{'orders':[order]},timeout=12)
        self._audit('ORDER_WHATIF',{'account':account,'order':order,'ok':r.get('ok',False)})
        return r

    def draft(self,payload):
        allowed=('symbol','conid','side','order_type','quantity','price','tif','account_id','reason')
        d={k:payload.get(k) for k in allowed if payload.get(k) is not None}
        d.update({'created_utc':datetime.now(timezone.utc).isoformat(),'status':'DRAFT_REVIEW_REQUIRED','transmitted':False})
        self._audit('ORDER_DRAFT_CREATED',d)
        return {'ok':True,'draft':d,'message':'Borrador creado. NEXUS V0.17 no transmite órdenes reales.'}
