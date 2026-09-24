from __future__ import annotations
import math

def _f(v, default=None):
    try:
        x=float(v); return x if math.isfinite(x) else default
    except Exception:return default

def _ret(close, bars):
    if close is None or len(close)<=bars:return None
    a=_f(close.iloc[-1]); b=_f(close.iloc[-1-bars])
    if a is None or b in (None,0):return None
    return round((a/b-1)*100,2)

def _trend_label(v):
    if v is None:return "sin datos"
    if v>=5:return "alcista fuerte"
    if v>=1:return "alcista"
    if v<=-5:return "bajista fuerte"
    if v<=-1:return "bajista"
    return "lateral"

def build_multihorizon(hist, row):
    close=hist["close"].astype(float) if hist is not None and not hist.empty else None
    rets={"1D":_ret(close,1),"1S":_ret(close,5),"1M":_ret(close,21),"3M":_ret(close,63),"6M":_ret(close,126),"1A":_ret(close,252)}
    available=[v for k,v in rets.items() if k in ("1M","3M","6M","1A") and v is not None]
    pos=sum(v>0 for v in available); neg=sum(v<0 for v in available)
    consensus="MIXTO"
    if available and pos/len(available)>=.75:consensus="ALCISTA"
    elif available and neg/len(available)>=.75:consensus="BAJISTA"
    px=_f(row.get("close") if hasattr(row,"get") else None)
    s20=_f(row.get("sma20") if hasattr(row,"get") else None); s50=_f(row.get("sma50") if hasattr(row,"get") else None)
    structure="NEUTRA"
    if px and s20 and s50:
        if px>s20>s50: structure="ALCISTA"
        elif px<s20<s50: structure="BAJISTA"
    return {"returns_pct":rets,"trend_labels":{k:_trend_label(v) for k,v in rets.items()},"consensus":consensus,"price_structure":structure}

def decision_analysis(x):
    mh=x.get("multi_horizon") or {}; rets=mh.get("returns_pct") or {}
    support=[]; against=[]
    if mh.get("consensus")=="ALCISTA": support.append("la mayoría de los horizontes de mediano/largo plazo son positivos")
    elif mh.get("consensus")=="BAJISTA": against.append("la mayoría de los horizontes de mediano/largo plazo son negativos")
    if mh.get("price_structure")=="ALCISTA": support.append("el precio mantiene estructura por encima de SMA20/SMA50")
    elif mh.get("price_structure")=="BAJISTA": against.append("el precio está por debajo de SMA20/SMA50")
    rv=_f(x.get("rel_volume")); rsi=_f(x.get("rsi14")); rs=_f(x.get("relative_strength_3m_pct"))
    if rv is not None and rv>=1.5:support.append(f"volumen relativo elevado ({rv:.2f}x)")
    if rs is not None:
        (support if rs>0 else against).append(f"fuerza relativa 3M vs benchmark {rs:+.1f}%")
    if rsi is not None and rsi>=75:support.append(f"momentum RSI14 alto ({rsi:.1f})")
    elif rsi is not None and rsi<45:against.append(f"momentum RSI14 débil ({rsi:.1f})")
    if x.get("validated_match"):support.append("el setup actual coincide con una estrategia históricamente validada")
    elif _f(x.get("validation_score"),0)>0:against.append("hay validación histórica, pero el setup actual aún no coincide")
    if _f(x.get("vulnerability_score"),0)>=70:against.append("la vulnerabilidad histórica es elevada")
    if _f(x.get("market_context_score"),50)>=60:support.append("el contexto de mercado es favorable")
    elif _f(x.get("market_context_score"),50)<40:against.append("el contexto de mercado es débil")
    action=x.get("ai_action","OBSERVAR")
    if action=="PAPER BUY": rationale="Las condiciones PAPER de entrada están alineadas y el setup validado está activo."
    elif action=="ESPERAR SETUP": rationale="La evidencia merece seguimiento, pero falta confirmación del setup validado; NEXUS no abre todavía."
    elif action=="PAUSAR": rationale="El riesgo/contexto supera los límites definidos; NEXUS pausa nuevas entradas PAPER."
    else:rationale="La evidencia actual no cumple todos los filtros necesarios para una entrada PAPER."
    return {"rationale":rationale,"support":support[:5],"against":against[:5],"returns_pct":rets,"consensus":mh.get("consensus","—"),"price_structure":mh.get("price_structure","—")}
