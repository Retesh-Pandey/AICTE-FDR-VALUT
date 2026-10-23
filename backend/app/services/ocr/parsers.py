import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

# Canonical bank registry for fuzzy matching
CANONICAL_BANKS = [
    ("State Bank of India", ["state bank of india", "sbi", "state bank"]),
    ("Punjab National Bank", ["punjab national bank", "pnb"]),
    ("Bank of Baroda", ["bank of baroda", "bob", "baroda"]),
    ("Canara Bank", ["canara bank", "canara"]),
    ("Union Bank of India", ["union bank of india", "union bank", "ubi"]),
    ("HDFC Bank", ["hdfc bank", "hdfc", "housing development finance"]),
    ("ICICI Bank", ["icici bank", "icici"]),
    ("Axis Bank", ["axis bank", "axis"]),
    ("Kotak Mahindra Bank", ["kotak mahindra bank", "kotak bank", "kotak"]),
    ("Indian Bank", ["indian bank"]),
    ("Bank of India", ["bank of india", "boi"]),
    ("Central Bank of India", ["central bank of india", "cbi"]),
    ("IDBI Bank", ["idbi bank", "idbi"]),
    ("IndusInd Bank", ["indusind bank", "indusind"]),
    ("Yes Bank", ["yes bank"]),
    ("Federal Bank", ["federal bank"]),
]


def parse_amount(text: str) -> Optional[Decimal]:
    """
    Parses Indian and international currency representations into a Decimal.
    Supports:
      - Indian comma grouping: 5,00,000.00 or 1,25,00,000
      - Currency symbols: ₹, Rs., Rs, INR, /-
      - Decimals and integer amounts
    """
    if not text or not isinstance(text, str):
        return None

    cleaned = text.strip()

    # Look for amount patterns following labels or currency symbols
    patterns = [
        # Label followed by optional currency symbol and numbers (e.g. Principal Amount: INR 1,50,00,000.00)
        r"(?:Principal(?:\s*(?:Amount|Sum))?|Deposit\s+Amount|Amount(?:\s*\(Rs\.?\))?|Deposit\s*Sum|Sum\s*of)[:\s\-]*(?:₹|Rs\.?|INR)?\s*([0-9][0-9,]*\.?[0-9]{0,2})(?:\s*/-)?",
        # Explicit currency prefix or label followed by optional non-word chars and numbers
        r"(?:₹|Rs\.?|INR)\s*[^\w\s]*\s*([0-9][0-9,]*\.?[0-9]{0,2})(?:\s*/-)?",
        # Numbers ending with /-
        r"\b([0-9][0-9,]*\.?[0-9]{0,2})\s*/-",
        # Freestanding Indian comma formatted numbers
        r"\b([0-9]{1,2},[0-9]{2},[0-9]{3}(?:\.[0-9]{1,2})?|[0-9]{1,3},[0-9]{3}(?:\.[0-9]{1,2})?)\b",
        # Standalone decimal numbers with at least 4 digits or with decimals
        r"\b([0-9]{4,}(?:\.[0-9]{1,2})?)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            raw_str = match.group(1).replace(",", "").strip()
            if raw_str.endswith("."):
                raw_str = raw_str[:-1]
            try:
                val = Decimal(raw_str)
                if val > 0:
                    return val.quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                continue

    # Fallback: find any token resembling a currency or large number
    fallback_match = re.search(r"([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?)", cleaned)
    if fallback_match:
        try:
            val = Decimal(fallback_match.group(1).replace(",", "").strip())
            if val > 0:
                return val.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            pass

    return None


def parse_date(text: str) -> Optional[date]:
    """
    Parses various date formats commonly found in Indian banking receipts:
      - DD/MM/YYYY or DD-MM-YYYY
      - DD.MM.YYYY
      - DD-Mon-YYYY (e.g. 15-Jan-2026, 15-JAN-2026)
      - DD Month YYYY (e.g. 15 January 2026, 15 Jan 2026)
      - YYYY-MM-DD
      - Month DD, YYYY (e.g. January 15, 2026)
    """
    if not text or not isinstance(text, str):
        return None

    cleaned = text.strip()

    date_formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%Y-%m-%d",
        "%b %d, %Y",
        "%B %d, %Y",
        "%b %d %Y",
        "%B %d %Y",
        "%d/%m/%y",
        "%d-%m-%y",
    ]

    # Pre-extract likely date candidates using regex
    candidates = re.findall(
        r"\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b|"
        r"\b\d{1,2}[\-\s](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\-\s]\d{2,4}\b|"
        r"\b\d{4}-\d{2}-\d{2}\b|"
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
        cleaned,
        re.IGNORECASE,
    )

    if not candidates:
        candidates = [cleaned]

    for candidate in candidates:
        cand_str = candidate.strip()
        cand_normalized = re.sub(r"\s+", " ", cand_str.replace(",", " "))

        for fmt in date_formats:
            for s in (cand_str, cand_normalized):
                try:
                    dt = datetime.strptime(s, fmt).date()
                    if 1990 <= dt.year <= 2100:
                        return dt
                except ValueError:
                    continue

    return None


def find_fdr_number(text: str) -> Optional[str]:
    """
    Extracts Fixed Deposit Receipt number from text by searching for common
    banking labels and identifiers.
    """
    if not text or not isinstance(text, str):
        return None

    patterns = [
        r"(?:Fixed Deposit Receipt No|FDR\s*No|Receipt\s*No|Deposit\s*A/c\s*(?:No)?|FDR\s*Number|Account\s*No|Certificate\s*No)[\.:\s\-#]+([A-Za-z0-9\-\/]{5,30})",
        r"\b(FDR[\-\/][A-Za-z0-9\-\/]{4,25})\b",
        r"\b([A-Z]{3,4}\d{6,16})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Exclude false positives like dates or common labels
            if len(candidate) >= 4 and not re.match(r"^\d{2}[/\-]\d{2}[/\-]\d{2,4}$", candidate):
                return candidate.strip("-/: ")

    return None


def match_bank(text: str) -> Optional[Tuple[str, float]]:
    """
    Matches bank name in text against known canonical Indian banks.
    Returns (canonical_name, confidence_score) where confidence is between 0.0 and 1.0.
    """
    if not text or not isinstance(text, str):
        return None

    lower_text = text.lower()

    best_match = None
    best_score = 0.0

    for canonical_name, aliases in CANONICAL_BANKS:
        for alias in aliases:
            # Word boundary search for high confidence
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, lower_text):
                # Longer alias matches get higher confidence
                score = 0.95 if alias == canonical_name.lower() else 0.90
                if score > best_score:
                    best_score = score
                    best_match = canonical_name
            elif alias in lower_text:
                score = 0.75
                if score > best_score:
                    best_score = score
                    best_match = canonical_name

    if best_match:
        return (best_match, best_score)
    return None


def parse_ifsc(text: str) -> Optional[str]:
    """Finds Indian Financial System Code (IFSC) matching regex [A-Z]{4}0[A-Z0-9]{6}."""
    if not text or not isinstance(text, str):
        return None
    match = re.search(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", text)
    if match:
        return match.group(1).upper()
    return None


def parse_interest_rate(text: str) -> Optional[str]:
    """Extracts stated deposit interest rate percentage."""
    if not text or not isinstance(text, str):
        return None
    patterns = [
        r"(?:Interest\s*Rate|ROI|Rate\s*of\s*Interest)[:\s\-]*([0-9]{1,2}(?:\.[0-9]{1,3})?)\s*%",
        r"\b([0-9]{1,2}\.[0-9]{1,3})\s*%\s*(?:p\.?a\.?|per\s*annum)?\b",
        r"\b([0-9]{1,2})\s*%\s*(?:p\.?a\.?|per\s*annum)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return f"{match.group(1)}%"
    return None


def parse_compounding(text: str) -> Optional[str]:
    """Extracts compounding frequency from deposit receipt."""
    if not text or not isinstance(text, str):
        return None
    patterns = [
        (r"\b(quarterly\s+compound(?:ing)?|compounded\s+quarterly)\b", "Quarterly Compound"),
        (r"\b(monthly\s+compound(?:ing)?|compounded\s+monthly|monthly\s+payout)\b", "Monthly Compound"),
        (r"\b(half[- ]yearly\s+compound(?:ing)?|compounded\s+half[- ]yearly|semi[- ]annually)\b", "Half-Yearly Compound"),
        (r"\b(annual(?:ly)?\s+compound(?:ing)?|compounded\s+annually)\b", "Annual Compound"),
        (r"\b(cumulative|re[- ]investment\s+plan)\b", "Cumulative"),
        (r"\bquarterly\b", "Quarterly Compound"),
        (r"\bmonthly\b", "Monthly Compound"),
        (r"\bat\s+maturity\b", "At Maturity"),
    ]
    for pattern, label in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return None


def parse_tenure(
    text: str,
    issue_date: Optional[date] = None,
    maturity_date: Optional[date] = None,
) -> Optional[str]:
    """
    Extracts tenure from deposit receipt text, or computes it from issue and maturity dates.
    """
    if text and isinstance(text, str):
        patterns = [
            r"(?:Tenure|Period(?:\s*of\s*Deposit)?|Term|Duration)[:\s\-]+([0-9]{1,3}\s*(?:Years?|Yrs?|Months?|Mos?|Days?))",
            r"\b([0-9]{1,3}\s*(?:Years?|Months?))\s*(?:Tenure|Period|Term)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

    if issue_date and maturity_date and maturity_date > issue_date:
        days = (maturity_date - issue_date).days
        approx_months = round(days / 30.4375)
        if approx_months >= 12 and approx_months % 12 == 0:
            years = approx_months // 12
            suffix = "s" if years > 1 else ""
            return f"{approx_months} Months ({years} Year{suffix})"
        elif approx_months >= 1:
            return f"{approx_months} Months"
        return f"{days} Days"

    return None


def parse_institution_id(text: str) -> Optional[str]:
    """Extracts AICTE Institution Identifier or Permanent ID."""
    if not text or not isinstance(text, str):
        return None
    patterns = [
        r"(?:AICTE\s*(?:Permanent\s*)?ID|Institution\s*ID|PID|AICTE\s*Code|College\s*Code)[:\s\-#]*([0-9]{1,2}-[0-9]{6,12}|AICTE-[0-9]{1,2}-[0-9]{6,12})",
        r"\b(AICTE-[0-9]{1,2}-[0-9]{6,12})\b",
        r"\b(1-[0-9]{7,10})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def parse_institution_name(text: str) -> Optional[str]:
    """Extracts Institution or College Name."""
    if not text or not isinstance(text, str):
        return None
    patterns = [
        r"(?:Name of (?:Institution|College|Society|Trust)|In (?:the )?Name of|Account Titular|Institution Name|College Name)[:\s\-]+([A-Za-z0-9\s,\.\-&']{5,80})",
        r"\b(Principal,\s*[A-Za-z0-9\s,\.\-&']{5,80})\b",
        r"(?:In Account With)[:\s\-]+([A-Za-z0-9\s,\.\-&']{5,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            cand = match.group(1).split("\n")[0].strip()
            # Clean up trailing punctuation
            cand = re.sub(r"[\s,\.\-]+$", "", cand)
            if len(cand) >= 5:
                return cand
    return None


def parse_lien_info(text: str) -> Optional[str]:
    """Extracts lien clause information referencing AICTE or Member Secretary."""
    if not text or not isinstance(text, str):
        return None
    patterns = [
        r"(?:Lien\s*Marked\s*To|Lien\s*In\s*Favo(?:u)?r\s*Of|Lien)[:\s\-]+([^\n\r]{4,120})",
        r"([^\n\r]*\b(?:Lien|lien)\b[^\n\r]*\b(?:AICTE|Council|Member\s*Secretary)\b[^\n\r]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
            if len(cleaned) >= 4:
                return cleaned
    return None

