"""
Text preprocessing for bank transaction descriptions.

Extracts meaningful merchant/payee names from noisy UPI/bank strings
and cleans transaction text for better ML features.
"""

import re

import pandas as pd


# Common noise patterns in bank transaction text
NOISE_PATTERNS = [
    r'\b\d{6,}\b',                          # Long numbers (transaction IDs, account numbers)
    r'\bUPI/[A-Z]{2}/\d+/',                 # UPI/DR/123456/ or UPI/CR/123456/
    r'\bUPI-\d+-',                           # UPI-123456-
    r'\b[A-Z]{4}\d{7,}\b',                  # Bank codes like UTIB7710820895
    r'\b\d{4,}\s+AT\s+\d+\b',              # "0097696162090 AT 05318"
    r'\b(WDL|DEP)\s+TFR\b',                # WDL TFR / DEP TFR
    r'\b(NO\s+R|UPI)\s+\d+\b',             # "NO R   0097696" or "UPI   0097696"
    r'\b\d{2}:\d{2}:\d{2}\b',              # Timestamps like 18:03:21
    r'\b\d+@[a-z]+\b',                      # UPI IDs like 8108874144@upi
    r'\b[a-z]+@ok[a-z]+\b',                # UPI handles like mahendraksy@okaxis
    r'\b\d+@ybl\b',                         # UPI handles like 7877756007@ybl
    r'/State Bank Of I/\d+/',               # Bank names in UPI strings
    r'\bBHAYANDAR\b',                       # Branch locations in transaction strings
    r'\bIN$',                               # Trailing "IN" (country code)
    r'\b(kaIN|UPIN)\b',                     # Merged "IN" suffixes
    r'\bCMS/',                              # CMS/ prefix
    r'\bBIL/ONL/\d+/',                      # Bill pay prefixes
    r'/\d+\s+WORLDLINE EPAYM',             # Payment processor suffixes
    r'\b\d{12}\b',                          # 12-digit numbers
    r'\bXX\d{4}\b',                         # Masked account numbers XX9273
]

# Patterns to extract merchant names
MERCHANT_EXTRACTORS = [
    # "UPI-123456-Merchant Name IN" -> "Merchant Name"
    (r'UPI-\d+-(.+?)(?:\s+IN)?$', 1),
    # "PAYU*Merchant Limited City IN" -> "Merchant Limited"
    (r'PAYU\*(.+?)(?:\s+\w+\s+IN)?$', 1),
    # "ING*MERCHANT NAME,URL" -> "MERCHANT NAME"
    (r'ING\*([^,]+)', 1),
]

# Known merchant name mappings (normalize variations)
MERCHANT_NORMALIZATIONS = {
    'swiggy': 'swiggy',
    'swiggy limited': 'swiggy',
    'swiggy dineout': 'swiggy dineout',
    'zomato': 'zomato',
    'zepto': 'zepto',
    'amazon': 'amazon',
    'amazon pay': 'amazon',
    'amazonin': 'amazon',
    'flipkart': 'flipkart',
    'flipkart payments': 'flipkart',
    'myntra': 'myntra',
    'myntra designs': 'myntra',
    'uber': 'uber',
    'ola': 'ola',
    'bigbasket': 'bigbasket',
    'blinkit': 'blinkit',
    'phonepe': 'phonepe',
    'gpay': 'gpay',
    'mark sandspencer': 'marks and spencer',
}


def extract_merchant(text: str) -> str:
    """Try to extract a clean merchant name from the transaction text."""
    if not text:
        return ""

    for pattern, group in MERCHANT_EXTRACTORS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(group).strip()

    return ""


def normalize_merchant(text: str) -> str:
    """Normalize known merchant names."""
    text_lower = text.lower().strip()
    for pattern, normalized in MERCHANT_NORMALIZATIONS.items():
        if pattern in text_lower:
            return normalized
    return text_lower


def clean_transaction_text(text: str) -> str:
    """Remove noise from bank transaction text, keep meaningful words."""
    if not text:
        return ""

    cleaned = text
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)

    # Remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Remove very short remaining tokens (likely fragments)
    tokens = cleaned.split()
    tokens = [t for t in tokens if len(t) > 1]

    return ' '.join(tokens)


PLATFORM_MERCHANTS = frozenset([
    "amazon", "flipkart", "myntra", "swiggy", "zomato", "zepto",
    "blinkit", "bigbasket", "meesho", "ajio", "nykaa", "tatacliq",
])


def is_platform_merchant(merchant_name: str) -> bool:
    """True if the merchant is a multi-category platform (Amazon, Swiggy, etc.)."""
    if not merchant_name:
        return False
    return merchant_name.lower().strip() in PLATFORM_MERCHANTS


def build_enhanced_text(details, notes) -> str:
    """
    Build an enhanced text feature combining cleaned details and notes.
    Notes are given higher weight by repeating them (they're more informative).
    """
    details = str(details) if pd.notna(details) else ""
    notes = str(notes) if pd.notna(notes) else ""

    merchant = extract_merchant(details)
    normalized = normalize_merchant(merchant) if merchant else ""
    cleaned_details = clean_transaction_text(details)
    clean_notes = notes.strip()

    parts = []
    # Normalized merchant name (strongest signal when available)
    if normalized:
        parts.append(normalized)
    # Cleaned transaction text
    if cleaned_details:
        parts.append(cleaned_details)
    # Notes repeated for higher weight (they're the best disambiguator)
    if clean_notes:
        parts.append(clean_notes)
        parts.append(clean_notes)  # double-weight

    return ' '.join(parts)
