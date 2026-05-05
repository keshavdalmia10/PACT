"""Cross-Asset Transmission Agent (spec §4.1).

Reads outputs from Macro Regime + Narrative/Event and reasons about
transmission chains (e.g. oil shock → inflation → 10y yield → IEF short).
The deterministic anchor uses a simple agree-amplify / disagree-soften rule;
the LLM layer reasons about transmission chains over that anchor.
"""

from __future__ import annotations

from datetime import date

from agents._llm_helpers import views_from_llm_or_anchor
from agents.base_agent import AgentDecision, BaseAgent, InstrumentView

SYSTEM_PROMPT = (
    "You are the Cross-Asset Transmission Agent. Inputs are Macro and "
    "Narrative agent views per instrument plus a deterministic anchor "
    "(agree-amplify / disagree-soften). Reason about cross-asset "
    "transmission chains (e.g. oil → CPI → 10y → IEF short; USD↑ → EEM↓; "
    "real yields↑ → GLD↓). Refine the anchor only when transmission logic "
    "supports it. Never invent factors. Output strict JSON: a list of "
    '{"instrument": SYMBOL, "direction": -1|0|1, "conviction": 0..1, '
    '"horizon": "1m", "rationale": "<=240 chars cite the transmission chain"}.'
)


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
            f: dict[str, float] = {}
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
        anchor: list[InstrumentView] = []
        for sym, f in factors_by_instrument.items():
            md, mc = f.get("macro_dir", 0.0), f.get("macro_conv", 0.0)
            nd, nc = f.get("narr_dir", 0.0), f.get("narr_conv", 0.0)
            agree = md == nd and md != 0
            direction = int(md if abs(md) >= abs(nd) else nd)
            conv = (mc + nc) / 2 * (1.2 if agree else 0.6)
            conv = max(0.0, min(1.0, conv))
            anchor.append(
                InstrumentView(
                    instrument=sym, direction=direction, conviction=conv, horizon="1m",
                    factors=f, rationale="agree-amplify / disagree-soften",
                )
            )

        # If both upstreams missing → no transmission to reason about; skip LLM.
        if all(not f for f in factors_by_instrument.values()):
            return anchor

        return views_from_llm_or_anchor(
            self.llm,
            system_prompt=SYSTEM_PROMPT,
            user_payload={
                "as_of": as_of.isoformat(),
                "upstream_views": factors_by_instrument,
                "anchor": [
                    {"instrument": v.instrument, "direction": v.direction, "conviction": v.conviction}
                    for v in anchor
                ],
            },
            universe=self.universe,
            default_horizon="1m",
            anchor_views=anchor,
            agent_name=self.name,
        )
