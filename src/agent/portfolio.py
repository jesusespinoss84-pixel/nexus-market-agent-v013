import json, threading
from datetime import datetime, timezone, timedelta
from src.config.loader import project_root

class PaperPortfolio:
    _lock=threading.RLock()

    def __init__(self,s):
        self.s=s
        self.root=project_root()
        self.path=self.root/s['storage']['portfolio']
        self.curve=self.root/s['storage']['equity_curve']
        self.events_path=self.root/s['storage'].get('trade_events','storage/paper_trade_events.json')
        self.load()

    def _read_json(self,p,default):
        try:return json.loads(p.read_text(encoding='utf-8'))
        except:return default

    def _write_json(self,p,obj):
        p.parent.mkdir(parents=True,exist_ok=True)
        tmp=p.with_suffix(p.suffix+'.tmp')
        tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
        tmp.replace(p)

    def load(self):
        with self._lock:
            if self.path.exists():
                self.data=self._read_json(self.path,{})
            else:self.data={}
            start=float(self.s['paper_portfolio']['starting_cash_mxn'])
            self.data.setdefault('starting_cash_mxn',start)
            self.data.setdefault('cash_mxn',start)
            self.data.setdefault('positions',[])
            self.data.setdefault('closed',[])
            self.data.setdefault('last_update_utc',None)
            self.save()

    def save(self):
        with self._lock:self._write_json(self.path,self.data)

    def _event(self,kind,payload):
        with self._lock:
            arr=self._read_json(self.events_path,[])
            arr.append({'t':datetime.now(timezone.utc).isoformat(),'type':kind,**payload})
            self._write_json(self.events_path,arr[-2000:])

    def _recently_closed(self,symbol):
        mins=int(self.s['paper_portfolio'].get('cooldown_minutes_after_close',60))
        now=datetime.now(timezone.utc)
        for x in reversed(self.data.get('closed',[])):
            if x.get('symbol')!=symbol:continue
            try:
                d=datetime.fromisoformat(x['closed_utc'].replace('Z','+00:00'))
                return now-d < timedelta(minutes=mins)
            except:return False
        return False

    def _paper_shares(self,row,px_mxn,max_budget,risk_budget=None,stop_pct=None):
        cfg=self.s['paper_portfolio']; allow_frac=bool(cfg.get('allow_fractional_us',True) and row.get('currency')=='USD')
        if risk_budget is None:
            raw=max_budget/px_mxn
        else:
            risk_per_share=max(px_mxn*float(stop_pct or 0),0.01); raw=min(max_budget/px_mxn,risk_budget/risk_per_share)
        if allow_frac:
            import math
            precision=int(cfg.get('fractional_precision',4)); step=10**(-precision)
            sh=math.floor(max(0,raw)/step)*step; sh=round(sh,precision)
            return sh if sh>=float(cfg.get('min_fractional_shares',0.001)) else 0
        return max(0,int(raw))

    def maybe_open(self,row,fx):
        cfg=self.s['paper_portfolio']
        if not cfg.get('enabled') or not row.get('validated_match') or row.get('direction')!='BUY':return False
        with self._lock:
            if len(self.data['positions'])>=int(cfg.get('max_open_positions',4)):return False
            if any(p['symbol']==row['symbol'] for p in self.data['positions']):return False
            if self._recently_closed(row['symbol']):return False

            px_native=float(row['price'])
            px_mxn=px_native if row['currency']=='MXN' else px_native*(fx or 1)
            if px_mxn<=0:return False

            max_budget=min(
                self.data['starting_cash_mxn']*float(cfg.get('max_position_pct',30))/100,
                self.data['cash_mxn']
            )
            risk_budget=self.data['starting_cash_mxn']*float(cfg.get('risk_per_trade_pct',1.0))/100
            stop_pct=float(self.s['risk']['stop_loss_pct'])/100
            risk_per_share=max(px_mxn*stop_pct,0.01)
            sh=self._paper_shares(row,px_mxn,max_budget,risk_budget,stop_pct)
            if sh<=0:return False

            slip=float(cfg.get('slippage_pct',0.05))/100
            entry=px_mxn*(1+slip)
            cost=entry*sh
            if cost>self.data['cash_mxn']:return False
            tp=float(self.s['risk']['take_profit_pct'])/100

            p={
                'symbol':row['symbol'],'name':row['name'],'currency':row['currency'],
                'shares':sh,'entry_native':round(px_native,6),
                'entry_price_mxn':round(entry,2),'last_price_mxn':round(px_mxn,2),
                'stop_mxn':round(entry*(1-stop_pct),2),'target_mxn':round(entry*(1+tp),2),
                'market_value_mxn':round(px_mxn*sh,2),
                'unrealized_mxn':round((px_mxn-entry)*sh,2),
                'opened_utc':datetime.now(timezone.utc).isoformat(),
                'strategy_id':row.get('validated_strategy_id'),
                'validation_score':row.get('validation_score'),
                'composite_score':row.get('composite_score'),
                'source':'LIVE_PAPER'
            }
            self.data['cash_mxn']-=cost
            self.data['positions'].append(p)
            self.data['last_update_utc']=datetime.now(timezone.utc).isoformat()
            self.save()
            self._event('BUY',p)
            return True

    def _mark_positions(self,price_map,fx):
        still=[];now=datetime.now(timezone.utc).isoformat()
        cfg=self.s['paper_portfolio']
        half_comm=float(cfg.get('commission_pct_round_trip',0.02))/200
        for p in self.data['positions']:
            q=price_map.get(p['symbol'])
            if not q:
                still.append(p);continue
            native=float(q['price'])
            row_currency=p.get('currency','MXN')
            px=native if row_currency=='MXN' else native*(fx or 1)
            p['last_price_mxn']=round(px,2)
            p['last_quote_utc']=q.get('timestamp') or now
            p['market_value_mxn']=round(px*p['shares'],2)
            p['unrealized_mxn']=round((px-p['entry_price_mxn'])*p['shares'],2)
            reason='STOP' if px<=p['stop_mxn'] else 'TARGET' if px>=p['target_mxn'] else None
            if not reason:
                still.append(p);continue

            exit_px=px*(1-half_comm)
            proceeds=exit_px*p['shares']
            pnl=(exit_px-p['entry_price_mxn'])*p['shares']
            risk=p['entry_price_mxn']-p['stop_mxn']
            rm=(exit_px-p['entry_price_mxn'])/risk if risk>0 else 0
            closed={**p,'closed_utc':now,'exit_price_mxn':round(exit_px,2),
                    'exit_reason':reason,'pnl_mxn':round(pnl,2),'r_multiple':round(rm,3)}
            self.data['cash_mxn']+=proceeds
            self.data['closed'].append(closed)
            self._event('SELL',closed)
        self.data['positions']=still
        self.data['last_update_utc']=now
        self.save()
        self.snapshot_curve()

    def update_and_close(self,snapshot,fx):
        # Uses scanner prices.
        pm={}
        for row in snapshot:
            pm[row['symbol']]={'price':row['price'],'timestamp':row.get('timestamp')}
        with self._lock:self._mark_positions(pm,fx)

    def live_update(self,provider,assets,fx):
        """Refresh only open positions with freshest available intraday quote."""
        with self._lock:
            symbols=[p['symbol'] for p in self.data['positions']]
        if not symbols:
            self.snapshot_curve()
            return self.summary()

        amap={a['symbol']:a for a in assets}
        pm={}
        for sym in symbols:
            a=amap.get(sym,{})
            q=provider.get_live_price(sym,a.get('fallback_symbols',[]))
            if q:pm[sym]=q
        with self._lock:self._mark_positions(pm,fx)
        return self.summary()


    def manual_open(self,row,fx,budget_mxn=None,stop_pct=None,target_pct=None):
        """Open a PAPER position manually. Never sends a real broker order."""
        cfg=self.s['paper_portfolio']
        if not cfg.get('enabled'):return {'ok':False,'error':'PAPER_DISABLED'}
        with self._lock:
            if any(p['symbol']==row['symbol'] for p in self.data['positions']):return {'ok':False,'error':'POSITION_ALREADY_OPEN'}
            if len(self.data['positions'])>=int(cfg.get('max_open_positions',4)):return {'ok':False,'error':'MAX_OPEN_POSITIONS'}
            px_native=float(row['price'])
            px_mxn=px_native if row['currency']=='MXN' else px_native*(fx or 1)
            if px_mxn<=0:return {'ok':False,'error':'INVALID_PRICE'}
            default_budget=self.data['starting_cash_mxn']*float(cfg.get('max_position_pct',30))/100
            budget=max(0,min(float(budget_mxn or default_budget),self.data['cash_mxn']))
            sh=self._paper_shares(row,px_mxn,budget)
            if sh<=0:return {'ok':False,'error':'INSUFFICIENT_CASH'}
            slip=float(cfg.get('slippage_pct',0.05))/100
            entry=px_mxn*(1+slip)
            cost=entry*sh
            if cost>self.data['cash_mxn']:
                sh=self._paper_shares(row,entry,self.data['cash_mxn'])
                cost=entry*sh
            if sh<=0:return {'ok':False,'error':'INSUFFICIENT_CASH'}
            sp=float(stop_pct if stop_pct is not None else self.s['risk']['stop_loss_pct'])/100
            tp=float(target_pct if target_pct is not None else self.s['risk']['take_profit_pct'])/100
            p={
                'symbol':row['symbol'],'name':row['name'],'currency':row['currency'],'shares':sh,
                'entry_native':round(px_native,6),'entry_price_mxn':round(entry,2),'last_price_mxn':round(px_mxn,2),
                'stop_mxn':round(entry*(1-sp),2),'target_mxn':round(entry*(1+tp),2),
                'market_value_mxn':round(px_mxn*sh,2),'unrealized_mxn':round((px_mxn-entry)*sh,2),
                'opened_utc':datetime.now(timezone.utc).isoformat(),'strategy_id':'MANUAL_PAPER',
                'validation_score':row.get('validation_score'),'composite_score':row.get('composite_score'),
                'source':'MANUAL_PAPER'
            }
            self.data['cash_mxn']-=cost
            self.data['positions'].append(p)
            self.data['last_update_utc']=datetime.now(timezone.utc).isoformat()
            self.save();self._event('BUY_MANUAL',p);self.snapshot_curve()
            return {'ok':True,'position':p}

    def manual_close(self,symbol,price_native,fx,reason='MANUAL'):
        """Close one PAPER position manually. Never sends a real broker order."""
        with self._lock:
            pos=next((p for p in self.data['positions'] if p.get('symbol')==symbol),None)
            if not pos:return {'ok':False,'error':'POSITION_NOT_FOUND'}
            px=float(price_native) if pos.get('currency')=='MXN' else float(price_native)*(fx or 1)
            cfg=self.s['paper_portfolio'];half_comm=float(cfg.get('commission_pct_round_trip',0.02))/200
            exit_px=px*(1-half_comm);proceeds=exit_px*pos['shares'];pnl=(exit_px-pos['entry_price_mxn'])*pos['shares']
            risk=pos['entry_price_mxn']-pos['stop_mxn'];rm=(exit_px-pos['entry_price_mxn'])/risk if risk>0 else 0
            now=datetime.now(timezone.utc).isoformat()
            closed={**pos,'closed_utc':now,'exit_price_mxn':round(exit_px,2),'exit_reason':reason,
                    'pnl_mxn':round(pnl,2),'r_multiple':round(rm,3)}
            self.data['positions']=[p for p in self.data['positions'] if p.get('symbol')!=symbol]
            self.data['cash_mxn']+=proceeds;self.data['closed'].append(closed);self.data['last_update_utc']=now
            self.save();self._event('SELL_MANUAL',closed);self.snapshot_curve()
            return {'ok':True,'closed':closed}

    def snapshot_curve(self):
        with self._lock:
            mv=sum(p.get('market_value_mxn',0) for p in self.data['positions'])
            eq=self.data['cash_mxn']+mv
            arr=self._read_json(self.curve,[])
            now=datetime.now(timezone.utc).isoformat()
            # Avoid dozens of duplicate points in the same minute.
            if arr and str(arr[-1].get('t',''))[:16]==now[:16]:
                arr[-1]={'t':now,'equity_mxn':round(eq,2)}
            else:arr.append({'t':now,'equity_mxn':round(eq,2)})
            self._write_json(self.curve,arr[-5000:])

    def events(self):
        return self._read_json(self.events_path,[])

    def summary(self):
        with self._lock:
            self.load()
            mv=sum(p.get('market_value_mxn',0) for p in self.data['positions'])
            eq=self.data['cash_mxn']+mv
            pnl=eq-self.data['starting_cash_mxn']
            c=self.data['closed'];w=sum(1 for x in c if x.get('pnl_mxn',0)>0)
            wr=w/len(c)*100 if c else 0
            realized=sum(float(x.get('pnl_mxn',0)) for x in c)
            return {**self.data,
                'market_value_mxn':round(mv,2),'equity_mxn':round(eq,2),
                'total_pnl_mxn':round(pnl,2),'realized_pnl_mxn':round(realized,2),
                'unrealized_pnl_mxn':round(sum(p.get('unrealized_mxn',0) for p in self.data['positions']),2),
                'wins':w,'losses':len(c)-w,'win_rate_pct':round(wr,1)
            }
