import io
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
import pymupdf
from PIL import Image

from app.core.config import settings
from app.services.ocr.extract import OCRExtractor, ocr_extractor


def create_selectable_pdf(text: str) -> bytes:
    """Creates a synthetic PDF in-memory with embedded searchable text."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def create_multipage_selectable_pdf(pages_text: list[str]) -> bytes:
    """Creates a multi-page PDF in-memory with embedded searchable text."""
    doc = pymupdf.open()
    for t in pages_text:
        page = doc.new_page()
        page.insert_text((50, 72), t, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def create_blank_scanned_pdf() -> bytes:
    """Creates a synthetic raster-only PDF with an empty white image (scanned blank page)."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    # Blank white image inserted as raster pixmap
    img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    page.insert_image(page.rect, stream=img_byte_arr.getvalue())
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def create_scanned_image_bytes(text: str = "") -> bytes:
    """Creates a synthetic PNG image."""
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_selectable_text_pdf_extraction():
    """Verify that selectable/embedded PDFs extract fields directly without OCR."""
    sample_text = (
        "STATE BANK OF INDIA\n"
        "Fixed Deposit Receipt No: SBI994820194\n"
        "Branch Name: Parliament Street New Delhi\n"
        "Principal Amount: INR 50,00,000.00\n"
        "Issue Date: 10/01/2023\n"
        "Maturity Date: 10/01/2028\n"
        "ROI: 7.25%\n"
        "Lien in favor of Member Secretary AICTE New Delhi\n"
    )
    pdf_bytes = create_selectable_pdf(sample_text)

    res = ocr_extractor.extract_fields(pdf_bytes, "fdr_selectable.pdf")
    assert res["extraction_status"] == "success"
    assert res["fdr_number"]["value"] == "SBI994820194"
    assert res["bank_name"]["value"] == "State Bank of India"
    assert res["amount"]["value"] == "5000000.00"
    assert res["issue_date"]["value"] == "2023-01-10"
    assert res["maturity_date"]["value"] == "2028-01-10"
    assert "AICTE" in res["lien_info"]["value"]
    assert "Assistive data entry only" in res["disclaimer"]


def test_scanned_pdf_raster_tesseract_ocr():
    """
    Verify that scanned/image-only PDFs (no embedded text) trigger
    page rendering to pixmap and call Tesseract OCR.
    """
    scanned_pdf = create_blank_scanned_pdf()

    mock_ocr_text = (
        "PUNJAB NATIONAL BANK\n"
        "FDR No: PNB882736192\n"
        "Principal Amount: Rs. 25,00,000.00\n"
        "Issue Date: 15/03/2024\n"
        "Maturity Date: 15/03/2029\n"
        "Lien Marked To Member Secretary AICTE\n"
    )

    with patch.object(ocr_extractor, "check_ocr_engine_available", return_value=(True, "Tesseract v5.3 ready")):
        with patch("pytesseract.image_to_string", return_value=mock_ocr_text):
            res = ocr_extractor.extract_fields(scanned_pdf, "scanned_document.pdf")

            assert res["extraction_status"] == "success"
            assert res["fdr_number"]["value"] == "PNB882736192"
            assert res["bank_name"]["value"] == "Punjab National Bank"
            assert res["amount"]["value"] == "2500000.00"
            assert res["issue_date"]["value"] == "2024-03-15"
            assert res["maturity_date"]["value"] == "2029-03-15"


def test_standalone_image_ocr():
    """Verify PNG/JPEG standalone images run direct OCR with image preprocessing."""
    img_bytes = create_scanned_image_bytes()

    mock_text = (
        "CANARA BANK\n"
        "Deposit Receipt No: CAN554433221\n"
        "Amount: Rs. 10,00,000.00\n"
        "Date of Issue: 01/06/2022\n"
        "Maturity Date: 01/06/2027\n"
    )

    with patch.object(ocr_extractor, "check_ocr_engine_available", return_value=(True, "Tesseract ready")):
        with patch("pytesseract.image_to_string", return_value=mock_text):
            res = ocr_extractor.extract_fields(img_bytes, "receipt_scan.png")

            assert res["extraction_status"] == "success"
            assert res["bank_name"]["value"] == "Canara Bank"
            assert res["fdr_number"]["value"] == "CAN554433221"
            assert res["amount"]["value"] == "1000000.00"


def test_multipage_pdf_page_limit():
    """Verify that multi-page PDFs process across pages up to configurable limit."""
    pages = [
        "Page 1: STATE BANK OF INDIA FDR No: SBI11223344",
        "Page 2: Principal Amount: Rs. 15,00,000.00 Issue Date: 10/02/2024 Maturity Date: 10/02/2029",
    ]
    multipage_pdf = create_multipage_selectable_pdf(pages)

    res = ocr_extractor.extract_fields(multipage_pdf, "multipage_fdr.pdf")
    assert res["extraction_status"] in ("success", "partial")
    assert res["bank_name"]["value"] == "State Bank of India"
    assert res["fdr_number"]["value"] == "SBI11223344"
    assert res["amount"]["value"] == "1500000.00"


def test_missing_tesseract_does_not_label_customer_doc_as_unreadable():
    """
    CRITICAL REQUIREMENT:
    Do not label a missing Tesseract installation as an unreadable customer document!
    When Tesseract binary is absent on scanned/image uploads, status must be
    'ocr_unavailable' with engine_available=False, NOT 'unreadable'.
    """
    scanned_pdf = create_blank_scanned_pdf()

    with patch.object(
        ocr_extractor,
        "check_ocr_engine_available",
        return_value=(False, "Tesseract executable binary not found in system PATH.")
    ):
        res = ocr_extractor.extract_fields(scanned_pdf, "scanned_doc.pdf")

        assert res["extraction_status"] == "ocr_unavailable"
        assert res["engine_available"] is False
        assert "Tesseract OCR engine is not installed" in res["status_detail"]


def test_unreadable_blank_document():
    """When document is scanned but OCR detects zero text characters, status is 'unreadable'."""
    scanned_pdf = create_blank_scanned_pdf()

    with patch.object(ocr_extractor, "check_ocr_engine_available", return_value=(True, "Tesseract v5.3 ready")):
        with patch("pytesseract.image_to_string", return_value=""):
            res = ocr_extractor.extract_fields(scanned_pdf, "blank_scan.pdf")

            assert res["extraction_status"] == "unreadable"
            assert "No readable text" in res["status_detail"]
            assert res["engine_available"] is True


def test_corrupt_file_handling():
    """Corrupt or non-PDF/image bytes should safely return 'processing_error' without 500 error."""
    corrupt_bytes = b"NOT_A_VALID_PDF_OR_IMAGE_DATA_RANDOM_GARBAGE_BYTES_12345678"
    res = ocr_extractor.extract_fields(corrupt_bytes, "corrupt.pdf")

    assert res["extraction_status"] == "processing_error"
    assert res["fdr_number"]["value"] is None


def test_oversized_file_handling():
    """Files exceeding MAX_UPLOAD_MB must be safely rejected."""
    oversized_bytes = b"%PDF-1.4" + b"0" * (11 * 1024 * 1024)
    res = ocr_extractor.extract_fields(oversized_bytes, "large.pdf")

    assert res["extraction_status"] == "processing_error"
    assert "exceeds maximum limit" in res["status_detail"]


def test_ocr_health_diagnostic_endpoint(client):
    """Verify GET /health/ocr returns operational/degraded diagnostic safely."""
    res = client.get("/health/ocr")
    assert res.status_code == 200
    data = res.json()

    assert "status" in data
    assert "ocr_engine_available" in data
    assert "python_libraries" in data
    assert data["python_libraries"]["pymupdf"] is True
    assert data["python_libraries"]["pillow"] is True
    assert data["python_libraries"]["pytesseract"] is True
    assert "disclaimer" in data

    # Also check /api/v1/health/ocr
    res_v1 = client.get("/api/v1/health/ocr")
    assert res_v1.status_code == 200
    assert res_v1.json()["status"] == data["status"]
