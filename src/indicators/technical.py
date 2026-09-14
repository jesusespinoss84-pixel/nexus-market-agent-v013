import numpy as np

def rsi(s,p=14):
    d=s.diff();g=d.clip(lower=0).rolling(p).mean();l=(-d.clip(upper=0)).rolling(p).mean();rs=g/l.replace(0,np.nan);return 100-(100/(1+rs))
def add_indicators(df):
    o=df.copy();o['sma20']=o['close'].rolling(20).mean();o['sma50']=o['close'].rolling(50).mean();o['rsi14']=rsi(o['close'])
    o['rel_volume']=o['volume']/o['volume'].shift(1).rolling(20,min_periods=3).mean();o['high20_prev']=o['high'].shift(1).rolling(20).max();o['low20_prev']=o['low'].shift(1).rolling(20).min();o['distance_sma20_pct']=((o['close']-o['sma20'])/o['sma20'])*100
    return o
