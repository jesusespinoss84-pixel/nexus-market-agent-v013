import json, math, threading
from datetime import datetime, timezone, timedelta
from src.config.loader import project_root

class PaperLearningAgent:
    _lock=threading.RLock()
    def __init__(self,s):
        self.s=s; self.root=project_root(); st=s.get('storage',{})
        self.samples_path=self.root/st.get('learning_samples','storage/learning_samples.json')
        self.summary_path=self.root/st.get('learning_summary','storage/learning_summary.json')
        self.state_path=self.root/st.get('learning_state','storage/learning_state.json')
        self.audit_path=self.root/st.get('learning_audit','storage/learning_audit.json')
        self.counterfactual_path=self.root/st.get('learning_counterfactual','storage/learning_counterfactual.json')
        self.calibration_path=self.root/st.get('learning_calibration','storage/learning_calibration.json')
        self.cfg=s.get('learning_agent',{})
    def _read(self,p,d):
        try:return json.loads(p.read_text(encoding='utf-8'))
        except:return d
    def _write(self,p,obj):
        p.parent.mkdir(parents=True,exist_ok=True)
        t=p.with_suffix(p.suffix+'.tmp'); t.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8'); t.replace(p)
    def _now(self): return datetime.now(timezone.utc)
    def _price_mxn(self,row,fx):
        try:
            px=float(row.get('price') or 0)
            return px if row.get('currency','MXN')=='MXN' else px*float(fx or 1)
        except:return 0.0
    def _eligible_action(self,a):
        return a in ('PAPER BUY','ESPERAR SETUP','ESTUDIAR','OBSERVAR','PAUSAR')
    def _direction_score(self,action,ret):
        # No intenta predecir con certeza; sólo mide si la decisión fue coherente con el movimiento posterior.
        if action in ('PAPER BUY','ESPERAR SETUP','ESTUDIAR'):
            return 1 if ret>0 else -1 if ret<0 else 0
        if action=='PAUSAR':
            return 1 if ret<=0 else -1
        return 0
    def _regime(self,row):
        mc=float(row.get('market_context_score') or 50); vol=float(row.get('volatility_30d_live') or 0); dist=float(row.get('distance_sma20_pct') or 0)
        if mc <= 30: return 'RISK_OFF'
        if vol >= 45: return 'ALTA_VOLATILIDAD'
        if mc >= 65 and dist >= 0: return 'ALCISTA'
        if mc < 45 and dist < 0: return 'BAJISTA'
        return 'LATERAL'
    def _confidence(self,n):
        if n < 5: return 'MUY BAJA'
        if n < 12: return 'BAJA'
        if n < 30: return 'MEDIA'
        if n < 60: return 'ALTA'
        return 'MUY ALTA'
    def _context_key(self,sm):
        return f"{sm.get('symbol') or 'SIN_SIMBOLO'}|{sm.get('regime') or 'SIN_REGIMEN'}|{sm.get('sector') or 'SIN_SECTOR'}|{sm.get('action') or 'SIN_ACCION'}"
    def _counterfactual_label(self,action,ret):
        threshold=float(self.cfg.get('counterfactual_move_threshold_pct',0.50))
        if action in ('ESPERAR SETUP','ESTUDIAR','OBSERVAR','PAUSAR'):
            if ret >= threshold: return 'OPORTUNIDAD_PERDIDA'
            if ret <= -threshold: return 'ENTRADA_EVITADA'
            return 'NEUTRAL'
        if action=='PAPER BUY':
            if ret >= threshold: return 'COMPRA_FAVORABLE'
            if ret <= -threshold: return 'COMPRA_DESFAVORABLE'
        return 'NEUTRAL'
    def _promotion(self,n,hit,avg):
        if n < int(self.cfg.get('min_samples_per_symbol',12)): return 'EXPERIMENTAL'
        if n < int(self.cfg.get('min_samples_candidate_review',40)): return 'PAPER'
        if hit is not None and avg is not None and hit >= float(self.cfg.get('candidate_min_hit_rate_pct',58)) and avg >= float(self.cfg.get('candidate_min_avg_return_pct',0.15)): return 'CANDIDATA A REVISIÓN REAL'
        return 'PAPER'
    def observe(self,rows,fx):
        if not self.cfg.get('enabled',True): return self.summary()
        now=self._now(); interval=int(self.cfg.get('sample_interval_minutes',60))
        horizons=[int(x) for x in self.cfg.get('horizons_minutes',[60,1440,7200])]
        samples=self._read(self.samples_path,[]); state=self._read(self.state_path,{})
        bysym={r.get('symbol'):r for r in rows if r.get('symbol')}
        # Primero maduramos muestras anteriores usando el precio actual disponible.
        for sm in samples:
            sym=sm.get('symbol'); row=bysym.get(sym)
            if not row: continue
            px=self._price_mxn(row,fx)
            if px<=0: continue
            try: t0=datetime.fromisoformat(sm['t'].replace('Z','+00:00'))
            except: continue
            elapsed=(now-t0).total_seconds()/60
            out=sm.setdefault('outcomes',{})
            for h in horizons:
                k=str(h)
                if k in out or elapsed < h: continue
                entry=float(sm.get('entry_price_mxn') or 0)
                if entry<=0: continue
                ret=(px/entry-1)*100
                out[k]={'evaluated_utc':now.isoformat(),'price_mxn':round(px,4),'return_pct':round(ret,4),'direction_score':self._direction_score(sm.get('action'),ret),'counterfactual':self._counterfactual_label(sm.get('action'),ret)}
        # Después registramos nuevas observaciones, máximo una por símbolo por intervalo.
        for r in rows:
            sym=r.get('symbol'); action=r.get('ai_action','OBSERVAR')
            if not sym or not self._eligible_action(action): continue
            px=self._price_mxn(r,fx)
            if px<=0: continue
            prev=state.get(sym,{})
            last=prev.get('last_sample_utc')
            if last:
                try:
                    age=now-datetime.fromisoformat(last.replace('Z','+00:00'))
                    # V0.16.2: evita inflar evidencia con decisiones idénticas repetidas.
                    same_action=prev.get('last_action')==action
                    same_regime=prev.get('last_regime')==self._regime(r)
                    dedupe=int(self.cfg.get('duplicate_same_decision_minutes',240))
                    if age < timedelta(minutes=interval): continue
                    if same_action and same_regime and age < timedelta(minutes=dedupe): continue
                except: pass
            sample={
                'id':f"{sym}-{int(now.timestamp())}",'t':now.isoformat(),'symbol':sym,'name':r.get('name'),'action':action,
                'entry_price_mxn':round(px,4),'currency':r.get('currency'),'setup_validated':bool(r.get('validated_match')),
                'sector':r.get('sector'),'industry':r.get('industry'),'regime':self._regime(r),
                'features':{
                    'technical':r.get('score'),'composite':r.get('composite_score'),'validation':r.get('validation_score'),
                    'robustness':r.get('validation_robustness'),'vulnerability':r.get('vulnerability_score'),
                    'market_context':r.get('market_context_score'),'intelligence':r.get('market_intelligence_score'),
                    'ai_strength':r.get('ai_strength_score'),'rsi14':r.get('rsi14'),'distance_sma20_pct':r.get('distance_sma20_pct'),
                    'relative_volume':r.get('relative_volume')
                },'outcomes':{}
            }
            samples.append(sample); state[sym]={'last_sample_utc':now.isoformat(),'last_action':action,'last_regime':sample['regime']}
        maxn=int(self.cfg.get('max_samples',20000)); samples=samples[-maxn:]
        with self._lock:
            self._write(self.samples_path,samples); self._write(self.state_path,state)
            summary=self._build_summary(samples,horizons)
            self._write(self.summary_path,summary)
        return summary
    def _build_summary(self,samples,horizons):
        stats={}
        for h in horizons:
            hk=str(h); stats[hk]={}
            for a in ('PAPER BUY','ESPERAR SETUP','ESTUDIAR','OBSERVAR','PAUSAR'):
                vals=[]; ds=[]
                for sm in samples:
                    if sm.get('action')!=a: continue
                    o=sm.get('outcomes',{}).get(hk)
                    if not o: continue
                    vals.append(float(o.get('return_pct',0))); ds.append(float(o.get('direction_score',0)))
                n=len(vals)
                if n:
                    win=sum(1 for x in ds if x>0)/n*100
                    avg=sum(vals)/n
                    stats[hk][a]={'n':n,'avg_return_pct':round(avg,3),'decision_hit_rate_pct':round(win,1),'min_return_pct':round(min(vals),3),'max_return_pct':round(max(vals),3)}
                else: stats[hk][a]={'n':0,'avg_return_pct':None,'decision_hit_rate_pct':None,'min_return_pct':None,'max_return_pct':None}
        adj=self._compute_adjustment(stats)
        audit=self._audit(samples)
        cf=self._counterfactual(samples)
        self._write(self.audit_path,audit); self._write(self.counterfactual_path,cf)
        cal=self._calibration(samples,horizons)
        self._write(self.calibration_path,cal)
        maturity=self._maturity_report(samples,horizons,stats,cal)
        return {'updated_utc':self._now().isoformat(),'total_samples':len(samples),'horizons_minutes':horizons,'stats':stats,'ai_adjustment_points':adj,
                'mode':'SHADOW_LEARNING_0165','auto_change_strategy_weights':False,'audit':audit,'counterfactual':cf,'calibration':cal,'maturity':maturity,'note':self.cfg.get('note')}
    def _audit(self,samples):
        h=str(int(self.cfg.get('adjustment_horizon_minutes',1440)))
        def group(keyfn):
            out={}
            for sm in samples:
                o=sm.get('outcomes',{}).get(h)
                if not o: continue
                k=keyfn(sm) or 'SIN_DATO'; z=out.setdefault(k,{'n':0,'returns':[],'hits':0})
                z['n']+=1; z['returns'].append(float(o.get('return_pct',0))); z['hits']+=1 if float(o.get('direction_score',0))>0 else 0
            final={}
            for k,z in out.items():
                n=z['n']; avg=sum(z['returns'])/n if n else None; hit=z['hits']/n*100 if n else None
                final[k]={'n':n,'avg_return_pct':round(avg,3) if avg is not None else None,'decision_hit_rate_pct':round(hit,1) if hit is not None else None,'promotion':self._promotion(n,hit,avg)}
            return final
        ctx=group(self._context_key)
        for v in ctx.values(): v['confidence']=self._confidence(v.get('n',0))
        return {'horizon_minutes':int(h),'by_symbol':group(lambda x:x.get('symbol')),'by_regime':group(lambda x:x.get('regime')),'by_sector':group(lambda x:x.get('sector')),'by_context':ctx,'guardrails':{'strategy_weights_auto_change':False,'real_trading':False,'max_global_adjustment_points':float(self.cfg.get('max_ai_adjustment_points',3))}}
    def _counterfactual(self,samples):
        h=str(int(self.cfg.get('adjustment_horizon_minutes',1440)))
        counts={k:0 for k in ('OPORTUNIDAD_PERDIDA','ENTRADA_EVITADA','COMPRA_FAVORABLE','COMPRA_DESFAVORABLE','NEUTRAL')}
        recent=[]; action_returns={}
        for sm in samples:
            o=sm.get('outcomes',{}).get(h)
            if not o: continue
            ret=float(o.get('return_pct',0)); label=o.get('counterfactual') or self._counterfactual_label(sm.get('action'),ret)
            counts[label]=counts.get(label,0)+1
            a=sm.get('action','SIN_ACCION'); action_returns.setdefault(a,[]).append(ret)
            if label in ('OPORTUNIDAD_PERDIDA','ENTRADA_EVITADA','COMPRA_DESFAVORABLE'):
                recent.append({'symbol':sm.get('symbol'),'action':a,'result':label,'return_pct':round(ret,3),'regime':sm.get('regime'),'sector':sm.get('sector'),'t':sm.get('t')})
        compare={}
        for a,vals in action_returns.items(): compare[a]={'n':len(vals),'avg_return_pct':round(sum(vals)/len(vals),3),'confidence':self._confidence(len(vals))}
        return {'horizon_minutes':int(h),'counts':counts,'action_comparison':compare,'recent':recent[-25:],'note':'Contrafactual PAPER: mide qué habría ocurrido después de cada decisión; no representa una orden real ni certeza futura.'}

    def _evidence_level(self,n):
        lv=self.cfg.get('evidence_levels',{})
        a=int(lv.get('initial',8)); m=int(lv.get('moderate',20)); solid=int(lv.get('solid',50))
        if n < a: return 'INSUFICIENTE'
        if n < m: return 'INICIAL'
        if n < solid: return 'MODERADA'
        return 'SÓLIDA'
    def _friction_pct(self,sm):
        fm=self.cfg.get('friction_model',{})
        if not fm.get('enabled',True): return 0.0
        pp=self.s.get('paper_portfolio',{})
        # Estimación conservadora PAPER de ida/vuelta para comparar señal bruta vs señal después de fricción.
        slip=float(pp.get('slippage_pct',0.05))*2
        comm=float(pp.get('commission_pct_round_trip',0.02))
        fx=float(fm.get('fx_buffer_pct_us',0.05)) if sm.get('currency')=='USD' else 0.0
        return slip+comm+fx
    def _calibration(self,samples,horizons):
        report={'updated_utc':self._now().isoformat(),'horizons':{},'guardrails':{'paper_only':True,'auto_strategy_change':False,'real_execution':False}}
        for h in horizons:
            hk=str(h); by_action={}
            for action in ('PAPER BUY','ESPERAR SETUP','ESTUDIAR','OBSERVAR','PAUSAR'):
                gross=[]; net=[]; hits=[]
                for sm in samples:
                    if sm.get('action')!=action: continue
                    o=sm.get('outcomes',{}).get(hk)
                    if not o: continue
                    r=float(o.get('return_pct',0)); gross.append(r)
                    # Para una entrada hipotética, el retorno neto descuenta fricción PAPER estimada.
                    net.append(r-self._friction_pct(sm)); hits.append(1 if float(o.get('direction_score',0))>0 else 0)
                n=len(gross)
                by_action[action]={'n':n,'evidence':self._evidence_level(n),'avg_gross_return_pct':round(sum(gross)/n,3) if n else None,
                    'avg_net_after_friction_pct':round(sum(net)/n,3) if n else None,'decision_consistency_pct':round(sum(hits)/n*100,1) if n else None}
            report['horizons'][hk]=by_action
        # La calibración informa; no reescribe estrategias ni eleva el límite global del ajuste IA.
        report['friction']={'slippage_round_trip_pct':round(float(self.s.get('paper_portfolio',{}).get('slippage_pct',0.05))*2,3),
            'commission_round_trip_pct':float(self.s.get('paper_portfolio',{}).get('commission_pct_round_trip',0.02)),
            'fx_buffer_pct_us':float(self.cfg.get('friction_model',{}).get('fx_buffer_pct_us',0.05))}
        report['note']='Calibración PAPER: separa retorno bruto y retorno estimado después de fricción. Los niveles de evidencia describen tamaño de muestra, no probabilidad de ganar.'
        return report
    def calibration(self): return self._read(self.calibration_path,{'horizons':{},'friction':{},'guardrails':{}})

    def audit(self): return self._read(self.audit_path,{'by_symbol':{},'by_regime':{},'by_sector':{},'by_context':{},'guardrails':{}})
    def counterfactual(self): return self._read(self.counterfactual_path,{'counts':{},'action_comparison':{},'recent':[]})
    def _maturity_report(self,samples,horizons,stats,cal):
        total=max(1,len(samples)); rows=[]
        for h in horizons:
            hk=str(h); matured=sum(1 for sm in samples if hk in sm.get('outcomes',{}))
            rows.append({'minutes':h,'matured':matured,'pending':max(0,len(samples)-matured),'coverage_pct':round(matured/total*100,1) if samples else 0.0})
        h1=stats.get('60',{}).get('PAPER BUY',{}); h24=stats.get('1440',{}).get('PAPER BUY',{}); h5=stats.get('7200',{}).get('PAPER BUY',{})
        checks=[]
        for label,x in [('1H',h1),('1D',h24),('5D',h5)]:
            n=int(x.get('n') or 0); hit=x.get('decision_hit_rate_pct'); avg=x.get('avg_return_pct')
            checks.append({'horizon':label,'n':n,'hit_rate_pct':hit,'avg_return_pct':avg,'confidence':self._confidence(n)})
        mature_1d=int(h24.get('n') or 0); min_adj=int(self.cfg.get('min_samples_for_adjustment',30))
        ready=mature_1d>=min_adj
        return {'horizons':rows,'paper_buy_consistency':checks,'adjustment_ready':ready,'required_1d_paper_buy_samples':min_adj,
                'remaining_1d_paper_buy_samples':max(0,min_adj-mature_1d),'guardrail':'El aprendizaje sólo ajusta de forma acotada el score interno; no cambia pesos de estrategia ni habilita trading real.'}

    def _compute_adjustment(self,stats):
        h='1440'; st=stats.get(h,{}).get('PAPER BUY',{})
        n=int(st.get('n') or 0); mn=int(self.cfg.get('min_samples_for_adjustment',30)); cap=float(self.cfg.get('max_ai_adjustment_points',3))
        if n<mn:return 0.0
        hit=float(st.get('decision_hit_rate_pct') or 50); avg=float(st.get('avg_return_pct') or 0)
        # Base conservadora: consistencia direccional a 1 día.
        raw=(hit-50)/15*cap
        # V0.16.5: exige coherencia temporal. Si 1h contradice fuertemente 1d, reduce el ajuste.
        h1=stats.get('60',{}).get('PAPER BUY',{}); n1=int(h1.get('n') or 0)
        if n1>=mn:
            hit1=float(h1.get('decision_hit_rate_pct') or 50)
            if (hit-50)*(hit1-50)<0: raw*=0.5
        # Si el retorno bruto medio a 1d no acompaña la dirección del ajuste, también se atenúa.
        if raw>0 and avg<=0: raw*=0.5
        if raw<0 and avg>=0: raw*=0.5
        return round(max(-cap,min(cap,raw)),2)

    def adjustment(self):
        return float(self._read(self.summary_path,{}).get('ai_adjustment_points',0) or 0)
    def summary(self):
        return self._read(self.summary_path,{'total_samples':0,'stats':{},'ai_adjustment_points':0,'mode':'SHADOW_LEARNING','auto_change_strategy_weights':False})
    def samples(self,limit=100): return self._read(self.samples_path,[])[-int(limit):]
