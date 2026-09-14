from datetime import datetime, timezone
import math
import pandas as pd
import yfinance as yf

def _finite(v, default=0.0):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default

def _ret(df, n):
    if df is None or df.empty or len(df) <= n: return None
    a=_finite(df["close"].iloc[-1], None); b=_finite(df["close"].iloc[-1-n], None)
    if a is None or b in (None,0): return None
    return (a/b-1)*100

def _score_center(v, scale=10.0):
    if v is None:return 50.0
    return max(0.0,min(100.0,50.0+float(v)*scale))

def _news_sentiment(items):
    # Lightweight headline polarity: transparent, intentionally low weight/informational.
    pos=("beat","beats","growth","record","upgrade","raises","strong","profit","surge","gain","expands","approval")
    neg=("miss","misses","downgrade","cuts","weak","loss","lawsuit","probe","decline","fall","warning","recall")
    vals=[]; headlines=[]
    for x in (items or [])[:12]:
        c=x.get("content",x) if isinstance(x,dict) else {}
        title=(c.get("title") or c.get("headline") or "").strip()
        if not title: continue
        t=title.lower(); p=sum(w in t for w in pos); n=sum(w in t for w in neg)
        vals.append(p-n); headlines.append(title)
    if not vals:return 50.0,headlines[:5]
    raw=sum(vals)/max(1,len(vals))
    return max(0,min(100,50+raw*15)),headlines[:5]

class MarketIntelligence:
    def __init__(self, settings, provider):
        self.s=settings; self.p=provider

    def benchmark(self, asset):
        return asset.get("comparison_benchmark") or ("^GSPC" if asset.get("market")=="USA" else "^MXX")

    def analyze(self, asset, hist):
        bm=self.benchmark(asset)
        bdf,_,_=self.p.get_bars(bm,"1y","1d")
        rs_asset=_ret(hist,63); rs_bm=_ret(bdf,63)
        rel=None if rs_asset is None or rs_bm is None else rs_asset-rs_bm
        rel_score=_score_center(rel,4.0)

        vol_ratio=None
        try:
            vols=hist["volume"].astype(float)
            base=float(vols.iloc[-21:-1].mean())
            vol_ratio=float(vols.iloc[-1]/base) if base>0 else None
        except Exception: pass
        volume_score=50 if vol_ratio is None else max(0,min(100,50+(vol_ratio-1)*35))

        try:
            r=hist["close"].pct_change().dropna().tail(30)
            vol30=float(r.std()*math.sqrt(252)*100)
        except Exception: vol30=None
        volatility_score=50 if vol30 is None else max(0,min(100,80-vol30))

        sector_score=rel_score
        earnings_days=None; news_score=50.0; headlines=[]
        try:
            t=yf.Ticker(asset["symbol"])
            cal=t.calendar
            dates=[]
            if isinstance(cal,dict):
                dates=cal.get("Earnings Date") or cal.get("EarningsDate") or []
            elif hasattr(cal,"index"):
                for key in ("Earnings Date","EarningsDate"):
                    if key in cal.index:
                        v=cal.loc[key]
                        dates=list(v.values) if hasattr(v,"values") else [v]
            now=pd.Timestamp.now(tz="UTC")
            future=[]
            for d in dates:
                try:
                    ts=pd.Timestamp(d)
                    if ts.tzinfo is None:ts=ts.tz_localize("UTC")
                    else:ts=ts.tz_convert("UTC")
                    dd=(ts-now).days
                    if dd>=0:future.append(dd)
                except Exception: pass
            if future:earnings_days=min(future)
            news_score,headlines=_news_sentiment(t.news)
        except Exception:
            pass

        earnings_score=50.0
        if earnings_days is not None:
            if earnings_days <= 3: earnings_score=35.0
            elif earnings_days <= 7: earnings_score=42.0
            elif earnings_days <= 14: earnings_score=47.0
            else: earnings_score=52.0

        cfg=self.s.get("market_intelligence",{})
        w={
          "sector":float(cfg.get("sector_weight",.30)),
          "relative":float(cfg.get("relative_strength_weight",.30)),
          "volume":float(cfg.get("volume_weight",.15)),
          "volatility":float(cfg.get("volatility_weight",.15)),
          "earnings":float(cfg.get("earnings_weight",.10)),
        }
        total=sum(w.values()) or 1
        score=(sector_score*w["sector"]+rel_score*w["relative"]+volume_score*w["volume"]+
               volatility_score*w["volatility"]+earnings_score*w["earnings"])/total
        return {
          "sector":asset.get("sector","—"),"industry":asset.get("industry","—"),
          "comparison_benchmark":bm,
          "relative_strength_3m_pct":None if rel is None else round(rel,2),
          "relative_strength_score":round(rel_score,1),
          "abnormal_volume_ratio":None if vol_ratio is None else round(vol_ratio,2),
          "volume_context_score":round(volume_score,1),
          "volatility_30d_live":None if vol30 is None else round(vol30,2),
          "volatility_context_score":round(volatility_score,1),
          "earnings_days":earnings_days,"earnings_context_score":round(earnings_score,1),
          "news_sentiment_score":round(news_score,1),"news_headlines":headlines,
          "market_intelligence_score":round(score,1),
          "updated_at":datetime.now(timezone.utc).isoformat()
        }
