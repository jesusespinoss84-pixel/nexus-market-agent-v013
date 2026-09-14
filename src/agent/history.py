import numpy as np

def pct_change_from(close,periods):
    if len(close)<=periods:return None
    a=float(close.iloc[-1]);b=float(close.iloc[-1-periods]);return None if b==0 else (a/b-1)*100

def ytd_return(close):
    if close.empty:return None
    try:
        year=close.index[-1].year;sub=close[close.index.year==year]
        return None if len(sub)<2 else (float(sub.iloc[-1])/float(sub.iloc[0])-1)*100
    except:return None

def max_drawdown(close):
    if close.empty:return None
    return float(((close/close.cummax())-1).min()*100)

def volatility30(close):
    r=close.pct_change().dropna().tail(30)
    return None if len(r)<10 else float(r.std()*np.sqrt(252)*100)

def historical_metrics(df):
    if df is None or df.empty:return {}
    c=df['close'].dropna()
    return {
      'ret_1d':pct_change_from(c,1),'ret_1w':pct_change_from(c,5),'ret_1m':pct_change_from(c,21),'ret_3m':pct_change_from(c,63),
      'ret_ytd':ytd_return(c),'ret_1y':pct_change_from(c,min(252,len(c)-1)) if len(c)>1 else None,
      'volatility_30d':volatility30(c),'max_drawdown_1y':max_drawdown(c)
    }

def viability_vulnerability(m):
    def v(k,d=0):return m.get(k) if m.get(k) is not None else d
    r1m,r3,r1y=v('ret_1m'),v('ret_3m'),v('ret_1y');vol=max(0,v('volatility_30d'));dd=abs(min(0,v('max_drawdown_1y')))
    momentum=max(-30,min(30,.30*r1m+.30*r3+.40*r1y));risk=min(100,.9*vol+1.1*dd)
    viability=50+momentum*.9-risk*.25;vulnerability=35+risk*.65-momentum*.5
    return round(max(0,min(100,viability)),1),round(max(0,min(100,vulnerability)),1)
