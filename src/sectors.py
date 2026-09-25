"""Map DART KSIC industry codes (Korean Standard Industrial Classification) to broad sectors.

KSIC divisions (first 2 digits) are grouped into sectors a sell-side analyst would recognize.
Sectors with fewer than MIN_SECTOR_SIZE firms are pooled into "Other" in screen.py.
"""

MIN_SECTOR_SIZE = 5

# (first 2 KSIC digits, sector)
KSIC_DIVISION_TO_SECTOR = {
    "10": "Consumer Staples", "11": "Consumer Staples", "12": "Consumer Staples",
    "13": "Consumer Discretionary", "14": "Consumer Discretionary", "15": "Consumer Discretionary",
    "16": "Materials", "17": "Materials", "18": "Materials",
    "19": "Energy",
    "20": "Chemicals",
    "21": "Healthcare",
    "22": "Materials", "23": "Materials",
    "24": "Steel & Metals",
    "25": "Industrials",
    "26": "Tech Hardware & Semis", "27": "Tech Hardware & Semis",
    "28": "Industrials", "29": "Industrials",
    "30": "Autos",
    "31": "Industrials",
    "32": "Consumer Discretionary", "33": "Consumer Discretionary",
    "35": "Utilities", "36": "Utilities", "37": "Utilities", "38": "Utilities", "39": "Utilities",
    "41": "Construction & Real Estate", "42": "Construction & Real Estate",
    "68": "Construction & Real Estate",
    "45": "Retail & Trading", "46": "Retail & Trading", "47": "Retail & Trading",
    "49": "Transport", "50": "Transport", "51": "Transport", "52": "Transport",
    "55": "Consumer Discretionary", "56": "Consumer Discretionary",
    "58": "Software & Internet", "62": "Software & Internet", "63": "Software & Internet",
    "59": "Media", "60": "Media",
    "61": "Telecom",
    "70": "Healthcare",  # KOSPI R&D-service firms are mostly biotech
    "71": "Business Services", "72": "Business Services", "73": "Business Services",
    "74": "Business Services", "75": "Business Services",
}


def sector_from_ksic(induty_code):
    code = str(induty_code)
    if code.startswith("64992"):
        return "Holding Companies"
    return KSIC_DIVISION_TO_SECTOR.get(code[:2], "Other")
