import itertools
import json
import numpy as np
import pandas as pd

from src.config.loader import load_settings, project_root
from src.data.yfinance_provider import YFinanceProvider
from src.indicators.technical import add_indicators
from src.strategies.momentum_breakout import evaluate
from datetime import datetime, timezone


class SensitivityEngine:
    def __init__(self):
        self.s = load_settings()
        self.c = self.s["sensitivity"]
        self.root = project_root()
        self.p = YFinanceProvider(self.s, self.root)

    def metrics(self, rs):
        if not rs:
            return {"trades": 0, "pf": 0.0, "exp_r": 0.0, "win_pct": 0.0}

        a = np.array(rs, dtype=float)
        wins = a[a > 0]
        losses = a[a <= 0]

        gross_profit = float(wins.sum()) if len(wins) else 0.0
        gross_loss = abs(float(losses.sum())) if len(losses) else 0.0
        pf = gross_profit / gross_loss if gross_loss > 0 else 999.0

        return {
            "trades": int(len(a)),
            "pf": round(float(pf), 3),
            "exp_r": round(float(a.mean()), 3),
            "win_pct": round(float((a > 0).mean() * 100), 2),
        }

    def prepare(self, df):
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

    def simulate(self, df, cands, rsi_min, sma_min, score_min, stop_pct, target_pct, slip_pct):
        opens = df["open"].to_numpy(dtype=float)
        highs = df["high"].to_numpy(dtype=float)
        lows = df["low"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)

        rs = []
        next_allowed = 0
        commission = float(self.c["commission_pct_round_trip"]) / 100.0
        max_bars = int(self.c["max_bars_in_trade"])

        for c in cands:
            i = c["i"]

            if i < next_allowed:
                continue
            if c["score"] < score_min:
                continue
            if c["rsi"] < rsi_min:
                continue
            if c["sma"] < sma_min:
                continue

            entry_i = i + 1
            entry = opens[entry_i] * (1 + slip_pct / 100.0)
            stop = entry * (1 - stop_pct / 100.0)
            target = entry * (1 + target_pct / 100.0)
            last = min(entry_i + max_bars - 1, len(df) - 1)

            result = None
            exit_i = last

            for j in range(entry_i, last + 1):
                if lows[j] <= stop:
                    result = -1.0
                    exit_i = j
                    break

                if highs[j] >= target:
                    result = (target - entry) / (entry - stop)
                    exit_i = j
                    break

            if result is None:
                result = (closes[last] - entry) / (entry - stop)

            commission_r = (entry * commission) / (entry - stop)
            rs.append(result - commission_r)
            next_allowed = max(i + 1, exit_i)

        return self.metrics(rs)

    def run(self):
        print()
        print("================================================")
        print(" NEXUS MARKET AGENT V0.10.4 - SENSIBILIDAD")
        print("================================================")
        print("Descargando/cargando datos de NVDA...")

        df, resolved, cached = self.p.get_bars(
            self.c["symbol"],
            self.c["period"],
            self.c["interval"]
        )

        if df is None or df.empty:
            print("ERROR: no se pudieron cargar datos para la sensibilidad.")
            return

        print(f"Ticker usado: {resolved}")
        print(f"Fuente: {'CACHE LOCAL' if cached else 'DESCARGA'}")
        print(f"Velas: {len(df)}")

        df = add_indicators(df)
        cands = self.prepare(df)

        print(f"Señales BUY precalculadas: {len(cands)}")

        combos = list(itertools.product(
            self.c["rsi_values"],
            self.c["sma20_distance_values"],
            self.c["score_values"],
            self.c["stop_values"],
            self.c["target_values"],
            self.c["slippage_values"],
        ))

        print(f"Combinaciones: {len(combos)}")
        rows = []

        for n, vals in enumerate(combos, start=1):
            rsi_min, sma_min, score_min, stop, target, slip = vals

            rows.append({
                "rsi_min": rsi_min,
                "sma20_distance_min": sma_min,
                "score_min": score_min,
                "stop_pct": stop,
                "target_pct": target,
                "slippage_pct": slip,
                **self.simulate(
                    df, cands,
                    rsi_min, sma_min, score_min,
                    stop, target, slip
                )
            })

            if n == 1 or n % 100 == 0 or n == len(combos):
                print(f"[{n}/{len(combos)}] {n/len(combos)*100:.1f}%")

        out = pd.DataFrame(rows)

        out_path = self.root / self.s["storage"]["sensitivity"]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(out_path, index=False, encoding="utf-8-sig")

        stable = out[
            out["trades"] >= int(self.c["min_trades_for_stability"])
        ].copy()

        stable["quality"] = stable["exp_r"] * stable["pf"].clip(upper=5)
        stable = stable.sort_values(
            ["quality", "trades"],
            ascending=[False, False]
        )

        summary = {
            "version": self.s["app"]["version"],
            "symbol": self.c["symbol"],
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "tested_combinations": int(len(out)),
            "stable_combinations": int(len(stable)),
            "top10": stable.head(10).to_dict(orient="records"),
        }

        summary_path = self.root / self.s["storage"]["sensitivity_summary"]
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        print()
        print("================================================")
        print(" SENSIBILIDAD TERMINADA CORRECTAMENTE")
        print("================================================")
        print(f"Probadas: {len(out)}")
        print(f"Con muestra suficiente: {len(stable)}")
        print("Guardado en:")
        print(out_path)
        print("Resumen guardado en:")
        print(summary_path)
