import math
def evaluate(row,settings):
    lp=sp=0;c=float(row['close']);s20=float(row['sma20']);s50=float(row['sma50']);r=float(row['rsi14']);rv=float(row['rel_volume']);h=float(row['high20_prev']);l=float(row['low20_prev'])
    if c>s20>s50:lp+=25
    elif c<s20<s50:sp+=25
    if c>h:lp+=30
    if c<l:sp+=30
    if math.isfinite(rv) and rv>=float(settings['agent']['min_relative_volume']):lp+=20;sp+=20
    if 55<=r<=75:lp+=15
    elif 25<=r<=45:sp+=15
    if c>s20:lp+=10
    elif c<s20:sp+=10
    return {'direction':'BUY' if lp>=sp else 'SELL','score':min(max(lp,sp),100)}
