from pathlib import Path
import time
import pandas as pd
import yfinance as yf

class YFinanceProvider:
    def __init__(self, settings=None, root=None):
        if settings is None or root is None:
            # Fallback seguro para evitar NoneType si alguna parte del sistema
            # instancia el proveedor sin argumentos.
            from src.config.loader import load_settings, project_root
            if settings is None:
                settings = load_settings()
            if root is None:
                root = project_root()

        self.settings = settings
        self.root = Path(root)

    def _cache_path(self, symbol, period, interval):
        safe = (
            str(symbol)
            .replace("^", "IDX_")
            .replace("=", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )
        cache_dir = self.settings.get("storage", {}).get("cache_dir", "storage/cache")
        return self.root / cache_dir / f"{safe}_{period}_{interval}.csv"

    def _cache_minutes(self, interval):
        agent = self.settings.get("agent", {})
        if interval == "1d":
            return int(agent.get("cache_minutes_history", 60))
        return int(agent.get("cache_minutes_intraday", 5))

    def _read_cache(self, path, max_age_minutes):
        if not path.exists():
            return None
        try:
            age_minutes = (time.time() - path.stat().st_mtime) / 60.0
            if age_minutes > max_age_minutes:
                return None

            df = pd.read_csv(path, index_col=0, parse_dates=True)
            if df is None or df.empty:
                return None
            return df
        except Exception:
            return None

    def _download(self, symbol, period, interval):
        try:
            df = yf.download(
                symbol,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                threads=False
            )

            if df is None or df.empty:
                return pd.DataFrame()

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df.columns = [str(c).lower() for c in df.columns]
            return df.sort_index()

        except Exception:
            return pd.DataFrame()

    def get_bars(self, symbol, period, interval, fallback_symbols=None):
        candidates = [symbol]
        for s in (fallback_symbols or []):
            if s not in candidates:
                candidates.append(s)

        for candidate in candidates:
            path = self._cache_path(candidate, period, interval)
            path.parent.mkdir(parents=True, exist_ok=True)

            cached = self._read_cache(path, self._cache_minutes(interval))
            if cached is not None:
                return cached, candidate, True

            df = self._download(candidate, period, interval)
            if not df.empty:
                try:
                    df.to_csv(path)
                except Exception:
                    pass
                return df, candidate, False

        return pd.DataFrame(), symbol, False

    def get_usdmxn(self):
        df, _, _ = self.get_bars("USDMXN=X", "5d", "1h")
        if df is None or df.empty:
            return None
        return float(df.iloc[-1]["close"])


def get_live_price(self, symbol, fallback_symbols=None):
    """Best-effort latest Yahoo intraday price. Bypasses local cache."""
    candidates=[symbol]+[x for x in (fallback_symbols or []) if x!=symbol]
    for candidate in candidates:
        try:
            df=self._download(candidate,"1d","1m")
            if df is None or df.empty or "close" not in df.columns:
                df=self._download(candidate,"5d","5m")
            if df is not None and not df.empty and "close" in df.columns:
                v=float(df["close"].dropna().iloc[-1])
                ts=str(df.index[-1])
                return {"price":v,"resolved_symbol":candidate,"timestamp":ts}
        except Exception:
            pass
    return None
