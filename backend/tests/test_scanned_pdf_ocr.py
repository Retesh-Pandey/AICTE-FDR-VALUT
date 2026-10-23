import io
import os
from datetime import date
from decimal import Decimal
import pytest
import pymupdf
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.ocr.extract import ocr_extractor
from app.services.ocr.parsers import (
    parse_amount,
    parse_compounding,
    parse_date,
    parse_ifsc,
    parse_institution_id,
    parse_institution_name,
    parse_interest_rate,
    parse_lien_info,
    parse_tenure,
)


def create_selectable_pdf(text: str) -> bytes:
    """Creates a PDF with embedded selectable/searchable text."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 72), text, fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def create_scanned_raster_pdf(text_lines: list[str]) -> bytes:
    """
    Creates a scanned/image-only PDF: renders text onto a PIL raster image,
    then embeds the raster image into a PDF page with zero embedded text objects.
    """
    # 300 DPI equivalent image (e.g. 1200 x 1600)
    img = Image.new("RGB", (1200, 1600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    y_pos = 100
    for line in text_lines:
        draw.text((80, y_pos), line, fill=(0, 0, 0))
        y_pos += 60

    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_bytes = img_buf.getvalue()

    # Wrap pure raster image in PDF page with no text objects
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=img_bytes)
    pdf_buf = io.BytesIO()
    doc.save(pdf_buf)
    doc.close()
    return pdf_buf.getvalue()


class TestTesseractEngineRuntime:
    """Validates that Tesseract OCR and language data are operational in this runtime."""

    def test_tesseract_engine_and_english_lang_available(self):
        available, reason = ocr_extractor.check_ocr_engine_available(force_refresh=True)
        assert available is True, f"Tesseract OCR engine must be available. Detail: {reason}"
        diag = ocr_extractor.get_engine_diagnostic(force_refresh=True)
        assert diag["available"] is True
        assert diag["status"] == "available"
        assert "eng" in diag["languages"], f"English traineddata missing. Found: {diag['languages']}"
        assert diag["binary_path"] is not None
        assert os.path.isfile(diag["binary_path"])

    def test_ocr_diagnostic_api_endpoint(self, client: TestClient):
        response = client.get("/health/ocr")
        assert response.status_code == 200
        data = response.json()
        assert data["ocr_engine_available"] is True
        assert data["status"] in ("operational", "degraded")
        assert data["python_libraries"]["pytesseract"] is True

        response_v1 = client.get("/api/v1/health/ocr")
        assert response_v1.status_code == 200
        assert response_v1.json()["ocr_engine_available"] is True


class TestFieldParsers:
    """Validates domain-specific FDR field parsing with Indian banking receipts."""

    def test_indian_currency_amounts(self):
        test_cases = [
            ("Principal Amount: INR 1,50,00,000.00", Decimal("15000000.00")),
            ("INR 1,50,00,000.00", Decimal("15000000.00")),
            ("Deposit Amount: Rs. 50,00,000/-", Decimal("5000000.00")),
            ("Amount: ₹ 2,75,50,000.50", Decimal("27550000.50")),
            ("Sum of INR 25,00,000", Decimal("2500000.00")),
            ("₹1,00,00,000.00/-", Decimal("10000000.00")),
            ("Rs. 10,00,000.00", Decimal("1000000.00")),
        ]
        for text, expected in test_cases:
            parsed = parse_amount(text)
            assert parsed == expected, f"Failed for '{text}': got {parsed}, expected {expected}"

    def test_compounding_frequency(self):
        assert parse_compounding("Interest Rate: 7.10% p.a. (Quarterly Compound)") == "Quarterly Compound"
        assert parse_compounding("Compounded Monthly payout") == "Monthly Compound"
        assert parse_compounding("Half-Yearly Compounding") == "Half-Yearly Compound"
        assert parse_compounding("Annual Compounding Scheme") == "Annual Compound"
        assert parse_compounding("Cumulative Interest Option") == "Cumulative"
        assert parse_compounding("Interest payable at maturity") == "At Maturity"

    def test_tenure_parsing_and_calculation(self):
        # Explicit text
        assert parse_tenure("Period of Deposit: 60 Months") == "60 Months"
        assert parse_tenure("Tenure: 5 Years") == "5 Years"
        assert parse_tenure("Term: 36 Months") == "36 Months"
        # Date difference calculation
        calc = parse_tenure("", issue_date=date(2023, 11, 24), maturity_date=date(2028, 11, 24))
        assert "60 Months" in calc and "5 Years" in calc
        calc_3yr = parse_tenure("", issue_date=date(2024, 1, 1), maturity_date=date(2027, 1, 1))
        assert "36 Months" in calc_3yr and "3 Years" in calc_3yr

    def test_institution_identifier_and_name(self):
        text_id = "AICTE Permanent ID: 1-4928190\nInstitution Name: Apex Institute of Technology"
        assert parse_institution_id(text_id) == "1-4928190"
        assert "Apex Institute of Technology" in parse_institution_name(text_id)

        text_alt = "In Account With: Greater Noida Institute of Engineering & Technology\nInstitution ID: AICTE-1-8899221"
        assert parse_institution_id(text_alt) == "AICTE-1-8899221"
        assert "Greater Noida Institute of Engineering" in parse_institution_name(text_alt)


class TestSelectableAndScannedPDFOCR:
    """Verifies selectable text bypass and scanned image-only PDF OCR extraction."""

    def test_selectable_text_pdf_path(self):
        sample_doc = (
            "STATE BANK OF INDIA\n"
            "Parliament Street Branch, New Delhi · IFSC: SBIN0000691\n"
            "AICTE Permanent ID: 1-4928190\n"
            "Name of Institution: Apex Institute of Technology, Greater Noida\n"
            "Fixed Deposit Receipt No: SBI-FDR-39482019482\n"
            "Principal Amount: INR 1,50,00,000.00\n"
            "Interest Rate: 7.10% p.a. (Quarterly Compound)\n"
            "Tenure: 60 Months\n"
            "Date of Issue: 24/11/2023\n"
            "Maturity Date: 24/11/2028\n"
            "Lien in favor of Member Secretary, AICTE New Delhi\n"
        )
        pdf_bytes = create_selectable_pdf(sample_doc)

        res = ocr_extractor.extract_fields(pdf_bytes, "selectable_fdr.pdf")
        assert res["extraction_status"] == "success"
        assert res["bank_name"]["value"] == "State Bank of India"
        assert res["ifsc"]["value"] == "SBIN0000691"
        assert res["fdr_number"]["value"] == "SBI-FDR-39482019482"
        assert res["amount"]["value"] == "15000000.00"
        assert "7.10%" in res["interest_rate"]["value"]
        assert res["compounding"]["value"] == "Quarterly Compound"
        assert "60 Months" in res["tenure"]["value"]
        assert res["issue_date"]["value"] == "2023-11-24"
        assert res["maturity_date"]["value"] == "2028-11-24"
        assert "1-4928190" in res["institution_id"]["value"]
        assert "Apex Institute of Technology" in res["institution_name"]["value"]
        assert "AICTE" in res["lien_info"]["value"]
        assert res["engine_available"] is True

    def test_scanned_image_only_pdf_local_tesseract_ocr(self):
        """
        Tests pure image-only PDF (no embedded text stream).
        PyMuPDF renders page to 200 DPI pixmap and runs local Tesseract OCR.
        """
        lines = [
            "STATE BANK OF INDIA",
            "FDR Number: 39482019482",
            "Branch: Parliament Street",
            "IFSC Code: SBIN0000691",
            "Principal Amount: INR 1,50,00,000.00",
            "Interest Rate: 7.10% p.a.",
            "Issue Date: 24/11/2023",
            "Maturity Date: 24/11/2028",
            "Lien in favor of Member Secretary AICTE",
        ]
        scanned_pdf = create_scanned_raster_pdf(lines)

        # Confirm the PDF has ZERO embedded selectable text
        doc = pymupdf.open(stream=scanned_pdf, filetype="pdf")
        assert doc[0].get_text().strip() == "", "Scanned PDF test fixture must have zero embedded text"
        doc.close()

        # Run extraction through live local Tesseract OCR
        res = ocr_extractor.extract_fields(scanned_pdf, "scanned_receipt.pdf")

        # Tesseract should read the rendered page
        assert res["engine_available"] is True
        assert res["extraction_status"] in ("success", "partial")
        assert res["bank_name"]["value"] == "State Bank of India"
        assert res["amount"]["value"] == "15000000.00"
        assert res["issue_date"]["value"] == "2023-11-24"
        assert res["maturity_date"]["value"] == "2028-11-24"
        assert res["fdr_number"]["value"] is not None


class TestPrivacyAndAccessControl:
    """Verifies confidential document privacy, role security, and no external calls."""

    def test_ocr_endpoint_requires_authentication(self, client: TestClient):
        # Unauthenticated request must be rejected
        res = client.post("/api/v1/fdrs/ocr", files={"file": ("test.pdf", b"%PDF-1.4 empty", "application/pdf")})
        assert res.status_code == 401

    def test_ocr_response_masks_raw_text(self):
        sample_doc = (
            "STATE BANK OF INDIA\n"
            "FDR No: 1234567890\n"
            "Amount: INR 50,00,000.00\n"
            "Issue Date: 01/01/2024\n"
            "Maturity Date: 01/01/2029\n"
            + ("Sensitive Internal Bank Note " * 50)
        )
        pdf_bytes = create_selectable_pdf(sample_doc)
        res = ocr_extractor.extract_fields(pdf_bytes, "private_fdr.pdf")
        assert len(res["raw_text"]) <= 200, "Raw text snippet must be truncated for privacy"
        assert "Assistive data entry only" in res["disclaimer"]
