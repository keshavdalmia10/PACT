"""Pinned HuggingFace commit shas for ChronoGPT yearly checkpoints (spec §6.1, §8).

Fetched on 2026-05-05 from https://huggingface.co/manelalab.

Each checkpoint is trained only on data through `<YYYY>-12-31` (the cutoff
year). For a backtest decision at date D, use the checkpoint with cutoff
= year(D) - 1 to stay strictly contamination-clean.

The base family (`chrono-gpt-v1-`) is the raw GPT; the instruct family
(`chrono-gpt-instruct-v1-`) is the instruction-tuned variant. We default to
instruct for agentic decision-making.
"""

from __future__ import annotations

INSTRUCT_FAMILY = "manelalab/chrono-gpt-instruct-v1"
BASE_FAMILY = "manelalab/chrono-gpt-v1"

# {cutoff_year: HF commit sha}
INSTRUCT_REVISIONS: dict[int, str] = {
    1999: "297f9ba7262dc86e71084ba214f4ee05a891c638",
    2000: "8c249ea8f7ce24bd9268864e2548fb71cb8772f5",
    2001: "2af12459c6e60b00edd82b6c14d5fbe9fe0463c1",
    2002: "777eadfdc8dd37c4cc5ec03e04d0375e60c2b93c",
    2003: "564bf9e9984c461793b2a6926979accaf0970e7d",
    2004: "19bff0527fcda270790103a200ce99b90c2877a8",
    2005: "6fdc3f4f5c2868481d26cfd644a9eb62556b03fe",
    2006: "208f9b790c9f2194ec93dea1bc2a326dd85157fe",
    2007: "d184f3be0b936613355498ca2b3bd7930114e7a6",
    2008: "d7bc47e91ad85f0271e461db78c9cc4544e60166",
    2009: "3a8099285798ca68fa7248516f22f4c7dc716c29",
    2010: "86d39adba13b3c2e0250c4e91fc0fafe4507614c",
    2011: "a60308731f1eac74a955ff3df48ac37f8826b6a9",
    2012: "64bc127dd28d636d2002a809cba064eea9173dfd",
    2013: "f35f1596d860a797df1c592a5a70bf02a3a00884",
    2014: "e121db790ca77ebb082c025b2438717644ee1cfb",
    2015: "5a7f3439fd5d782b3780c366160c43177e6f5eba",
    2016: "5aec0aacc696f9526e12abe22a3fc96348dfca1d",
    2017: "5f6b4ab1664bd5e658af44ad6b02183178b81b55",
    2018: "331c03be137a1a80f1a371232d3d6a9636f6ad9a",
    2019: "4dfb7817915d07d0ed99815877186f827ec3b88e",
    2020: "f8020c2c939645abbec9caf8a0cdd1d7806cb42a",
    2021: "7f3c7d0dccea060d96dfb89391ef830655b8dbaf",
    2022: "f1b8c4eb806a9fe7c26b7e5d30cf003304ed9281",
    2023: "2156f3ac9a36916773664266397682b951d43411",
    2024: "c162df20666475d125737e030943e18e10b3d91f",
}

# Newest cutoff that exists; used as the default when no as_of is supplied.
LATEST_CUTOFF_YEAR = max(INSTRUCT_REVISIONS)


def cutoff_year_for(decision_year: int) -> int:
    """Pick the contamination-clean cutoff for a backtest decision year.

    Decision year 2015 → cutoff 2014 (model trained only through 2014-12-31).
    Clamps to the available range.
    """
    target = decision_year - 1
    if target < min(INSTRUCT_REVISIONS):
        return min(INSTRUCT_REVISIONS)
    if target > LATEST_CUTOFF_YEAR:
        return LATEST_CUTOFF_YEAR
    return target


def repo_id(cutoff_year: int, family: str = INSTRUCT_FAMILY) -> str:
    return f"{family}-{cutoff_year}1231"


def revision(cutoff_year: int) -> str:
    return INSTRUCT_REVISIONS[cutoff_year]
