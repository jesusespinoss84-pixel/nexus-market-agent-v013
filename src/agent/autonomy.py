import json, threading
from datetime import datetime, timezone
from src.config.loader import project_root

class AutonomousPaperAgent:
    _lock=threading.RLock()
    def __init__(self,s):
        self.s=s; self.root=project_root(); cfg=s.get('storage',{})
        self.log_path=self.root/cfg.get('decision_log','storage/decision_log.json')
        self.feed_path=self.root/cfg.get('alert_feed','storage/alert_feed.json')
        self.state_path=self.root/cfg.get('decision_state','storage/decision_state.json')
        self.cfg=s.get('autonomous_agent',{})
    def _read(self,p,d):
        try:return json.loads(p.read_text(encoding='utf-8'))
        except:return d
    def _write(self,p,obj):
        p.parent.mkdir(parents=True,exist_ok=True)
        t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8');t.replace(p)
    def _append(self,p,item,limit):
        a=self._read(p,[]);a.append(item);self._write(p,a[-int(limit):])
    def risk_plan(self,row,fx,cash_mxn=10000):
        native=float(row.get('price') or 0); currency=row.get('currency','MXN')
        px=native if currency=='MXN' else native*(fx or 1)
        if px<=0:return {}
        pp=self.s.get('paper_portfolio',{}); risk=self.s.get('risk',{})
        stop_pct=float(risk.get('stop_loss_pct',2)); target_pct=float(risk.get('take_profit_pct',4))
        max_budget=min(float(cash_mxn), float(self.s['paper_portfolio'].get('starting_cash_mxn',10000))*float(pp.get('max_position_pct',30))/100)
        risk_budget=float(self.s['paper_portfolio'].get('starting_cash_mxn',10000))*float(pp.get('risk_per_trade_pct',1))/100
        risk_per_share=max(px*stop_pct/100,0.01)
        shares=max(0,min(int(max_budget/px),int(risk_budget/risk_per_share)))
        return {'entry_mxn':round(px,2),'stop_mxn':round(px*(1-stop_pct/100),2),'target_mxn':round(px*(1+target_pct/100),2),'stop_pct':stop_pct,'target_pct':target_pct,'risk_budget_mxn':round(risk_budget,2),'suggested_shares':shares,'suggested_notional_mxn':round(shares*px,2)}
    def enrich(self,row,fx,cash_mxn=10000):
        c=self.cfg
        allowed=bool(c.get('enabled',True) and c.get('paper_only',True) and row.get('validated_match') and row.get('direction')=='BUY' and float(row.get('validation_score',0))>=float(c.get('min_validation_score',60)) and float(row.get('composite_score',0))>=float(c.get('min_composite_score',65)) and float(row.get('ai_strength_score',0))>=float(c.get('min_ai_strength',62)) and float(row.get('vulnerability_score',100))<=float(c.get('max_vulnerability_for_entry',60)))
        pause=bool(float(row.get('vulnerability_score',0))>=float(c.get('pause_vulnerability',85)) or float(row.get('market_context_score',100))<=float(c.get('pause_market_context',20)))
        row['autonomous_paper_allowed']=allowed
        row['autonomous_pause']=pause
        row['risk_plan']=self.risk_plan(row,fx,cash_mxn)
        if pause: row['ai_action']='PAUSAR'
        elif allowed: row['ai_action']='PAPER BUY'
        return row
    def process_transitions(self,rows):
        now=datetime.now(timezone.utc).isoformat(); prev=self._read(self.state_path,{})
        nxt={}; alerts=[]; logs=[]
        for r in rows:
            sym=r.get('symbol'); action=r.get('ai_action','OBSERVAR'); setup=bool(r.get('validated_match'))
            old=prev.get(sym,{})
            changed=old.get('action') not in (None,action)
            setup_new=setup and not bool(old.get('setup'))
            rec={'t':now,'symbol':sym,'name':r.get('name'),'action':action,'previous_action':old.get('action'),'setup_validated':setup,'ai_strength_score':r.get('ai_strength_score'),'validation_score':r.get('validation_score'),'composite_score':r.get('composite_score'),'vulnerability_score':r.get('vulnerability_score'),'market_context_score':r.get('market_context_score'),'risk_plan':r.get('risk_plan',{}),'reason':r.get('reason')}
            if changed or setup_new or action in ('PAPER BUY','PAUSAR') and old.get('action')!=action:
                logs.append(rec)
            if (changed and self.cfg.get('alert_on_action_change',True)) or (setup_new and self.cfg.get('alert_on_setup_detected',True)):
                title=f"{sym}: {action}"
                body=("Setup validado detectado. " if setup_new else "Cambio de decisión. ")+f"Fuerza {float(r.get('ai_strength_score',0)):.1f}/100"
                alert={'id':f"{sym}-{now}-{action}",'t':now,'symbol':sym,'title':title,'body':body,'action':action,'setup_validated':setup,'risk_plan':r.get('risk_plan',{})}
                alerts.append(alert)
            nxt[sym]={'action':action,'setup':setup}
        with self._lock:
            for rec in logs:self._append(self.log_path,rec,self.cfg.get('decision_log_max',5000))
            for al in alerts:self._append(self.feed_path,al,self.cfg.get('alert_feed_max',1000))
            self._write(self.state_path,nxt)
        return alerts
    def decisions(self,limit=200):return self._read(self.log_path,[])[-int(limit):]
    def alerts(self,limit=100):return self._read(self.feed_path,[])[-int(limit):]
