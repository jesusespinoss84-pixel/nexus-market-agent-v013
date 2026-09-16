from datetime import datetime,timezone
import json,math
from src.config.loader import load_settings,project_root
from src.data.yfinance_provider import YFinanceProvider
from src.indicators.technical import add_indicators
from src.strategies.momentum_breakout import evaluate
from src.agent.history import historical_metrics,viability_vulnerability
from src.agent.brain import market_context_score,validation_score,composite,explanation
from src.agent.portfolio import PaperPortfolio
from src.agent.validator import SymbolValidator
from src.agent.market_intelligence import MarketIntelligence
from src.agent.autonomy import AutonomousPaperAgent
from src.agent.learning import PaperLearningAgent
from src.agent.risk_governor import RiskGovernor

class NexusAgent:
    def __init__(self):
        self.s=load_settings();self.root=project_root();self.p=YFinanceProvider(self.s,self.root);self.port=PaperPortfolio(self.s);self.validator=SymbolValidator(self.s,self.p);self.intel=MarketIntelligence(self.s,self.p);self.auto=AutonomousPaperAgent(self.s);self.learning=PaperLearningAgent(self.s);self.riskgov=RiskGovernor(self.s)
    def static_validated_match(self,symbol,direction,score,row):
        for st in self.s.get('validated_strategies',[]):
            if symbol==st['symbol'] and direction==st['direction'] and score>=int(st['min_score']) and float(row['rsi14'])>=float(st.get('rsi14_min',-999)) and float(row['distance_sma20_pct'])>=float(st.get('distance_sma20_pct_min',-999)):return st
        return None
    def benchmarks(self):
        out=[]
        for b in self.s.get('benchmarks',[]):
            df,res,_=self.p.get_bars(b['symbol'],'1y','1d')
            if not df.empty:out.append({'symbol':b['symbol'],'resolved_symbol':res,'name':b['name'],'currency':b['currency'],**historical_metrics(df)})
        return out
    def decision(self,x):
        if x['validated_match']:return 'PAPER CANDIDATE'
        if x['validation_score']>=60 and x['composite_score']>=65:return 'VALIDADA · ESPERAR SETUP'
        if x['composite_score']>=70 and x['vulnerability_score']<=55:return 'INVESTIGAR'
        if x['score']>=65:return 'OPORTUNIDAD TÉCNICA'
        if x['viability_score']>=60:return 'VIABLE A ESTUDIAR'
        if x['vulnerability_score']>=75:return 'VULNERABLE'
        if x['score']>=55:return 'OBSERVAR'
        return 'SIN SEÑAL'
    def _prefilter(self,x):
        c=self.s.get('validation',{}).get('prefilter',{})
        return x['score']>=int(c.get('min_technical',65)) and x['viability_score']>=float(c.get('min_viability',45)) and x['vulnerability_score']<=float(c.get('max_vulnerability',85))
    def scan_once(self):
        now=datetime.now(timezone.utc).isoformat();fx=self.p.get_usdmxn();bench=self.benchmarks();snap=[];errors=[];raw=[]
        for a in self.s['assets']:
            try:
                intr,resi,ci=self.p.get_bars(a['symbol'],self.s['agent']['market_period'],self.s['agent']['market_interval'],a.get('fallback_symbols',[]));hist,resh,ch=self.p.get_bars(a['symbol'],self.s['agent']['history_period'],self.s['agent']['history_interval'],a.get('fallback_symbols',[]))
                if intr.empty or len(intr)<55 or hist.empty:errors.append(a['symbol']+': datos insuficientes');continue
                intr=add_indicators(intr);row=intr.iloc[-1];keys=['close','sma20','sma50','rsi14','rel_volume','high20_prev','low20_prev','distance_sma20_pct']
                if any(not math.isfinite(float(row[k])) for k in keys):continue
                sig=evaluate(row,self.s);price=float(row['close']);hm=historical_metrics(hist);via,vul=viability_vulnerability(hm);mc=market_context_score(a['market'],bench);mxn=price if a['currency']=='MXN' else price*(fx or 1)
                raw.append((a,row,sig,resi,price,hm,via,vul,mc,mxn))
            except Exception as e:errors.append(f"{a['symbol']}: {e}")
        # Embudo: valida automáticamente solo las mejores candidatas que no tengan cache reciente.
        prelim=[]
        for pack in raw:
            a,row,sig,resi,price,hm,via,vul,mc,mxn=pack
            precomp=composite(sig['score'],via,vul,mc,0)
            prelim.append((precomp,pack))
        prelim.sort(key=lambda z:z[0],reverse=True)
        auto_left=int(self.s.get('validation',{}).get('max_auto_per_scan',2)) if self.s.get('validation',{}).get('auto_validate',True) else 0
        for _,pack in prelim:
            if auto_left<=0:break
            a,row,sig,resi,price,hm,via,vul,mc,mxn=pack
            probe={'score':sig['score'],'viability_score':via,'vulnerability_score':vul}
            if not self._prefilter(probe):continue
            existing=self.validator.load(a['symbol'])
            if self.validator.is_fresh(existing):continue
            try:self.validator.validate(a,mode='quick',force=True);auto_left-=1
            except Exception as e:errors.append(f"VALIDATION {a['symbol']}: {e}")
        for _,pack in prelim:
            a,row,sig,resi,price,hm,via,vul,mc,mxn=pack
            dyn=self.validator.load(a['symbol'])
            dyn_score=float(dyn.get('validation_score',0)) if dyn and dyn.get('status')=='OK' else 0.0
            dyn_match=self.validator.current_setup_matches(dyn,sig['score'],row) if sig['direction']=='BUY' else False
            static=self.static_validated_match(a['symbol'],sig['direction'],sig['score'],row)
            st_match=bool(static)
            match=bool(dyn_match or st_match)
            vs=max(dyn_score,validation_score(st_match,static))
            comp=composite(sig['score'],via,vul,mc,vs)
            intel=self.intel.analyze(a,hist=self.p.get_bars(a['symbol'],'1y','1d',a.get('fallback_symbols',[]))[0])
            # V0.12 keeps historical validation independent; intelligence refines context, not probability.
            context12=round(mc*0.55+float(intel.get('market_intelligence_score',50))*0.45,1)
            comp=composite(sig['score'],via,vul,context12,vs)
            x={'timestamp':now,'symbol':a['symbol'],'resolved_symbol':resi,'name':a['name'],'aliases':a.get('aliases',''),'sector':a.get('sector',''),'industry':a.get('industry',''),'market':a['market'],'currency':a['currency'],'price':round(price,4),'mxn_equivalent':round(mxn,2),'cheap_mexican_under_50':a['market']=='MEX' and price<float(self.s['affordability']['cheap_mexican_max_mxn']),'direction':sig['direction'],'score':int(sig['score']),'rsi14':round(float(row['rsi14']),2),'rel_volume':round(float(row['rel_volume']),2),'distance_sma20_pct':round(float(row['distance_sma20_pct']),2),'viability_score':via,'vulnerability_score':vul,'market_context_score':context12,'validation_score':vs,'composite_score':comp,'validated_match':match,'validation_available':bool(dyn),'validation_mode':dyn.get('mode') if dyn else None,'validation_robustness':dyn.get('robustness_score') if dyn else None,'validation_walk_forward':(dyn.get('walk_forward') or {}).get('label') if dyn else None,'validated_strategy_id':(f"DYNAMIC_{a['symbol']}" if dyn_match else static['id'] if static else None),**intel,**{k:(round(v,2) if isinstance(v,(int,float)) and v is not None else v) for k,v in hm.items()}}
            x['decision']=self.decision(x);x['reason']=explanation(x)
            # V0.14: acción del agente para soporte de decisión / PAPER. No es probabilidad de ganancia.
            if x['vulnerability_score']>=80 or x['market_context_score']<=25:
                x['ai_action']='PAUSAR'
            elif x['validated_match'] and x['validation_score']>=60 and x['composite_score']>=65:
                x['ai_action']='PAPER BUY'
            elif x['validation_score']>=60 and x['composite_score']>=60:
                x['ai_action']='ESPERAR SETUP'
            elif x['composite_score']>=68 and x['vulnerability_score']<=60:
                x['ai_action']='ESTUDIAR'
            else:
                x['ai_action']='OBSERVAR'
            base_ai=0.34*x['composite_score']+0.24*x['validation_score']+0.18*(100-x['vulnerability_score'])+0.14*x.get('market_intelligence_score',50)+0.10*x['score']
            learn_adj=self.learning.adjustment()
            x['learning_adjustment_points']=learn_adj
            x['ai_strength_score']=round(max(0,min(100,base_ai+learn_adj)),1)
            x=self.auto.enrich(x,fx,self.port.summary().get('cash_mxn',self.s['paper_portfolio']['starting_cash_mxn']))
            snap.append(x)
        snap.sort(key=lambda x:(0 if x['validated_match'] else 1,-x['composite_score'],x['vulnerability_score']))
        transition_alerts=self.auto.process_transitions(snap)
        learning_summary=self.learning.observe(snap,fx)
        risk_state=self.riskgov.evaluate(self.port.summary(),snap)
        self.riskgov.stress_test(self.port.summary(),snap)
        for x in snap:
            x['risk_governor_level']=risk_state.get('level','NORMAL')
            x['risk_governor_block']=bool(risk_state.get('block_new_entries',False))
            if x['risk_governor_block'] and x.get('autonomous_paper_allowed'):
                x['autonomous_paper_allowed']=False
                if x.get('ai_action')=='PAPER BUY':x['ai_action']='ESPERAR RIESGO'
        for x in snap:
            if x.get('autonomous_paper_allowed') and self.s.get('autonomous_agent',{}).get('auto_open',True):self.port.maybe_open(x,fx)
            if x.get('autonomous_pause') and self.s.get('autonomous_agent',{}).get('auto_close_on_pause',True) and any(p.get('symbol')==x.get('symbol') for p in self.port.summary().get('positions',[])):
                self.port.manual_close(x['symbol'],x['price'],fx,'AGENT_PAUSE')
        self.port.update_and_close(snap,fx)
        state={'version':self.s['app']['version'],'mode':self.s['app']['mode'],'last_scan_utc':now,'assets_scanned':len(snap),'cheap_mexican_count':sum(1 for x in snap if x['cheap_mexican_under_50']),'validated_matches':sum(1 for x in snap if x['validated_match']),'validated_assets':sum(1 for x in snap if x['validation_score']>0),'usdmxn':round(fx,4) if fx else None,'errors':errors[-12:],'autonomous_agent':bool(self.s.get('autonomous_agent',{}).get('enabled',True)),'new_alerts':len(transition_alerts)}
        (self.root/self.s['storage']['state']).write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding='utf-8');(self.root/self.s['storage']['snapshot']).write_text(json.dumps(snap,indent=2,ensure_ascii=False),encoding='utf-8');(self.root/self.s['storage']['benchmarks']).write_text(json.dumps(bench,indent=2,ensure_ascii=False),encoding='utf-8')
        return state,snap
