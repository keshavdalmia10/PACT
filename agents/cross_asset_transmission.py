"""Cross-Asset Transmission Agent (spec §4.1).

Reads outputs from Macro Regime + Narrative/Event and reasons about
transmission chains (e.g. oil shock → inflation → 10y yield → IEF short).
Adjusts per-instrument views.
"""

from __future__ import annotations

from datetime import date

from agents.base_agent import AgentDecision, BaseAgent, InstrumentView


class CrossAssetTransmissionAgent(BaseAgent):
    name = "cross_asset_transmission"

    def set_upstream(self, macro: AgentDecision, narrative: AgentDecision) -> None:
        self._macro = macro
        self._narrative = narrative

    def extract_factors(self, as_of: date) -> dict[str, dict[str, float]]:
        macro = getattr(self, "_macro", None)
        narrative = getattr(self, "_narrative", None)
        out: dict[str, dict[str, float]] = {}
        for sym in self.universe:
            f = {}
            if macro is not None:
                v = macro.view_for(sym)
                if v:
                    f["macro_dir"] = float(v.direction)
                    f["macro_conv"] = v.conviction
            if narrative is not None:
                v = narrative.view_for(sym)
                if v:
                    f["narr_dir"] = float(v.direction)
                    f["narr_conv"] = v.conviction
            out[sym] = f
        return out

    def decide(
        self,
        as_of: date,
        factors_by_instrument: dict[str, dict[str, float]],
    ) -> list[InstrumentView]:
        # Coherence check: if macro and narrative agree, double down; if they
        # disagree, soften. Non-trivial transmission logic belongs in the LLM
        # call; this is the deterministic anchor.
        views: list[InstrumentView] = []
        for sym, f in factors_by_instrument.items():
            md, mc = f.get("macro_dir", 0.0), f.get("macro_conv", 0.0)
            nd, nc = f.get("narr_dir", 0.0), f.get("narr_conv", 0.0)
            agree = md == nd and md != 0
            direction = int(md if abs(md) >= abs(nd) else nd)
            conv = (mc + nc) / 2 * (1.2 if agree else 0.6)
            conv = max(0.0, min(1.0, conv))
            views.append(
                InstrumentView(
                    instrument=sym,
                    direction=direction,
                    conviction=conv,
                    horizon="1m",
                    factors=f,
                    rationale="agree-amplify / disagree-soften coherence rule",
                )
            )
        return views
