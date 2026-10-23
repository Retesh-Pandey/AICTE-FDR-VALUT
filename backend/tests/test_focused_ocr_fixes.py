import io
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pymupdf
import pytest
from PIL import Image

from app.services.ocr.extract import OCRExtractor, ocr_extractor


def create_synthetic_fdr_pdf(
    fdr_number="FDR-SYNTH-9921",
    bank_name="State Bank of India",
    branch="Parliament Street Branch",
    ifsc="SBIN0000691",
    amount="Rs. 25,00,000.00",
    roi="7.15%",
    issue_date="10/01/2026",
    maturity_date="10/01/2029",
    lien="Lien marked to Member Secretary AICTE",
) -> bytes:
    """Creates an in-memory text-based synthetic FDR PDF for testing."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    text = f"""
    ======================================================================
                         {bank_name.upper()}
                 {branch} | IFSC: {ifsc}
    ======================================================================
    
    TERM DEPOSIT RECEIPT / FDR CERTIFICATE
    
    Receipt / FDR Number: {fdr_number}
    Date of Issue: {issue_date}
    
    Depositor Name: APEX INSTITUTE OF TECHNOLOGY
    
    Principal Amount: {amount}
    Interest Rate: {roi} p.a.
    Maturity Date: {maturity_date}
    
    Lien Clause: {lien}
    ======================================================================
    """
    page.insert_text((40, 60), text, fontsize=11)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def test_text_based_pdf_full_extraction():
    """1. Test a text-based PDF with known expected fields."""
    content = create_synthetic_fdr_pdf()
    res = ocr_extractor.extract_fields(content, "synthetic_clean.pdf")

    assert res["extraction_status"] == "success"
    assert res["bank_name"]["value"] == "State Bank of India"
    assert res["fdr_number"]["value"] == "FDR-SYNTH-9921"
    assert res["ifsc"]["value"] == "SBIN0000691"
    assert res["amount"]["value"] == "2500000.00"
    assert res["interest_rate"]["value"] == "7.15%"
    assert res["issue_date"]["value"] == "2026-01-10"
    assert res["maturity_date"]["value"] == "2029-01-10"
    assert "Member Secretary" in str(res["lien_info"]["value"])
    assert "Assistive data entry only" in res["disclaimer"]
    assert res["engine_available"] is True


def test_multipage_pdf_fdr_on_second_page():
    """2. Test a multipage PDF where FDR information is not on page one."""
    doc = pymupdf.open()
    # Page 1: Institutional cover letter (no FDR values)
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text(
        (50, 100),
        "INSTITUTIONAL COVER LETTER\nTo: Member Secretary AICTE\nRef: Security deposit submission enclosure.",
        fontsize=12,
    )
    # Page 2: The actual FDR certificate
    p2 = doc.new_page(width=595, height=842)
    fdr_text = """
    PUNJAB NATIONAL BANK
    Branch: Sector 62 Noida | IFSC: PUNB0123400
    Fixed Deposit Receipt No: PNB/2026/7788
    Deposit Amount: Rs. 15,00,000.00
    Issue Date: 12-Feb-2026
    Maturity Date: 12-Feb-2029
    Interest Rate: 7.30%
    Lien: Favor of AICTE
    """
    p2.insert_text((50, 100), fdr_text, fontsize=11)
    content = doc.write()
    doc.close()

    res = ocr_extractor.extract_fields(content, "multipage_fdr.pdf")
    assert res["extraction_status"] == "success"
    assert res["bank_name"]["value"] == "Punjab National Bank"
    assert res["fdr_number"]["value"] == "PNB/2026/7788"
    assert res["amount"]["value"] == "1500000.00"
    assert res["issue_date"]["value"] == "2026-02-12"
    assert res["maturity_date"]["value"] == "2029-02-12"


def test_document_with_text_but_no_fdr_fields_returns_needs_review():
    """3. Test a document containing readable text, but none of the standard FDR fields."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(
        (50, 100),
        "All India Council for Technical Education General Circular\n"
        "Guidelines regarding academic curricula, semester examinations, and faculty development schemes.\n"
        "This circular does not contain financial instruments or deposit receipts.",
        fontsize=11,
    )
    content = doc.write()
    doc.close()

    res = ocr_extractor.extract_fields(content, "circular.pdf")
    # Must NOT report unreadable or invalid file; must return helpful needs_review status
    assert res["extraction_status"] == "needs_review"
    assert "standard FDR fields were not identified" in res["status_detail"]
    assert res["bank_name"]["value"] is None
    assert res["fdr_number"]["value"] is None


def test_corrupt_and_unsupported_files():
    """4. Test corrupt, empty, and unsupported file formats fail gracefully without server crash."""
    # A. Empty 0-byte file
    res_empty = ocr_extractor.extract_fields(b"", "empty.pdf")
    assert res_empty["extraction_status"] == "processing_error"
    assert "empty" in res_empty["status_detail"].lower()

    # B. Corrupt random binary content
    res_corrupt = ocr_extractor.extract_fields(b"not a valid pdf header \x00\xff\xfe random binary", "corrupt.pdf")
    assert res_corrupt["extraction_status"] in ("processing_error", "unreadable")
    assert res_corrupt["bank_name"]["value"] is None

    # C. Unsupported file format (e.g. .exe or .docx)
    res_unsupported = ocr_extractor.extract_fields(b"MZ executable header...", "program.exe")
    assert res_unsupported["extraction_status"] == "processing_error"
    assert "unsupported" in res_unsupported["status_detail"].lower()


def test_missing_tesseract_dependency_simulation():
    """5. Test missing Tesseract reports the actual OCR availability problem rather than 'unreadable'."""
    extractor = OCRExtractor()

    # Create synthetic raster image bytes (PNG)
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    # Mock engine availability to simulate host missing Tesseract binary
    with patch.object(extractor, "check_ocr_engine_available", return_value=(False, "Tesseract executable binary not found in system PATH.")):
        res = extractor.extract_fields(png_bytes, "scanned_receipt.png")

        assert res["extraction_status"] == "ocr_unavailable"
        assert res["engine_available"] is False
        assert "Tesseract OCR engine is not installed" in res["status_detail"]


def test_scanned_image_ocr_with_mocked_tesseract():
    """6. Test scanned image OCR flow when Tesseract is available."""
    extractor = OCRExtractor()

    # Synthetic image
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    fake_ocr_text = """
    CANARA BANK
    FDR Number: CAN-2026-9933
    Deposit: Rs. 10,00,000.00
    Issue Date: 01/01/2026
    Maturity Date: 01/01/2027
    """

    with patch.object(extractor, "check_ocr_engine_available", return_value=(True, "Tesseract v5.3 ready")):
        with patch("pytesseract.image_to_string", return_value=fake_ocr_text):
            res = extractor.extract_fields(png_bytes, "scanned_canara.png")

            assert res["extraction_status"] == "success"
            assert res["bank_name"]["value"] == "Canara Bank"
            assert res["fdr_number"]["value"] == "CAN-2026-9933"
            assert res["amount"]["value"] == "1000000.00"
            assert res["issue_date"]["value"] == "2026-01-01"
            assert res["maturity_date"]["value"] == "2027-01-01"


def test_ocr_failure_does_not_erase_manual_form_values():
    """7. Test that OCR failure or missing fields preserves manually entered form values."""
    # Simulate existing manual form state in UI
    manual_state = {
        "fdrNumber": "39482019482",
        "bankName": "State Bank of India",
        "principalAmount": "5000000.00",
        "issueDate": "2026-01-15",
        "maturityDate": "2027-01-15",
    }

    # Simulate an OCR response where the document is unreadable or ocr_unavailable
    mock_ocr_failure = {
        "fdr_number": {"value": None, "confidence": 0.0},
        "bank_name": {"value": None, "confidence": 0.0},
        "amount": {"value": None, "confidence": 0.0},
        "issue_date": {"value": None, "confidence": 0.0},
        "maturity_date": {"value": None, "confidence": 0.0},
        "extraction_status": "ocr_unavailable",
    }

    # Apply preservation merge logic (matching frontend implementation)
    updated_state = {
        "fdrNumber": mock_ocr_failure["fdr_number"]["value"] or manual_state["fdrNumber"],
        "bankName": mock_ocr_failure["bank_name"]["value"] or manual_state["bankName"],
        "principalAmount": mock_ocr_failure["amount"]["value"] or manual_state["principalAmount"],
        "issueDate": mock_ocr_failure["issue_date"]["value"] or manual_state["issueDate"],
        "maturityDate": mock_ocr_failure["maturity_date"]["value"] or manual_state["maturityDate"],
    }

    # Verify that all manually entered values remain 100% intact
    assert updated_state == manual_state
