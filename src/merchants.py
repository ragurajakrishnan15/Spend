"""Synthetic merchant catalogue and a regex rule engine that cleans raw card descriptors.

All merchant names are fictional. Raw descriptors imitate the noise in real card data
(prefixes, store numbers, abbreviations, locations); a share of them is deliberately
hard to match so coverage and precision are meaningful to report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Merchant:
    name: str
    category: str
    pattern: str            # regex applied to the *normalised* descriptor
    variants: tuple[str, ...]   # raw name variants used by the generator


CATALOG: tuple[Merchant, ...] = (
    Merchant("Greenfield Market", "Groceries", r"\bGREEN\s?F(IE)?LD\b|\bGRNFLD\b", ("GREENFIELD MARKET", "GREENFIELD MKT", "GRNFLD MARKET")),
    Merchant("Harvest Basket", "Groceries", r"\bHARVEST\s?BSKT\b|\bHARVEST\s?BASKET\b", ("HARVEST BASKET", "HARVEST BSKT", "HARVESTBASKET")),
    Merchant("Corner Fresh", "Groceries", r"\bCORNER\s?FRESH\b|\bCRNR\s?FRSH\b", ("CORNER FRESH", "CORNERFRESH", "CRNR FRSH")),
    Merchant("Copper Kettle Cafe", "Dining", r"\bCOPPER\s?KETTLE\b|\bCPR\s?KTL\b", ("COPPER KETTLE CAFE", "COPPER KETTLE", "CPR KTL CAFE")),
    Merchant("Blue Fig Bistro", "Dining", r"\bBLUE\s?FIG\b", ("BLUE FIG BISTRO", "BLUEFIG BISTRO", "BLUE FIG")),
    Merchant("Urban Noodle House", "Dining", r"\bURBAN\s?NOODLE\b|\bURB\s?NDL\b", ("URBAN NOODLE HOUSE", "URBAN NOODLE", "URB NDL HSE")),
    Merchant("Skyline Airways", "Travel", r"\bSKYLINE\s?(AIR|AIRWAYS)\b|\bSKYLN\s?AIR\b", ("SKYLINE AIRWAYS", "SKYLINE AIR", "SKYLN AIR")),
    Merchant("Wayfarer Hotels", "Travel", r"\bWAYFARER\b|\bWYFRR\s?HTL\b", ("WAYFARER HOTELS", "WAYFARER HTL", "WYFRR HTL")),
    Merchant("Metro Rail Pass", "Travel", r"\bMETRO\s?RAIL\b", ("METRO RAIL PASS", "METRO RAIL", "METRORAIL")),
    Merchant("Northgate Outfitters", "Retail", r"\bNORTH\s?GATE\b|\bNRTHGT\b", ("NORTHGATE OUTFITTERS", "NORTHGATE OUTFIT", "NRTHGT OUTFTRS")),
    Merchant("Brightwood Home", "Retail", r"\bBRIGHT\s?WOOD\b|\bBRGHTWD\b", ("BRIGHTWOOD HOME", "BRIGHTWOOD", "BRGHTWD HOME")),
    Merchant("Pixel & Plug Electronics", "Retail", r"\bPIXEL\s?(&|AND)?\s?PLUG\b|\bPXL\s?PLG\b", ("PIXEL & PLUG", "PIXEL AND PLUG", "PXL PLG ELEC")),
    Merchant("Metro Power & Light", "Utilities", r"\bMETRO\s?POWER\b|\bMTR\s?PWR\b", ("METRO POWER & LIGHT", "METRO POWER LT", "MTR PWR LIGHT")),
    Merchant("ClearStream Water", "Utilities", r"\bCLEAR\s?STREAM\b|\bCLRSTRM\b", ("CLEARSTREAM WATER", "CLEAR STREAM WTR", "CLRSTRM WATER")),
    Merchant("Summit Telecom", "Utilities", r"\bSUMMIT\s?(TELECOM|TEL)\b|\bSMMT\s?TEL", ("SUMMIT TELECOM", "SUMMIT TEL", "SMMT TELECOM")),
    Merchant("Starlight Cinemas", "Entertainment", r"\bSTAR\s?LIGHT\s?(CINEMAS?|CIN)\b|\bSTRLGHT\b", ("STARLIGHT CINEMAS", "STARLIGHT CINEMA", "STRLGHT CIN")),
    Merchant("PlayHouse Games", "Entertainment", r"\bPLAY\s?HOUSE\b|\bPLYHS\b", ("PLAYHOUSE GAMES", "PLAY HOUSE GAMES", "PLYHS GAMES")),
    Merchant("Harbor Live Tickets", "Entertainment", r"\bHARBOR\s?LIVE\b|\bHRBR\s?LIVE\b", ("HARBOR LIVE TICKETS", "HARBOR LIVE", "HRBR LIVE TIX")),
    Merchant("Wellspring Pharmacy", "Health", r"\bWELL\s?SPRING\b|\bWLLSPRNG\b", ("WELLSPRING PHARMACY", "WELLSPRING PHARM", "WLLSPRNG RX")),
    Merchant("Evergreen Dental", "Health", r"\bEVER\s?GREEN\s?DENT", ("EVERGREEN DENTAL", "EVERGREEN DENTL", "EVERGREENDENTAL")),
    Merchant("Pulse Fitness", "Health", r"\bPULSE\s?(FITNESS|FIT)\b", ("PULSE FITNESS", "PULSE FIT", "PULSEFITNESS")),
    Merchant("RoadRunner Fuel", "Fuel", r"\bROAD\s?RUNNER\b|\bRDRNR\b", ("ROADRUNNER FUEL", "ROAD RUNNER FUEL", "RDRNR FUEL")),
    Merchant("Beacon Gas & Go", "Fuel", r"\bBEACON\s?GAS\b|\bBCN\s?GAS\b", ("BEACON GAS & GO", "BEACON GAS GO", "BCN GAS")),
    Merchant("Citywide Petro", "Fuel", r"\bCITY\s?WIDE\s?PETRO\b|\bCTYWD\s?PTR\b", ("CITYWIDE PETRO", "CITY WIDE PETRO", "CTYWD PTR")),
)

BY_NAME = {m.name: m for m in CATALOG}
PREFIXES = ("", "", "", "POS DEBIT ", "SQ *", "TST* ", "PURCHASE AUTHORIZED ON 0412 ", "CHECKCARD 0907 ")
CITIES = ("NEW YORK NY", "BROOKLYN NY", "CHICAGO IL", "AUSTIN TX", "DENVER CO", "SEATTLE WA", "ATLANTA GA", "BOSTON MA")
GARBLED = ("{a}#{b}", "{a}*{n}", "{a}-{b} INC")
UNKNOWN = "Unknown"

_PREFIX_RE = re.compile(r"^(POS DEBIT|SQ\s?\*|TST\*|PURCHASE AUTHORIZED ON \d{4}|CHECKCARD \d{4})\s*")
_NOISE_RE = re.compile(r"#\s?\d+|\b\d{3,}\b|\b[A-Z]{2}$")
# Plain groups are made non-capturing so pandas does not warn about match groups.
_COMPILED = [(i, re.compile(re.sub(r"\((?!\?)", "(?:", m.pattern)), m) for i, m in enumerate(CATALOG)]


def make_descriptor(rng: np.random.Generator, merchant: Merchant, garble_rate: float = 0.07) -> str:
    """Build one noisy raw descriptor for a merchant."""
    if rng.random() < garble_rate:
        base = merchant.variants[0].replace(" ", "")
        a, b = base[:3], base[3:5]
        text = GARBLED[int(rng.integers(len(GARBLED)))].format(a=a, b=b, n=int(rng.integers(100, 999)))
    else:
        text = merchant.variants[int(rng.integers(len(merchant.variants)))]
    prefix = PREFIXES[int(rng.integers(len(PREFIXES)))]
    store = f" #{int(rng.integers(10, 9999))}" if rng.random() < .6 else ""
    city = f" {CITIES[int(rng.integers(len(CITIES)))]}" if rng.random() < .7 else ""
    return f"{prefix}{text}{store}{city}".strip()


def normalize_descriptor(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s).upper().strip())
    s = _PREFIX_RE.sub("", s)
    s = _NOISE_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def classify_descriptors(descriptors: pd.Series) -> pd.DataFrame:
    """Apply the ordered regex rules; first match wins. Unmatched rows are labelled 'Unknown'."""
    norm = descriptors.astype(str).map(normalize_descriptor)
    out = pd.DataFrame({"normalized": norm, "merchant_clean": UNKNOWN, "category_clean": UNKNOWN,
                        "rule_id": -1}, index=descriptors.index)
    unassigned = pd.Series(True, index=descriptors.index)
    for i, rx, m in _COMPILED:
        hit = unassigned & norm.str.contains(rx, regex=True)
        if hit.any():
            out.loc[hit, ["merchant_clean", "category_clean", "rule_id"]] = [m.name, m.category, i]
            unassigned &= ~hit
    return out


def classification_report(df: pd.DataFrame, classified: pd.DataFrame, top_unmatched: int = 10) -> dict:
    """Coverage and (because the data is synthetic) accuracy against the generator's true merchant."""
    matched = classified["merchant_clean"] != UNKNOWN
    report = {"rows": int(len(df)), "matched_rows": int(matched.sum()), "coverage": float(matched.mean()),
              "rules": len(CATALOG)}
    if "true_merchant" in df:
        truth = df["true_merchant"]
        correct = (classified["merchant_clean"] == truth) & matched
        report["precision"] = float(correct.sum() / matched.sum()) if matched.any() else 0.0
        report["recall"] = float(correct.sum() / len(df))
        report["category_agreement"] = float((classified.loc[matched, "category_clean"] == df.loc[matched, "category"]).mean()) if matched.any() else 0.0
    um = classified.loc[~matched, "normalized"].value_counts().head(top_unmatched)
    report["top_unmatched"] = [{"descriptor": k, "count": int(v)} for k, v in um.items()]
    per_rule = classified[matched].groupby("merchant_clean").size().sort_values(ascending=False)
    report["rule_hits"] = [{"merchant": k, "rows": int(v), "category": BY_NAME[k].category,
                            "pattern": BY_NAME[k].pattern} for k, v in per_rule.items()]
    return report
