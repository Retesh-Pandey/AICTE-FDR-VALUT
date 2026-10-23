import re
from typing import Any, Dict, List, Optional, Tuple


class DocumentClassificationResult:
    def __init__(
        self,
        status: str,
        confidence: float,
        classification_reasons: List[str],
        detected_document_type: Optional[str] = None,
        content_summary: Optional[str] = None,
        extracted_snippets: Optional[List[str]] = None,
        is_fdr_candidate: bool = True,
        submission_blocked: bool = False,
    ):
        self.status = status
        self.confidence = round(confidence, 2)
        self.classification_reasons = classification_reasons
        self.detected_document_type = detected_document_type
        self.content_summary = content_summary
        self.extracted_snippets = extracted_snippets or []
        self.is_fdr_candidate = is_fdr_candidate
        self.submission_blocked = submission_blocked

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "classification_reasons": self.classification_reasons,
            "detected_document_type": self.detected_document_type,
            "content_summary": self.content_summary,
            "extracted_snippets": self.extracted_snippets,
            "is_fdr_candidate": self.is_fdr_candidate,
            "submission_blocked": self.submission_blocked,
        }


# Unrelated document detection profiles
UNRELATED_PROFILES = [
    {
        "type": "Utility / Electricity Bill",
        "description": "an electricity or utility bill containing consumer numbers, meter readings, or tariff charges",
        "keywords": [
            "electricity bill", "meter reading", "kwh", "power distribution",
            "discom", "consumer number", "consumer no", "ca number", "units consumed",
            "connected load", "tariff", "subdivision", "electricity board",
            "water bill", "gas bill", "utility bill", "billing period", "current reading"
        ],
        "strong_patterns": [
            r"\b(?:electricity|water|gas)\s*bill\b",
            r"\bmeter\s*(?:reading|no|number)\b",
            r"\bconsumer\s*(?:no|number|id)\b",
            r"\bunits\s*consumed\b",
            r"\bkwh\b",
        ],
    },
    {
        "type": "Academic Transcript / Marksheet",
        "description": "an academic transcript, marksheet, or degree certificate detailing courses, grades, or credits",
        "keywords": [
            "statement of marks", "grade card", "semester", "cgpa", "sgpa",
            "controller of examinations", "marksheet", "hall ticket", "admit card",
            "degree certificate", "bachelor of", "master of", "diploma in",
            "roll no", "enrollment no", "course code", "credits earned",
            "academic year", "examination results"
        ],
        "strong_patterns": [
            r"\bstatement\s*of\s*marks\b",
            r"\bgrade\s*card\b",
            r"\b(?:semester|sem)\s*[ivx0-9]+\b",
            r"\b(?:cgpa|sgpa)\b",
            r"\bcontroller\s*of\s*examinations\b",
            r"\broll\s*no\b",
        ],
    },
    {
        "type": "Commercial / Tax Invoice",
        "description": "a commercial or tax invoice detailing merchandise, GST breakdowns, or vendor billing",
        "keywords": [
            "tax invoice", "gstin", "gst invoice", "hsn code", "sac code",
            "bill to", "ship to", "cgst", "sgst", "igst", "purchase order",
            "delivery challan", "invoice number", "taxable value", "item description"
        ],
        "strong_patterns": [
            r"\btax\s*invoice\b",
            r"\bgstin\b",
            r"\bhsn\s*/?\s*sac\b",
            r"\b(?:cgst|sgst|igst)\b",
            r"\bbill\s*to\b",
        ],
    },
    {
        "type": "Resume / Curriculum Vitae",
        "description": "a personal curriculum vitae or resume detailing employment history, skills, and education",
        "keywords": [
            "curriculum vitae", "resume", "work experience", "skills summary",
            "education background", "career objective", "employment history",
            "professional experience", "declaration", "hobbies", "personal profile"
        ],
        "strong_patterns": [
            r"\bcurriculum\s*vitae\b",
            r"\bcareer\s*objective\b",
            r"\bwork\s*experience\b",
            r"\btechnical\s*skills\b",
        ],
    },
    {
        "type": "Personal Identity Document",
        "description": "a government-issued identity credential (such as PAN, Aadhaar, or Passport)",
        "keywords": [
            "aadhaar", "pan card", "income tax department", "permanent account number",
            "driving licence", "driver license", "passport", "voter id",
            "election commission of india", "unique identification authority", "uidai"
        ],
        "strong_patterns": [
            r"\bpermanent\s*account\s*number\b",
            r"\bincome\s*tax\s*department\b",
            r"\bunique\s*identification\s*authority\b",
            r"\belection\s*commission\s*of\s*india\b",
        ],
    },
    {
        "type": "Lease / Legal Agreement",
        "description": "a lease, rental deed, or legal agreement between contracting parties",
        "keywords": [
            "rental agreement", "lease deed", "stamp duty", "affidavit",
            "notary public", "court of", "deed of lease", "lessor", "lessee", "tenancy"
        ],
        "strong_patterns": [
            r"\brental\s*agreement\b",
            r"\blease\s*deed\b",
            r"\bnotary\s*public\b",
            r"\baffidavit\b",
        ],
    },
]

FDR_INDICATOR_KEYWORDS = [
    "fixed deposit", "term deposit", "fdr", "tdr", "stdr",
    "deposit receipt", "cumulative deposit", "reinvestment plan",
    "short term deposit", "special term deposit", "deposit account",
    "term deposit receipt", "interest rate", "maturity value",
    "principal amount", "fixed deposit receipt"
]


def extract_safe_snippets(text: str, detected_type: str, max_snippets: int = 3) -> List[str]:
    """
    Extracts short, sanitized non-sensitive snippets showing why the document was classified.
    Masks numbers longer than 4 digits, emails, and personal identification to preserve privacy.
    """
    snippets = []
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 5]

    for line in lines:
        if len(snippets) >= max_snippets:
            break
        lower_line = line.lower()
        # Find lines matching typical indicators for this type
        if any(w in lower_line for w in ["meter", "consumer", "bill", "invoice", "grade", "semester", "resume", "experience", "pan", "tax", "units"]):
            # Sanitize: mask 5+ digit numbers and email-like patterns
            sanitized = re.sub(r"\b\d{5,}\b", "XXXXX", line)
            sanitized = re.sub(r"[\w\.-]+@[\w\.-]+", "[EMAIL]", sanitized)
            sanitized = sanitized[:80].strip()
            if sanitized and sanitized not in snippets:
                snippets.append(sanitized)

    return snippets


def classify_document(
    text: str,
    filename: str = "",
    is_unreadable: bool = False,
    ocr_unavailable: bool = False,
    is_corrupt: bool = False,
    bank_matched: Optional[str] = None,
    fdr_number_matched: Optional[str] = None,
    amount_matched: Optional[Any] = None,
    dates_matched: int = 0,
    lien_matched: Optional[str] = None,
) -> DocumentClassificationResult:
    """
    Evaluates extracted text and domain features to produce a structured document classification.
    Adheres strictly to safety rules:
      - Never claims authenticity or fraud.
      - Never labels a file 'wrong' or 'unrelated' if OCR is unavailable.
      - Uses conservative thresholds and honest confidence scores.
      - Discloses estimates as automated indicators.
    """
    # Guard 1: Corrupt or unsupported document
    if is_corrupt:
        return DocumentClassificationResult(
            status="corrupt_or_unsupported",
            confidence=0.0,
            classification_reasons=["The file format is corrupt, encrypted, or unsupported for processing."],
            detected_document_type=None,
            content_summary="The system cannot determine what the file contains because the file is corrupt or unreadable.",
            is_fdr_candidate=False,
            submission_blocked=True,
        )

    # Guard 2: OCR engine unavailable
    if ocr_unavailable:
        return DocumentClassificationResult(
            status="ocr_unavailable",
            confidence=0.0,
            classification_reasons=[
                "The Tesseract OCR engine is not installed or unavailable on the server.",
                "Scanned or image documents cannot be parsed automatically.",
            ],
            detected_document_type=None,
            content_summary="Automated OCR is currently unavailable on this server. Document type could not be evaluated automatically.",
            is_fdr_candidate=True,
            submission_blocked=False,
        )

    # Guard 3: Completely unreadable scan or empty file
    if is_unreadable or not text or not text.strip():
        return DocumentClassificationResult(
            status="unreadable",
            confidence=0.0,
            classification_reasons=["No readable text or characters were detected in the uploaded file."],
            detected_document_type=None,
            content_summary="The system cannot determine what the file contains because no readable text was detected.",
            is_fdr_candidate=True,
            submission_blocked=False,
        )

    lower_text = text.lower()

    # --- 1. Evaluate FDR Evidence ---
    fdr_score = 0.0
    fdr_reasons = []

    # A. FDR terminology
    matched_fdr_terms = [kw for kw in FDR_INDICATOR_KEYWORDS if kw in lower_text]
    if matched_fdr_terms:
        term_pts = min(4.0, len(matched_fdr_terms) * 1.5)
        fdr_score += term_pts
        fdr_reasons.append(f"Contains Fixed Deposit / Term Deposit terminology: {', '.join(matched_fdr_terms[:3])}")

    # B. Bank Name
    if bank_matched:
        fdr_score += 2.5
        fdr_reasons.append(f"Recognized scheduled bank entity: {bank_matched}")
    elif any(b_kw in lower_text for b_kw in ["bank", "banking", "treasury"]):
        fdr_score += 1.0

    # C. Deposit / Certificate Number
    if fdr_number_matched:
        fdr_score += 2.0
        fdr_reasons.append(f"Identified deposit receipt / certificate number: {fdr_number_matched}")

    # D. Amount
    if amount_matched is not None:
        fdr_score += 1.5
        fdr_reasons.append("Identified deposit principal amount")

    # E. Dates (Issue / Maturity)
    if dates_matched >= 2:
        fdr_score += 2.0
        fdr_reasons.append("Identified deposit issue and maturity tenure dates")
    elif dates_matched == 1:
        fdr_score += 1.0

    # F. Lien / Security Terminology
    if lien_matched:
        fdr_score += 2.0
        fdr_reasons.append("Identified lien / AICTE security clause marking")

    # --- 2. Evaluate Unrelated Document Profiles ---
    best_unrelated_score = 0.0
    best_unrelated_profile = None
    best_matched_terms = []

    for profile in UNRELATED_PROFILES:
        matched_kw = [kw for kw in profile["keywords"] if kw in lower_text]
        pattern_matches = 0
        for pat in profile.get("strong_patterns", []):
            if re.search(pat, lower_text):
                pattern_matches += 1

        score = (len(matched_kw) * 1.0) + (pattern_matches * 2.0)
        if score > best_unrelated_score:
            best_unrelated_score = score
            best_unrelated_profile = profile
            best_matched_terms = matched_kw

    # --- 3. Decision Matrix ---
    # Scenario A: Strong unrelated profile match without sufficient FDR indicators
    has_fdr_core = bool(matched_fdr_terms) or (bank_matched is not None) or (fdr_number_matched is not None)
    is_unrelated_match = False
    if best_unrelated_profile and best_unrelated_score >= 2.0:
        if not has_fdr_core or fdr_score < 4.0:
            is_unrelated_match = True

    if is_unrelated_match:
        doc_type = best_unrelated_profile["type"]
        summary = (
            f"Automated estimate: This file appears to contain {best_unrelated_profile['description']} "
            f"rather than a bank Fixed Deposit Receipt."
        )
        evidence = [
            f"Document matches {doc_type} patterns (found: {', '.join(best_matched_terms[:4])})",
            "Document lacks required Fixed Deposit / Term Deposit keywords and banking receipt structure.",
        ]
        snippets = extract_safe_snippets(text, doc_type)
        confidence = min(0.95, 0.70 + (best_unrelated_score * 0.05))

        return DocumentClassificationResult(
            status="likely_unrelated",
            confidence=confidence,
            classification_reasons=evidence,
            detected_document_type=doc_type,
            content_summary=summary,
            extracted_snippets=snippets,
            is_fdr_candidate=False,
            submission_blocked=True,
        )

    # Scenario B: Strong FDR indicators
    if fdr_score >= 5.0:
        confidence = min(0.98, 0.75 + (fdr_score * 0.04))
        return DocumentClassificationResult(
            status="likely_fdr",
            confidence=confidence,
            classification_reasons=fdr_reasons,
            detected_document_type="Fixed Deposit Receipt",
            content_summary="Automated estimate: Document contains standard Fixed Deposit Receipt terminology and banking details.",
            extracted_snippets=[],
            is_fdr_candidate=True,
            submission_blocked=False,
        )

    # Scenario C: Some FDR indicators present, but incomplete (Needs Review)
    if fdr_score >= 2.5:
        confidence = min(0.75, 0.50 + (fdr_score * 0.05))
        return DocumentClassificationResult(
            status="possibly_fdr_needs_review",
            confidence=confidence,
            classification_reasons=fdr_reasons or ["Some deposit or banking terms identified, but receipt fields are partial."],
            detected_document_type="Possible FDR (Requires Verification)",
            content_summary="Automated estimate: Document contains some banking references, but specific Fixed Deposit receipt fields or labels are incomplete. Requires verification.",
            extracted_snippets=[],
            is_fdr_candidate=True,
            submission_blocked=False,
        )

    # Scenario D: Generic text without FDR terms
    words = re.findall(r"\w+", lower_text)
    if len(words) < 20:
        # Too little text to confidently determine category
        return DocumentClassificationResult(
            status="possibly_fdr_needs_review",
            confidence=0.35,
            classification_reasons=["Document text is very brief; standard FDR indicators could not be confirmed."],
            detected_document_type=None,
            content_summary="The system cannot determine what the file contains based on the available text. Please verify manually.",
            extracted_snippets=[],
            is_fdr_candidate=True,
            submission_blocked=False,
        )

    # Document has substantial text but zero FDR terms and no specific profile
    return DocumentClassificationResult(
        status="likely_unrelated",
        confidence=0.80,
        classification_reasons=[
            "Extracted text does not contain Fixed Deposit Receipt keywords, bank identifiers, or deposit tenure terms."
        ],
        detected_document_type="Unrelated Document",
        content_summary="Automated estimate: This file does not appear to be an FDR receipt as it contains no bank deposit or lien terms.",
        extracted_snippets=extract_safe_snippets(text, "Unrelated", max_snippets=2),
        is_fdr_candidate=False,
        submission_blocked=True,
    )
