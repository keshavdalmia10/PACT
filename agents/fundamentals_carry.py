"""Fundamentals/Carry Agent (spec §4.1).

Per-instrument factor families:
- Equity indices: aggregated P/E, FCF yield, revenue growth (EDGAR 10-K/Q)
- Bonds: real yields, term premium, slope (ALFRED)
- Gold: real-yield-vs-gold, USD context
- Oil: EIA inventories + NOAA weather (HDD, hurricanes)
- BTC: on-chain (active addresses, exchange flows, MVRV, hashrate)
- QQQ: GitHub Archive aggregate engineering velocity
- Earnings transcripts: per-quarter guidance/sentiment
"""

from __future__ import annotations

from datetime import date

from agents.base_agent import BaseAgent, InstrumentView

EQUITY_INDICES = ("SPY", "QQQ", "IWM", "EEM")
BONDS = ("IEF", "SHY")


class FundamentalsCarryAgent(BaseAgent):
    name = "fundamentals_carry"

    def __init__(self, llm_client, universe: tuple[str, ...], enable_altdata: bool = False):
        super().__init__(llm_client, universe)
        self.enable_altdata = enable_altdata

    def extract_factors(self, as_of: date) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for sym in self.universe:
            f: dict[str, float] = {}
            if sym in EQUITY_INDICES:
                f.update({
                    "agg_pe": 0.0,
                    "fwd_earnings_yield": 0.0,
                    "rev_growth_yoy": 0.0,
                    "fcf_yield": 0.0,
                    "transcript_guidance_score": 0.0,
                })
                if self.enable_altdata and sym == "QQQ":
                    f["github_eng_velocity_log_abnormal"] = 0.0
            elif sym in BONDS:
                f.update({"real_yield": 0.0, "term_premium": 0.0, "slope_2s10s": 0.0})
            elif sym == "GLD":
                f.update({"real_yield_corr": 0.0, "usd_index_z": 0.0})
            elif sym == "USO":
                f.update({"eia_inventory_z": 0.0})
                if self.enable_altdata:
                    f.update({"noaa_hdd_z": 0.0, "hurricane_active": 0.0})
            elif sym == "BTC":
                if self.enable_altdata:
                    f.update({
                        "active_addresses_log_abnormal": 0.0,
                        "exchange_netflow_z": 0.0,
                        "mvrv": 0.0,
                        "hashrate_log_abnormal": 0.0,
                    })
            out[sym] = f
        return out

    def decide(
        self,
        as_of: date,
        factors_by_instrument: dict[str, dict[str, float]],
    ) -> list[InstrumentView]:
        return [
            InstrumentView(
                instrument=sym,
                direction=0,
                conviction=0.0,
                horizon="1q",
                factors=f,
                rationale="fundamentals/carry: stub view (factor extraction pending)",
            )
            for sym, f in factors_by_instrument.items()
        ]
