import json, threading, time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order

RENDER_BASE='https://nexus-market-agent-v013.onrender.com'
PING_URL=RENDER_BASE+'/api/local-bridge/ping-body'
REPORT_URL=RENDER_BASE+'/api/local-bridge/report-body'
NEXT_ORDER_URL=RENDER_BASE+'/api/local-bridge/paper-order/next-body'
ORDER_RESULT_URL=RENDER_BASE+'/api/local-bridge/paper-order/result-body'
ORDER_RECOVER_URL=RENDER_BASE+'/api/local-bridge/paper-order/recover-body'
TWS_HOST='127.0.0.1'; TWS_PORT=7497; CLIENT_ID=44; ACCOUNT_REQ_ID=72
REPORT_SECONDS=30; POLL_SECONDS=5
ACCOUNT_TAGS=','.join(['NetLiquidation','TotalCashValue','AvailableFunds','BuyingPower','ExcessLiquidity','GrossPositionValue'])

class NexusIBKR(EWrapper,EClient):
    def __init__(self, token):
        EClient.__init__(self,self); self.token=token; self.ready=threading.Event(); self.accounts_ready=threading.Event(); self.account_ready=threading.Event(); self.positions_ready=threading.Event(); self.lock=threading.Lock(); self.account={}; self.positions=[]; self.accounts=[]; self.next_order_id=None; self.pending={}; self.recovered_open_orders={}; self.recovery_done=threading.Event()
    def nextValidId(self, orderId): self.next_order_id=int(orderId); print(f'[TWS] HANDSHAKE OK | nextValidId={orderId}'); self.ready.set()
    def managedAccounts(self, accountsList):
        self.accounts=[x.strip() for x in str(accountsList).split(',') if x.strip()]; self.accounts_ready.set(); print('[TWS] Cuenta(s) detectada(s); identificador oculto.')
    def paper_guard(self): return bool(self.accounts) and all(str(x).upper().startswith('DU') for x in self.accounts)
    def error(self, reqId, *args):
        code=None; msg=''
        if len(args)>=3 and isinstance(args[1],int): code,msg=args[1],args[2]
        elif len(args)>=2 and isinstance(args[0],int): code,msg=args[0],args[1]
        else: print(f'[TWS INFO] reqId={reqId} args={args}'); return
        if code in {2104,2106,2107,2108,2158}: print(f'[TWS INFO] {code}: {msg}'); return
        print(f'[TWS ERROR] {code}: {msg}')
        with self.lock:
            hit=next(((oid,p) for oid,p in self.pending.items() if p.get('ibkr_order_id')==reqId),None)
        if hit:
            oid,_=hit
            # 354 may accompany an order that TWS stages/holds because API market data is unavailable.
            # Do not call it FILLED or REJECTED without a definitive orderStatus/openOrder callback.
            if int(code or 0)==354:
                status='TWS_MANUAL_REVIEW_REQUIRED'
                execution_state='AWAITING_MANUAL_TWS_REVIEW'
                print('[PAPER ORDER] 354 -> REVISION MANUAL EN TWS PAPER. NO se anulan precauciones.')
                threading.Timer(0.8, self.reqOpenOrders).start()
            else:
                status='TWS_ERROR_REPORTED'
                execution_state='AWAITING_TWS_STATUS'
            post_result(self.token,{'id':oid,'status':status,'event_type':'ERROR_CALLBACK','execution_state':execution_state,'error_code':code,'error_message':str(msg)[:300],'ibkr_order_id':int(reqId),'event_utc':datetime.now(timezone.utc).isoformat()})
    def accountSummary(self, reqId, account, tag, value, currency):
        with self.lock:self.account[tag]={'value':value,'currency':currency}
    def accountSummaryEnd(self, reqId): self.account_ready.set(); print('[TWS] AccountSummary recibido.')
    def position(self, account, contract, position, avgCost):
        sym=getattr(contract,'symbol','') or getattr(contract,'localSymbol','')
        with self.lock:
            self.positions=[x for x in self.positions if x.get('symbol')!=sym]
            if float(position)!=0:self.positions.append({'symbol':sym,'position':float(position),'avg_cost':float(avgCost),'currency':getattr(contract,'currency',''),'sec_type':getattr(contract,'secType','')})
    def positionEnd(self): self.positions_ready.set(); print('[TWS] Positions recibido.')
    def _find_pending(self, order_id):
        with self.lock:
            return next(((oid,p) for oid,p in self.pending.items() if p.get('ibkr_order_id')==order_id),None)
    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice=0.0):
        hit=self._find_pending(orderId)
        if not hit: return
        oid,_=hit
        raw=str(status or '').strip()
        key=raw.upper().replace(' ','_')
        mapping={
            'PENDINGSUBMIT':'TWS_PENDING_SUBMIT','PENDING_SUBMIT':'TWS_PENDING_SUBMIT',
            'PRESUBMITTED':'TWS_PRE_SUBMITTED','PRE_SUBMITTED':'TWS_PRE_SUBMITTED',
            'SUBMITTED':'TWS_SUBMITTED','FILLED':'TWS_FILLED',
            'PENDINGCANCEL':'TWS_PENDING_CANCEL','PENDING_CANCEL':'TWS_PENDING_CANCEL',
            'CANCELLED':'TWS_CANCELLED','APICANCELLED':'TWS_CANCELLED','API_CANCELLED':'TWS_CANCELLED',
            'INACTIVE':'TWS_INACTIVE'
        }
        canonical=mapping.get(key,'TWS_STATUS_'+key if key else 'TWS_STATUS_UNKNOWN')
        print(f'[PAPER ORDER] {oid} -> {raw} | filled={filled} remaining={remaining} avg={avgFillPrice} whyHeld={whyHeld}')
        post_result(self.token,{'id':oid,'status':canonical,'event_type':'ORDER_STATUS','execution_state':canonical,'tws_raw_status':raw,'ibkr_order_id':int(orderId),'filled':float(filled),'remaining':float(remaining),'avg_fill_price':float(avgFillPrice),'last_fill_price':float(lastFillPrice),'perm_id':int(permId or 0),'why_held':str(whyHeld or '')[:200],'event_utc':datetime.now(timezone.utc).isoformat()})
    def openOrder(self, orderId, contract, order, orderState):
        hit=self._find_pending(orderId)
        raw=str(getattr(orderState,'status','') or '').strip()
        warning=str(getattr(orderState,'warningText','') or '').strip()
        if hit:
            oid,_=hit
            print(f'[PAPER ORDER] openOrder {oid} | TWS status={raw or "N/A"} | transmit={getattr(order,"transmit",None)} | warning={warning[:160]}')
            raw_key=raw.upper().replace(' ','_')
            if raw_key in {'SUBMITTED','PRESUBMITTED','PRE_SUBMITTED'}:
                state='TWS_SUBMITTED' if raw_key=='SUBMITTED' else 'TWS_PRE_SUBMITTED'
            elif raw_key=='FILLED': state='TWS_FILLED'
            elif raw_key in {'CANCELLED','APICANCELLED','API_CANCELLED'}: state='TWS_CANCELLED'
            elif raw_key=='INACTIVE': state='TWS_INACTIVE'
            else: state='TWS_STAGED_MANUAL_REVIEW'
            post_result(self.token,{'id':oid,'status':state,'event_type':'OPEN_ORDER','execution_state':state,'tws_raw_status':raw,'tws_warning_text':warning[:500],'ibkr_order_id':int(orderId),'event_utc':datetime.now(timezone.utc).isoformat()})
            return
        # Existing TWS PAPER order discovered after Bridge/TWS restart. Audit only: never retransmit it.
        symbol=str(getattr(contract,'symbol','') or getattr(contract,'localSymbol','') or '').upper()
        payload={'bridge_token':self.token,'paper_account_verified':self.paper_guard(),'status':'TWS_RECOVERED_OPEN_ORDER',
                 'execution_state':'TWS_RECOVERED_OPEN_ORDER','ibkr_order_id':int(orderId),
                 'perm_id':int(getattr(order,'permId',0) or 0),'symbol':symbol,
                 'side':str(getattr(order,'action','') or '').upper(),'quantity':float(getattr(order,'totalQuantity',0) or 0),
                 'order_type':str(getattr(order,'orderType','') or '').upper(),'limit_price':float(getattr(order,'lmtPrice',0) or 0),
                 'tif':str(getattr(order,'tif','') or '').upper(),'currency':str(getattr(contract,'currency','') or '').upper(),
                 'exchange':str(getattr(contract,'exchange','') or '').upper(),'tws_raw_status':raw,
                 'tws_warning_text':warning[:500],'transmit':bool(getattr(order,'transmit',False)),
                 'event_utc':datetime.now(timezone.utc).isoformat()}
        self.recovered_open_orders[int(orderId)]=payload
        st,txt=http_json(ORDER_RECOVER_URL,payload,30)
        print(f'[RECOVERY] TWS open order {orderId} {symbol} {payload["side"]} {payload["quantity"]} {payload["order_type"]} {payload["limit_price"]} | status={raw or "N/A"} | cloud={st}')
    def openOrderEnd(self):
        print(f'[RECOVERY] Consulta de órdenes abiertas terminada. Recuperadas: {len(self.recovered_open_orders)}')
        self.recovery_done.set()
    def execDetails(self, reqId, contract, execution):
        order_id=int(getattr(execution,'orderId',-1))
        hit=self._find_pending(order_id)
        if not hit: return
        oid,_=hit
        shares=float(getattr(execution,'shares',0) or 0); price=float(getattr(execution,'price',0) or 0)
        print(f'[PAPER ORDER] EJECUCION {oid} | shares={shares} price={price}')
        post_result(self.token,{'id':oid,'status':'TWS_EXECUTION_REPORTED','event_type':'EXECUTION','execution_state':'TWS_EXECUTION_REPORTED','ibkr_order_id':order_id,'exec_id':str(getattr(execution,'execId','') or ''),'shares':shares,'price':price,'event_utc':datetime.now(timezone.utc).isoformat()})
    def snapshot(self):
        with self.lock: acct=dict(self.account); pos=list(self.positions)
        def val(tag):
            try:return float(acct.get(tag,{}).get('value'))
            except:return acct.get(tag,{}).get('value')
        cur=next((acct[x].get('currency') for x in ('NetLiquidation','TotalCashValue','AvailableFunds') if x in acct and acct[x].get('currency')),None)
        return {'source':'NEXUS_LOCAL_BROKER_BRIDGE','bridge_version':'V4.6-PAPER','mode':'IBKR_TWS_PAPER_CONTROLLED','tws_connected':bool(self.isConnected()),'paper_account_verified':self.paper_guard(),'account_number_exposed':False,'order_transmission_available':self.paper_guard(),'received_utc':datetime.now(timezone.utc).isoformat(),'account':{'currency':cur,'net_liquidation':val('NetLiquidation'),'total_cash':val('TotalCashValue'),'available_funds':val('AvailableFunds'),'buying_power':val('BuyingPower'),'excess_liquidity':val('ExcessLiquidity'),'gross_position_value':val('GrossPositionValue')},'positions':pos}
    def place_guarded_paper(self, row):
        if not self.paper_guard(): raise RuntimeError('LIVE_ACCOUNT_REJECTED_OR_PAPER_NOT_VERIFIED')
        symbol=str(row.get('symbol') or '').upper(); qty=float(row.get('quantity') or 0); price=float(row.get('limit_price') or 0); tws_ref=float(row.get('tws_reference_price') or 0)
        if not symbol or symbol.endswith('.MX'): raise RuntimeError('V4_US_STOCKS_ONLY')
        if qty<=0 or qty>1 or price<=0 or qty*price>500: raise RuntimeError('V4_RISK_LIMIT_REJECTED')
        if tws_ref<=0: raise RuntimeError('TWS_REFERENCE_PRICE_REQUIRED')
        source=str(row.get('tws_reference_source') or 'MANUAL_TWS_PRICE').upper()
        if source!='MANUAL_TWS_PRICE': raise RuntimeError('UNTRUSTED_TWS_REFERENCE_SOURCE')
        deviation=abs(price-tws_ref)/tws_ref*100.0
        if deviation>2.5: raise RuntimeError(f'LOCAL_PRICE_GUARD_{deviation:.2f}PCT')
        if str(row.get('side') or '').upper() not in {'BUY','SELL'}: raise RuntimeError('INVALID_SIDE')
        if str(row.get('order_type') or '').upper()!='LMT' or str(row.get('tif') or '').upper()!='DAY': raise RuntimeError('V4_LMT_DAY_ONLY')
        if self.next_order_id is None: self.reqIds(-1); time.sleep(1)
        oid=int(self.next_order_id); self.next_order_id+=1
        c=Contract(); c.symbol=symbol; c.secType='STK'; c.exchange='SMART'; c.currency='USD'
        o=Order(); o.overridePercentageConstraints=False; o.action=str(row['side']).upper(); o.orderType='LMT'; o.totalQuantity=qty; o.lmtPrice=price; o.tif='DAY'; o.transmit=True; o.account=self.accounts[0]
        with self.lock:self.pending[row['id']]={'ibkr_order_id':oid,'symbol':symbol}
        print(f'[PAPER ORDER] GUARDA PRECIO OK ({deviation:.2f}% <= 2.5%) | fuente={source}. Precauciones TWS NO anuladas.')
        print(f'[PAPER ORDER] ENVIANDO A TWS PAPER: {symbol} {o.action} {qty} LMT {price} DAY | id local {row["id"]}')
        self.placeOrder(oid,c,o)
        post_result(self.token,{'id':row['id'],'status':'SENT_TO_TWS_PAPER','event_type':'PLACE_ORDER_CALLED','execution_state':'SENT_TO_TWS_PAPER','ibkr_order_id':oid,'event_utc':datetime.now(timezone.utc).isoformat()})

def http_json(url,payload=None,timeout=45):
    body=json.dumps(payload).encode() if payload is not None else None; req=Request(url,data=body,headers={'Content-Type':'application/json','User-Agent':'NEXUS-Bridge-V4.6-PAPER'},method='POST' if payload is not None else 'GET')
    try:
        with urlopen(req,timeout=timeout) as r:return r.status,r.read().decode(errors='replace')
    except HTTPError as e:return e.code,e.read().decode(errors='replace')
    except Exception as e:return 0,json.dumps({'error':str(e)})
def post_result(token,payload):
    payload=dict(payload); payload['bridge_token']=token; status,txt=http_json(ORDER_RESULT_URL,payload,30); return status,txt

def main():
    print('NEXUS LOCAL BROKER BRIDGE V4.6 - IBKR PAPER RECOVERY + ORDER LIFECYCLE')
    print('GUARDAS: cuenta PAPER obligatoria (DU), US STK, max 1 accion, max USD 500, LMT DAY.')
    print('CUENTAS LIVE: RECHAZADAS. Numero de cuenta: nunca se envia a Render.')
    print('PRECIO: fallback manual TWS permitido y auditado como MANUAL_TWS_PRICE; nunca anula precauciones TWS.'); print()
    token=input('Pega NEXUS_RENDER_BRIDGE_TOKEN y ENTER (SE MOSTRARA): ').strip(); print(f'[OK] Token capturado. Longitud {len(token)}.')
    if len(token)!=31: print('[ALTO] Token invalido.'); input('ENTER para cerrar...'); return
    st,txt=http_json(PING_URL,timeout=60); print(f'[CLOUD] PING HTTP {st} {txt[:220]}')
    if st!=200: input('ENTER para cerrar...'); return
    st,txt=http_json(REPORT_URL,{'bridge_token':token,'bridge_version':'V4.6-PAPER','mode':'IBKR_TWS_PAPER_CONTROLLED','account_number_exposed':False,'order_transmission_available':False},60); print(f'[CLOUD] TOKEN HTTP {st} {txt[:220]}')
    if st!=200: input('ENTER para cerrar...'); return
    app=NexusIBKR(token); print(f'[TWS] Conectando a {TWS_HOST}:{TWS_PORT} clientId={CLIENT_ID}...'); app.connect(TWS_HOST,TWS_PORT,clientId=CLIENT_ID); threading.Thread(target=app.run,daemon=True).start()
    if not app.ready.wait(12): print('[ALTO] Sin handshake TWS.'); app.disconnect(); input('ENTER...'); return
    app.reqManagedAccts(); app.accounts_ready.wait(8)
    if not app.paper_guard(): print('[ALTO] CUENTA PAPER NO VERIFICADA. V4.6 NO TRANSMITIRA ORDENES.'); app.disconnect(); input('ENTER...'); return
    print('[OK] CUENTA IBKR PAPER VERIFICADA. Identificador oculto.')
    app.reqAccountSummary(ACCOUNT_REQ_ID,'All',ACCOUNT_TAGS); app.reqPositions(); app.account_ready.wait(12); app.positions_ready.wait(12)
    print('[RECOVERY] Consultando órdenes PAPER abiertas existentes en TWS...')
    app.reqOpenOrders(); app.recovery_done.wait(10)
    print('[OK] PAPER -> TWS -> PYTHON -> RENDER listo. Recuperación + cola PAPER habilitadas. Ctrl+C para detener.')
    last_report=0
    try:
        while True:
            now=time.time()
            if now-last_report>=REPORT_SECONDS:
                rep=app.snapshot(); rep['bridge_token']=token; st,txt=http_json(REPORT_URL,rep,60); print(f'[OK] REPORT HTTP {st} | {datetime.now(timezone.utc).isoformat()}'); last_report=now
            st,txt=http_json(NEXT_ORDER_URL,{'bridge_token':token},30)
            if st==200:
                try: row=json.loads(txt).get('order')
                except: row=None
                if row:
                    try: app.place_guarded_paper(row)
                    except Exception as e:
                        print(f'[PAPER ORDER] RECHAZADA: {e}'); post_result(token,{'id':row.get('id'),'status':'REJECTED_BY_LOCAL_GUARD','error_message':str(e),'event_utc':datetime.now(timezone.utc).isoformat()})
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt: print('\n[STOP] Cerrando...')
    finally:
        try: app.cancelAccountSummary(ACCOUNT_REQ_ID); app.cancelPositions(); app.disconnect()
        except: pass
        print('[OK] V4.6 detenido.')
if __name__=='__main__': main()
