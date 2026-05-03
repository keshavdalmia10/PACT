"""Portfolio Manager Agent (spec §4.1, §5).

Aggregates per-instrument views from the 6 specialists according to the
active coordination protocol, then emits final target weights via the
portfolio construction layer (§5).
"""

from __future__ import annotations

from datetime import date

from agents.base_agent import AgentDecision, BaseAgent, InstrumentView


class PortfolioManagerAgent(BaseAgent):
    name = "portfolio_manager"

    def set_inputs(self, specialist_decisions: list[AgentDecision]) -> None:
        self._specialists = specialist_decisions

    def extract_factors(self, as_of: date) -> dict[str, dict[str, float]]:
        specs: list[AgentDecision] = getattr(self, "_specialists", [])
        out: dict[str, dict[str, float]] = {}
        for sym in self.universe:
            f: dict[str, float] = {}
            for d in specs:
                v = d.view_for(sym)
                if v is None:
                    continue
                f[f"{d.agent_name}_dir"] = float(v.direction)
                f[f"{d.agent_name}_conv"] = v.conviction
            out[sym] = f
        return out

    def decide(
        self,
        as_of: date,
        factors_by_instrument: dict[str, dict[str, float]],
    ) -> list[InstrumentView]:
        # Default conviction-weighted average. Coordination protocols may
        # override this by injecting a different aggregator function.
        views: list[InstrumentView] = []
        for sym, f in factors_by_instrument.items():
            num = 0.0
            den = 0.0
            for k, v in f.items():
                if not k.endswith("_dir"):
                    continue
                conv_key = k.replace("_dir", "_conv")
                w = f.get(conv_key, 0.0)
                # Risk agent contributes through scaling, not signed direction.
                if k.startswith("risk_correlation"):
                    continue
                num += v * w
                den += w
            score = (num / den) if den > 0 else 0.0
            direction = int(1 if score > 0.1 else (-1 if score < -0.1 else 0))
            views.append(
                InstrumentView(
                    instrument=sym,
                    direction=direction,
                    conviction=min(abs(score), 1.0),
                    horizon="1w",
                    factors={**f, "aggregated_score": score},
                    rationale=f"PM aggregate score={score:.3f}",
                )
            )
        return views
