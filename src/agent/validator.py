from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
import itertools
import json
import re

import numpy as np
import pandas as pd

from src.config.loader import load_settings, project_root
from src.data.yfinance_provider import YFinanceProvider
from src.indicators.technical import add_indicators
from src.strategies.momentum_breakout import evaluate


def clamp(x):
    return round(max(0.0, min(100.0, float(x))), 1)


class SymbolValidator:
    """Valida la estrategia BUY de NEXUS por símbolo.

    - quick: rejilla reducida para el embudo automático.
    - full: rejilla completa del laboratorio (1,800 combinaciones por defecto).
    - guarda un resumen por símbolo para que la web y el agente usen la misma fuente.
    """

    def __init__(self, settings=None, provider=None):
        self.s = settings or load_settings()
        self.root = project_root()
        self.p = provider or YFinanceProvider(self.s, self.root)
        self.cfg = self.s.get("validation", {})
        self.sens = self.s.get("sensitivity", {})
        self.out_dir = self.root / self.s.get("storage", {}).get("validations_dir", "storage/validations")
        self.out_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe(symbol):
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", symbol)

    def summary_path(self, symbol):
        return self.out_dir / f"{self._safe(symbol)}.json"

    def csv_path(self, symbol):
        return self.out_dir / f"{self._safe(symbol)}.csv"

    def load(self, symbol):
        p = self.summary_path(symbol)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def is_fresh(self, summary):
        if not summary:
            return False
        try:
            t = datetime.fromisoformat(summary["generated_at_utc"])
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            max_h = float(self.cfg.get("cache_hours", 24))
            return datetime.now(timezone.utc) - t <= timedelta(hours=max_h)
        except Exception:
            return False

    def _metrics(self, rs):
        if not rs:
            return {"trades": 0, "pf": 0.0, "exp_r": 0.0, "win_pct": 0.0}
        a = np.asarray(rs, dtype=float)
        wins = a[a > 0]
        losses = a[a <= 0]
        gp = float(wins.sum()) if len(wins) else 0.0
        gl = abs(float(losses.sum())) if len(losses) else 0.0
        pf = gp / gl if gl > 0 else (5.0 if gp > 0 else 0.0)
        return {
            "trades": int(len(a)),
            "pf": round(float(pf), 3),
            "exp_r": round(float(a.mean()), 3),
            "win_pct": round(float((a > 0).mean() * 100), 2),
        }

    def _prepare(self, df):
        out = []
        for i in range(55, len(df) - 1):
            try:
                sig = evaluate(df.iloc[i], self.s)
                if sig["direction"] == "BUY":
                    out.append({
                        "i": i,
                        "score": int(sig["score"]),
                        "rsi": float(df.iloc[i]["rsi14"]),
                        "sma": float(df.iloc[i]["distance_sma20_pct"]),
                    })
            except Exception:
                pass
        return out

    def _simulate(self, df, cands, rsi_min, sma_min, score_min, stop_pct, target_pct, slip_pct):
        opens = df["open"].to_numpy(dtype=float)
        highs = df["high"].to_numpy(dtype=float)
        lows = df["low"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)
        rs, next_allowed = [], 0
        commission = float(self.sens.get("commission_pct_round_trip", 0.02)) / 100.0
        max_bars = int(self.sens.get("max_bars_in_trade", 20))

        for c in cands:
            i = c["i"]
            if i < next_allowed or c["score"] < score_min or c["rsi"] < rsi_min or c["sma"] < sma_min:
                continue
            entry_i = i + 1
            if entry_i >= len(df):
                continue
            entry = opens[entry_i] * (1 + slip_pct / 100.0)
            stop = entry * (1 - stop_pct / 100.0)
            target = entry * (1 + target_pct / 100.0)
            risk = entry - stop
            if risk <= 0:
                continue
            last = min(entry_i + max_bars - 1, len(df) - 1)
            result, exit_i = None, last
            for j in range(entry_i, last + 1):
                if lows[j] <= stop:
                    result, exit_i = -1.0, j
                    break
                if highs[j] >= target:
                    result, exit_i = (target - entry) / risk, j
                    break
            if result is None:
                result = (closes[last] - entry) / risk
            result -= (entry * commission) / risk
            rs.append(result)
            next_allowed = max(i + 1, exit_i)
        return self._metrics(rs)

    def _grid(self, mode):
        if mode == "full":
            c = self.sens
        else:
            c = self.cfg.get("quick_grid", {})
        return list(itertools.product(
            c.get("rsi_values", [70, 75, 80]),
            c.get("sma20_distance_values", [1.0, 2.0, 3.0]),
            c.get("score_values", [65, 70, 75]),
            c.get("stop_values", [1.5, 2.0]),
            c.get("target_values", [3.0, 4.0, 5.0]),
            c.get("slippage_values", [0.05]),
        ))

    def _walk_forward(self, df, cands, best):
        folds = int(self.cfg.get("walk_forward_folds", 5))
        if folds < 2 or len(df) < 200:
            return {"positive_folds": 0, "folds": folds, "label": f"0/{folds}", "details": []}
        edges = np.linspace(55, len(df) - 1, folds + 1).astype(int)
        details, positive = [], 0
        for k in range(folds):
            lo, hi = int(edges[k]), int(edges[k + 1])
            fc = [c for c in cands if lo <= c["i"] < hi]
            m = self._simulate(
                df, fc, best["rsi_min"], best["sma20_distance_min"], best["score_min"],
                best["stop_pct"], best["target_pct"], best["slippage_pct"]
            )
            ok = m["trades"] >= max(3, int(self.sens.get("min_trades_for_stability", 20) / folds / 2)) and m["exp_r"] > 0
            positive += int(ok)
            details.append({"fold": k + 1, **m, "positive": bool(ok)})
        return {"positive_folds": positive, "folds": folds, "label": f"{positive}/{folds}", "details": details}

    def _robustness(self, stable, best, wf):
        if stable.empty:
            return 0.0
        profitable = float((stable["exp_r"] > 0).mean())
        pf_good = float((stable["pf"] >= 1.2).mean())
        wf_ratio = wf["positive_folds"] / max(1, wf["folds"])
        top_pf = min(float(best["pf"]), 3.0) / 3.0
        top_exp = min(max(float(best["exp_r"]), 0.0), 0.75) / 0.75
        return clamp(25 * profitable + 15 * pf_good + 20 * wf_ratio + 20 * top_pf + 20 * top_exp)

    def _validation_score(self, robustness, best, wf):
        wf_ratio = wf["positive_folds"] / max(1, wf["folds"])
        return clamp(
            0.45 * robustness
            + 20 * min(float(best.get("pf", 0)), 2.5) / 2.5
            + 20 * min(max(float(best.get("exp_r", 0)), 0), 0.5) / 0.5
            + 15 * wf_ratio
        )

    def validate(self, asset, mode="quick", force=False, progress=None):
        symbol = asset["symbol"] if isinstance(asset, dict) else str(asset)
        a = asset if isinstance(asset, dict) else {"symbol": symbol, "fallback_symbols": []}
        old = self.load(symbol)
        if not force and self.is_fresh(old) and (old.get("mode") == "full" or mode == "quick"):
            return old

        period = self.cfg.get("period", self.sens.get("period", "2y"))
        interval = self.cfg.get("interval", self.sens.get("interval", "1h"))
        df, resolved, cached = self.p.get_bars(symbol, period, interval, a.get("fallback_symbols", []))
        if df is None or df.empty or len(df) < 100:
            out = {
                "version": self.s["app"]["version"], "symbol": symbol, "resolved_symbol": resolved,
                "status": "NO_DATA", "mode": mode, "validation_score": 0.0,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(), "top10": []
            }
            self.summary_path(symbol).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            return out

        df = add_indicators(df)
        cands = self._prepare(df)
        combos = self._grid(mode)
        rows = []
        total = len(combos)
        for n, vals in enumerate(combos, 1):
            rsi, sma, score, stop, target, slip = vals
            rows.append({
                "rsi_min": rsi, "sma20_distance_min": sma, "score_min": score,
                "stop_pct": stop, "target_pct": target, "slippage_pct": slip,
                **self._simulate(df, cands, rsi, sma, score, stop, target, slip)
            })
            if progress and (n == 1 or n % 100 == 0 or n == total):
                progress(n, total)

        outdf = pd.DataFrame(rows)
        min_trades = int(self.cfg.get("min_trades", self.sens.get("min_trades_for_stability", 20)))
        stable = outdf[outdf["trades"] >= min_trades].copy()
        if not stable.empty:
            stable["quality"] = stable["exp_r"].clip(lower=-2) * stable["pf"].clip(upper=5) * np.log1p(stable["trades"])
            stable = stable.sort_values(["quality", "trades"], ascending=[False, False])
            best = stable.iloc[0].to_dict()
            wf = self._walk_forward(df, cands, best)
            robustness = self._robustness(stable, best, wf)
            val_score = self._validation_score(robustness, best, wf)
        else:
            best, wf, robustness, val_score = {}, {"positive_folds": 0, "folds": 5, "label": "0/5", "details": []}, 0.0, 0.0

        thresholds = self.cfg.get("validated_thresholds", {})
        passed = bool(
            best
            and int(best.get("trades", 0)) >= int(thresholds.get("min_trades", min_trades))
            and float(best.get("pf", 0)) >= float(thresholds.get("min_pf", 1.25))
            and float(best.get("exp_r", 0)) >= float(thresholds.get("min_exp_r", 0.10))
            and robustness >= float(thresholds.get("min_robustness", 60))
            and wf["positive_folds"] >= int(thresholds.get("min_positive_folds", 3))
        )

        result = {
            "version": self.s["app"]["version"],
            "symbol": symbol,
            "resolved_symbol": resolved,
            "mode": mode,
            "status": "OK" if best else "INSUFFICIENT_SAMPLE",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_cached": bool(cached),
            "bars": int(len(df)),
            "buy_candidates": int(len(cands)),
            "tested_combinations": int(len(outdf)),
            "stable_combinations": int(len(stable)),
            "best": best,
            "top10": stable.head(10).replace({np.nan: None}).to_dict(orient="records") if not stable.empty else [],
            "walk_forward": wf,
            "robustness_score": robustness,
            "validation_score": val_score,
            "validated": passed,
        }
        outdf.to_csv(self.csv_path(symbol), index=False, encoding="utf-8-sig")
        self.summary_path(symbol).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result

    def current_setup_matches(self, validation, signal_score, row):
        if not validation or not validation.get("validated") or not validation.get("best"):
            return False
        b = validation["best"]
        try:
            return (
                int(signal_score) >= int(b["score_min"])
                and float(row["rsi14"]) >= float(b["rsi_min"])
                and float(row["distance_sma20_pct"]) >= float(b["sma20_distance_min"])
            )
        except Exception:
            return False
