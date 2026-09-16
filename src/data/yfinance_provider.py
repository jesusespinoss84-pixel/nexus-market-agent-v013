from pathlib import Path
import json
import logging
import time
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

# Evita que yfinance inunde los logs de Render con errores internos de crumb.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


class YFinanceProvider:
    """Proveedor Yahoo robusto para NEXUS.

    FIX V0.16.3:
    - Intenta primero el endpoint chart de Yahoo, que no depende del crumb de yfinance.
    - yfinance queda como respaldo.
    - Circuit breaker temporal tras fallos para no repetir 401 en bucle.
    - Puede servir cache vencido de forma controlada si Yahoo está temporalmente caído.
    - get_live_price vuelve a ser un método real de la clase.
    """

    def __init__(self, settings=None, root=None):
        if settings is None or root is None:
            from src.config.loader import load_settings, project_root
            if settings is None:
                settings = load_settings()
            if root is None:
                root = project_root()

        self.settings = settings
        self.root = Path(root)
        provider_cfg = self.settings.get("provider", {}) or {}
        self.timeout = int(provider_cfg.get("http_timeout_seconds", 12))
        self.cooldown_seconds = int(provider_cfg.get("failure_cooldown_seconds", 900))
        self.stale_intraday_minutes = int(provider_cfg.get("stale_intraday_minutes", 1440))
        self.stale_history_minutes = int(provider_cfg.get("stale_history_minutes", 10080))
        self._failed_until = {}

    def _cache_path(self, symbol, period, interval):
        safe = (str(symbol).replace("^", "IDX_").replace("=", "_")
                .replace("/", "_").replace("\\", "_"))
        cache_dir = self.settings.get("storage", {}).get("cache_dir", "storage/cache")
        return self.root / cache_dir / f"{safe}_{period}_{interval}.csv"

    def _cache_minutes(self, interval):
        agent = self.settings.get("agent", {})
        if interval == "1d":
            return int(agent.get("cache_minutes_history", 60))
        return int(agent.get("cache_minutes_intraday", 5))

    def _read_cache(self, path, max_age_minutes=None):
        if not path.exists():
            return None
        try:
            if max_age_minutes is not None:
                age_minutes = (time.time() - path.stat().st_mtime) / 60.0
                if age_minutes > max_age_minutes:
                    return None
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            if df is None or df.empty:
                return None
            return df
        except Exception:
            return None

    def _normalize(self, df):
        if df is None or df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]
        return df.sort_index()

    def _chart_download(self, symbol, period, interval):
        """Yahoo chart API: evita el flujo cookie/crumb que provoca Invalid Crumb."""
        try:
            params = urlencode({
                "range": period,
                "interval": interval,
                "includePrePost": "false",
                "events": "div,splits",
            })
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(str(symbol), safe='')}?{params}"
            req = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; NEXUS-Market-Agent/0.16.3)",
                "Accept": "application/json,text/plain,*/*",
                "Connection": "close",
            })
            with urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))

            result = ((payload.get("chart") or {}).get("result") or [])
            if not result:
                return pd.DataFrame()
            item = result[0]
            stamps = item.get("timestamp") or []
            quotes = (((item.get("indicators") or {}).get("quote") or [{}])[0])
            adj = (((item.get("indicators") or {}).get("adjclose") or [{}])[0]).get("adjclose")
            if not stamps or not quotes:
                return pd.DataFrame()

            n = len(stamps)
            def vals(name):
                v = quotes.get(name) or []
                return list(v) + [None] * max(0, n - len(v))

            data = {
                "open": vals("open")[:n],
                "high": vals("high")[:n],
                "low": vals("low")[:n],
                "close": vals("close")[:n],
                "volume": vals("volume")[:n],
            }
            if adj and len(adj) == n:
                data["adj close"] = adj
            idx = pd.to_datetime(stamps, unit="s", utc=True)
            df = pd.DataFrame(data, index=idx)
            df = df.dropna(subset=["close"])
            return self._normalize(df)
        except Exception:
            return pd.DataFrame()

    def _yfinance_download(self, symbol, period, interval):
        try:
            df = yf.download(symbol, period=period, interval=interval,
                             progress=False, auto_adjust=True, threads=False)
            return self._normalize(df)
        except Exception:
            return pd.DataFrame()

    def _download(self, symbol, period, interval):
        # Si Yahoo ya falló recientemente para esta combinación, no lo golpeamos en bucle.
        key = (str(symbol), str(period), str(interval))
        if time.time() < self._failed_until.get(key, 0):
            return pd.DataFrame()

        # Primero chart API sin crumb; yfinance sólo como segundo intento.
        df = self._chart_download(symbol, period, interval)
        if df.empty:
            df = self._yfinance_download(symbol, period, interval)

        if df.empty:
            self._failed_until[key] = time.time() + self.cooldown_seconds
        else:
            self._failed_until.pop(key, None)
        return df

    def get_bars(self, symbol, period, interval, fallback_symbols=None):
        candidates = [symbol]
        for s in (fallback_symbols or []):
            if s not in candidates:
                candidates.append(s)

        stale_candidates = []
        for candidate in candidates:
            path = self._cache_path(candidate, period, interval)
            path.parent.mkdir(parents=True, exist_ok=True)

            cached = self._read_cache(path, self._cache_minutes(interval))
            if cached is not None:
                return cached, candidate, True

            stale_limit = self.stale_history_minutes if interval == "1d" else self.stale_intraday_minutes
            stale = self._read_cache(path, stale_limit)
            if stale is not None:
                stale_candidates.append((stale, candidate))

            df = self._download(candidate, period, interval)
            if not df.empty:
                try:
                    df.to_csv(path)
                except Exception:
                    pass
                return df, candidate, False

        # Degradación segura: preferimos datos cacheados identificables antes que vacío total.
        if stale_candidates:
            df, candidate = stale_candidates[0]
            return df, candidate, True
        return pd.DataFrame(), symbol, False

    def get_usdmxn(self):
        df, _, _ = self.get_bars("USDMXN=X", "5d", "1h")
        if df is None or df.empty or "close" not in df.columns:
            return None
        return float(df["close"].dropna().iloc[-1])

    def get_live_price(self, symbol, fallback_symbols=None):
        """Última marca best-effort, con cache corto y fallback 5m."""
        candidates = [symbol] + [x for x in (fallback_symbols or []) if x != symbol]
        for candidate in candidates:
            # Cache específico LIVE: evita consultar Yahoo cada pocos segundos.
            path = self._cache_path(candidate, "1d", "1m")
            path.parent.mkdir(parents=True, exist_ok=True)
            cached = self._read_cache(path, 2)
            if cached is not None and "close" in cached.columns:
                close = cached["close"].dropna()
                if not close.empty:
                    return {"price": float(close.iloc[-1]), "resolved_symbol": candidate,
                            "timestamp": str(cached.index[-1]), "cached": True}

            df = self._download(candidate, "1d", "1m")
            if df.empty or "close" not in df.columns:
                df = self._download(candidate, "5d", "5m")
            if df is not None and not df.empty and "close" in df.columns:
                close = df["close"].dropna()
                if close.empty:
                    continue
                try:
                    df.to_csv(path)
                except Exception:
                    pass
                return {"price": float(close.iloc[-1]), "resolved_symbol": candidate,
                        "timestamp": str(df.index[-1]), "cached": False}

            # Último recurso: cache stale de hasta 24 h, marcado explícitamente.
            stale = self._read_cache(path, self.stale_intraday_minutes)
            if stale is not None and "close" in stale.columns:
                close = stale["close"].dropna()
                if not close.empty:
                    return {"price": float(close.iloc[-1]), "resolved_symbol": candidate,
                            "timestamp": str(stale.index[-1]), "cached": True, "stale": True}
        return None
