"""Local research groups reviewed 2026-11-24; these are not licensed index classifications.

Treat diversified manufacturers conservatively. Samsung Electronics covers devices and
semiconductors (https://news.samsung.com/sg/fast-facts); Hanwha Solutions covers both
chemicals and solar (https://www.hanwhasolutions.com/m/en/company/about). First Solar
manufactures modules (https://www.firstsolar.com/en/About-Us/Overview). Doosan makes
generation equipment (https://www.doosanenerbility.com/en/business/gas_turbine_infra).
GLD and SLV are exchange-traded bullion trusts, grouped with ETFs strictly for retrieval
by underlying exposure. SCHP holds inflation-protected US Treasury bonds.
"""

POLICY = "sector-v1"
VERSION = "research-2026-11-24"

# Keys identify exchange listings. A missing peer group cannot authorize transfer.
EQUITIES = {
    "000660.KS": ("technology", "semiconductors"),
    "005380.KS": ("consumer_discretionary", "automobiles"),
    "005930.KS": ("technology", "diversified_electronics"),
    "009830.KS": (None, None),
    "012450.KS": ("industrials", "aerospace_defense"),
    "034020.KS": ("industrials", "power_equipment"),
    "036460.KS": ("utilities", "gas_utilities"),
    "096770.KS": ("energy", "integrated_energy"),
    "267260.KS": ("industrials", "electrical_equipment"),
    "316140.KS": ("financials", "banking"),
    "DLR": ("real_estate", "data_center_reits"),
    "FSLR": ("technology", "solar_modules"),
    "GOOGL": ("communication_services", "interactive_media"),
    "KO": ("consumer_staples", "beverages"),
    "NVDA": ("technology", "semiconductors"),
    "OXY": ("energy", "oil_gas"),
    "TSLA": ("consumer_discretionary", "automobiles"),
    "VST": ("utilities", "power_generation"),
    "WMT": ("consumer_staples", "staples_retail"),
}
FUNDS = {
    "069500.KS": "kr_large_cap",  # https://www.samsungfund.com/sheet/20260907/2ETF01_20260831.pdf
    "GLD": "gold",  # https://www.spdrgoldshares.com/usa/gld/
    "SCHP": "us_tips",  # https://www.schwabassetmanagement.com/products/schp
    "SLV": "silver",  # https://www.ishares.com/us/products/239855/ishares-silver-trust-fund
    "SPY": "us_large_cap",  # https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy
}


def classify(ticker, instrument_type):
    asset_class, sector, industry, exposure = "unknown", None, None, None
    if ticker in EQUITIES and instrument_type == "EQUITY":
        asset_class = "equity"
        sector, industry = EQUITIES[ticker]
    elif ticker in FUNDS and instrument_type == "ETF":
        asset_class, exposure = "etf", FUNDS[ticker]
    return {
        "version": VERSION,
        "asset_class": asset_class,
        "sector": sector,
        "industry": industry,
        "exposure": exposure,
    }


def catalog_classification(ticker, market):
    """Preview watchlist labels, without asserting a market-data identity check."""
    expected_market = "kr" if ticker.endswith((".KS", ".KQ")) else "us"
    expected_type = "ETF" if ticker in FUNDS else "EQUITY"
    return classify(ticker, expected_type if market == expected_market else None)
