import json
from datetime import datetime, timezone
from src.config.loader import project_root

class RiskGovernor:
    def __init__(self,s):
        self.s=s; self.cfg=s.get("risk_governor",{}); self.root=project_root()
        st=s.get("storage",{}); self.path=self.root/st.get("risk_governor","storage/risk_governor.json")
        self.stress_path=self.root/st.get("stress_test","storage/stress_test.json")
    def _write(self,p,o):
        p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+".tmp")
        t.write_text(json.dumps(o,indent=2,ensure_ascii=False),encoding="utf-8"); t.replace(p)
    def _curve(self):
        try:return json.loads((self.root/self.s["storage"]["equity_curve"]).read_text(encoding="utf-8"))
        except:return []
    def evaluate(self,ps,rows=None):
        start=float(ps.get("starting_cash_mxn") or self.s["paper_portfolio"]["starting_cash_mxn"])
        eq=float(ps.get("equity_mxn",start) or start); pos=ps.get("positions",[]) or []
        exp=sum(float(x.get("market_value_mxn",0) or 0) for x in pos); exp_pct=exp/eq*100 if eq else 100
        curve=self._curve(); peak=max([float(x.get("equity_mxn",eq) or eq) for x in curve]+[eq])
        dd=max(0,(peak-eq)/peak*100) if peak else 0
        today=datetime.now(timezone.utc).date().isoformat()
        vals=[float(x.get("equity_mxn",eq) or eq) for x in curve if str(x.get("t",""))[:10]==today]
        day0=vals[0] if vals else start; dl=max(0,(day0-eq)/day0*100) if day0 else 0
        amap={r.get("symbol"):r for r in (rows or [])}; sectors={}
        for x in pos:
            sec=amap.get(x.get("symbol"),{}).get("sector","Sin sector")
            sectors[sec]=sectors.get(sec,0)+float(x.get("market_value_mxn",0) or 0)
        secpct={k:round(v/eq*100,2) if eq else 0 for k,v in sectors.items()}; mx=max(secpct.values(),default=0)
        c=self.cfg; level="NORMAL"; reasons=[]
        if dl>=float(c.get("daily_loss_pause_pct",4)) or dd>=float(c.get("drawdown_pause_pct",8)):
            level="PAUSA"; reasons.append("límite de pérdida/drawdown PAPER")
        elif dl>=float(c.get("daily_loss_defensive_pct",2.5)) or dd>=float(c.get("drawdown_defensive_pct",5)):
            level="DEFENSIVO"; reasons.append("deterioro de equity PAPER")
        elif dl>=float(c.get("daily_loss_caution_pct",1.5)) or dd>=float(c.get("drawdown_caution_pct",3)):
            level="PRECAUCIÓN"; reasons.append("pérdida/drawdown PAPER en vigilancia")
        if exp_pct>=float(c.get("max_total_exposure_pct",70)) or mx>=float(c.get("max_sector_exposure_pct",40)):
            if level=="NORMAL":level="PRECAUCIÓN"
            reasons.append("concentración/exposición PAPER elevada")
        block=(level=="PAUSA" and c.get("block_new_entries_in_pause",True)) or (level=="DEFENSIVO" and c.get("block_new_entries_in_defensive",True))
        o={"updated_utc":datetime.now(timezone.utc).isoformat(),"paper_only":True,"level":level,"block_new_entries":bool(block),
           "equity_mxn":round(eq,2),"exposure_pct":round(exp_pct,2),"daily_loss_pct":round(dl,2),"drawdown_pct":round(dd,2),
           "sector_exposure_pct":secpct,"max_sector_exposure_pct":round(mx,2),"open_positions":len(pos),
           "reasons":reasons or ["límites PAPER dentro de rango"]}
        self._write(self.path,o); return o
    def stress_test(self,ps,rows=None):
        eq=float(ps.get("equity_mxn",0) or 0); cash=float(ps.get("cash_mxn",0) or 0); pos=ps.get("positions",[]) or []; arr=[]
        for sc in self.cfg.get("stress_scenarios",[]):
            shock=float(sc.get("shock_pct",0))/100; fx=float(sc.get("fx_shock_pct",0))/100; mult=float(sc.get("slippage_multiplier",1))
            mv=0
            for x in pos:
                v=float(x.get("market_value_mxn",0) or 0)*(1+shock)
                if x.get("currency")=="USD":v*=1+fx
                mv+=max(0,v)
            friction=sum(float(x.get("market_value_mxn",0) or 0) for x in pos)*float(self.s["paper_portfolio"].get("slippage_pct",.05))/100*max(0,mult-1)
            stressed=max(0,cash+mv-friction); loss=eq-stressed
            arr.append({"name":sc.get("name"),"equity_stressed_mxn":round(stressed,2),"loss_mxn":round(loss,2),
                        "loss_pct":round(loss/eq*100,2) if eq else 0,"shock_pct":sc.get("shock_pct"),
                        "fx_shock_pct":sc.get("fx_shock_pct",0),"slippage_multiplier":mult})
        o={"updated_utc":datetime.now(timezone.utc).isoformat(),"paper_only":True,"scenarios":arr}; self._write(self.stress_path,o); return o
