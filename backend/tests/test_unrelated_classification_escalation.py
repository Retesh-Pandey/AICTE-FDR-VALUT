import io
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.models import (
    DocumentSubmissionReview,
    FDRRecord,
    Institution,
    Notification,
    User,
    UserRole,
    WorkflowAuditLog,
)
from app.services.escalation import (
    adjudicate_document_submission,
    admin_extend_institution_hold,
    admin_unfreeze_institution_hold,
    check_and_update_institution_hold,
    count_confirmed_unrelated_strikes,
    record_submission_for_review,
    submit_institution_hold_appeal,
)
from app.services.ocr.classifier import classify_document
from app.services.ocr.extract import ocr_extractor


def create_pdf_with_text(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((40, 60), text, fontsize=11)
    b = doc.write()
    doc.close()
    return b


def test_synthetic_valid_fdr_classification():
    """1. Valid FDR receipt with bank, receipt number, amount, tenure, and AICTE lien."""
    fdr_text = """
    STATE BANK OF INDIA
    Parliament Street Branch, New Delhi | IFSC: SBIN0000691
    FIXED DEPOSIT RECEIPT / TERM DEPOSIT CERTIFICATE
    FDR No: SBI-FDR-982145
    Date of Issue: 15/01/2026
    Depositor: Apex Institute of Technology
    Principal Amount: Rs. 25,00,000.00
    Interest Rate: 7.25% p.a.
    Maturity Date: 15/01/2029
    Lien: Pledged exclusively in favor of Member Secretary AICTE New Delhi.
    """
    pdf_bytes = create_pdf_with_text(fdr_text)
    res = ocr_extractor.extract_fields(pdf_bytes, "valid_fdr.pdf")

    assert res["extraction_status"] == "success"
    assert res["classification"]["status"] == "likely_fdr"
    assert res["classification"]["confidence"] >= 0.80
    assert res["classification"]["is_fdr_candidate"] is True
    assert res["classification"]["submission_blocked"] is False
    assert res["fdr_number"]["value"] == "SBI-FDR-982145"
    assert res["bank_name"]["value"] == "State Bank of India"
    assert "Assistive data entry only" in res["disclaimer"]


def test_synthetic_unrelated_document_electricity_bill(client: TestClient, auth_headers):
    """2. Unrelated document (Electricity Bill) with readable text."""
    bill_text = """
    NORTH BIHAR POWER DISTRIBUTION COMPANY LIMITED (DISCOM)
    ELECTRICITY CONSUMER BILL & TARIFF INVOICE
    Consumer Number: 104928194
    Meter Number: MTR-98214
    Billing Period: 01-Jan-2026 to 31-Jan-2026
    Previous Meter Reading: 4120 kWh
    Current Meter Reading: 4680 kWh
    Total Units Consumed: 560 kWh
    Tariff Category: Commercial LT-2
    Connected Load: 15 kW
    Subdivision: Patna Central Electric Supply
    Total Bill Amount Due: Rs. 6,840.00
    Due Date For Payment: 15-Feb-2026
    """
    pdf_bytes = create_pdf_with_text(bill_text)
    res = ocr_extractor.extract_fields(pdf_bytes, "electricity_bill.pdf")

    assert res["classification"]["status"] == "likely_unrelated"
    assert res["classification"]["is_fdr_candidate"] is False
    assert res["classification"]["submission_blocked"] is True
    assert res["classification"]["detected_document_type"] == "Utility / Electricity Bill"
    assert "electricity or utility bill" in res["classification"]["content_summary"].lower()
    assert "Automated estimate" in res["classification"]["content_summary"]
    # Check that snippets are provided and sanitized
    assert len(res["classification"]["extracted_snippets"]) > 0

    # Ensure raw full text is NOT leaked in snippets (sanitized)
    for snip in res["classification"]["extracted_snippets"]:
        assert len(snip) <= 80

    # Test that submitting this file directly as an FDR by an institution is BLOCKED
    form_data = {
        "fdr_number": "FDR-BILL-001",
        "bank_name": "State Bank of India",
        "amount": "100000.00",
        "issue_date": "2026-01-15",
        "maturity_date": "2027-01-15",
    }
    files = {"file": ("electricity_bill.pdf", pdf_bytes, "application/pdf")}
    resp = client.post(
        "/api/v1/fdrs",
        headers={"Authorization": auth_headers["institution"]["Authorization"]},
        data=form_data,
        files=files,
    )
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "DOCUMENT_CLASSIFIED_UNRELATED"
    assert "This does not appear to be an FDR receipt" in err["message"]


def test_synthetic_unrelated_academic_transcript(client: TestClient, auth_headers):
    """3. Unrelated document: Academic mark sheet / transcript."""
    transcript_text = """
    UNIVERSITY OF TECHNOLOGY & APPLIED SCIENCES
    STATEMENT OF MARKS - SEMESTER IV EXAMINATION
    Roll No: 22BCSE1049
    Enrollment No: ENR-2022-88419
    Student Name: Candidate Student
    Course Code | Course Title | Credits Earned | Grade
    CS-401 | Database Management Systems | 4.0 | A+
    CS-402 | Theory of Computation | 4.0 | A
    CS-403 | Microprocessor Architecture | 4.0 | B+
    Semester SGPA: 8.65 | Cumulative CGPA: 8.42
    Controller of Examinations
    Date of Result Publication: 15-June-2025
    """
    pdf_bytes = create_pdf_with_text(transcript_text)
    res = ocr_extractor.extract_fields(pdf_bytes, "student_marksheet.pdf")

    assert res["classification"]["status"] == "likely_unrelated"
    assert res["classification"]["detected_document_type"] == "Academic Transcript / Marksheet"
    assert "academic transcript" in res["classification"]["content_summary"].lower()


def test_synthetic_unrelated_tax_invoice(client: TestClient, auth_headers):
    """4. Unrelated document: Commercial / Tax Invoice."""
    invoice_text = """
    TECH SUPPLY PRIVATE LIMITED
    TAX INVOICE / GST INVOICE
    GSTIN: 07AAAAA0000A1Z5
    Invoice Number: INV-2026-0941
    Invoice Date: 10-Jan-2026
    Bill To: Modern Engineering College
    Ship To: Campus Warehouse, Greater Noida
    HSN/SAC: 8471 | Description: High Performance Compute Server Nodes
    Taxable Value: Rs. 14,50,000.00
    CGST @ 9%: Rs. 1,30,500.00
    SGST @ 9%: Rs. 1,30,500.00
    Total Invoice Value: Rs. 17,11,000.00
    Payment Terms: Net 30 Days | Delivery Challan No: DC-9921
    """
    pdf_bytes = create_pdf_with_text(invoice_text)
    res = ocr_extractor.extract_fields(pdf_bytes, "tax_invoice.pdf")

    assert res["classification"]["status"] == "likely_unrelated"
    assert res["classification"]["detected_document_type"] == "Commercial / Tax Invoice"


def test_low_confidence_ambiguous_document():
    """5. Low-confidence ambiguous document without clear signals returns possibly_fdr_needs_review."""
    ambiguous_text = "General inquiry letter regarding technical campus building inspection schedule."
    pdf_bytes = create_pdf_with_text(ambiguous_text)
    res = ocr_extractor.extract_fields(pdf_bytes, "short_note.pdf")

    # Low confidence does not invent values and does not guess
    assert res["classification"]["status"] == "possibly_fdr_needs_review"
    assert res["classification"]["confidence"] <= 0.50
    assert "cannot determine what the file contains" in res["classification"]["content_summary"]


def test_unreadable_blank_document_no_hallucination():
    """6. Blank unreadable document states inability to determine content."""
    doc = pymupdf.open()
    doc.new_page(width=595, height=842)  # Completely blank page
    b = doc.write()
    doc.close()

    with patch.object(ocr_extractor, "check_ocr_engine_available", return_value=(True, "Engine operational")):
        with patch("pytesseract.image_to_string", return_value=""):
            res = ocr_extractor.extract_fields(b, "blank.pdf")
            assert res["extraction_status"] == "unreadable"
            assert res["classification"]["status"] == "unreadable"
            assert "cannot determine what the file contains" in res["classification"]["content_summary"]
            assert res["classification"]["submission_blocked"] is False  # Does not block manual submission


def test_missing_tesseract_does_not_label_wrong_or_create_strikes(db):
    """7. OCR outage / missing Tesseract must NOT label document wrong or create strikes."""
    doc = pymupdf.open()
    doc.new_page(width=595, height=842)
    b = doc.write()
    doc.close()

    with patch.object(ocr_extractor, "check_ocr_engine_available", return_value=(False, "Tesseract not installed")):
        res = ocr_extractor.extract_fields(b, "scan_receipt.pdf")

        assert res["extraction_status"] == "ocr_unavailable"
        assert res["classification"]["status"] == "ocr_unavailable"
        assert res["engine_available"] is False
        assert res["classification"]["submission_blocked"] is False
        assert "not installed" in res["status_detail"]

        # Ensure no strikes are created in the database
        inst = db.query(Institution).first()
        strikes = count_confirmed_unrelated_strikes(db, inst.id)
        assert strikes == 0


def test_duplicate_file_hash_does_not_create_duplicate_strikes(db):
    """8. Repeated submissions of the same file hash deduplicate strikes."""
    inst = db.query(Institution).first()
    officer = db.query(User).filter(User.role == UserRole.officer).first()
    same_hash = "abcdef112233445566778899aabbccddeeff00112233445566778899aabbccdd"

    # Attempt 1: Officer confirms as unrelated -> strike 1
    item1 = record_submission_for_review(
        db=db,
        institution_id=inst.id,
        filename="bill_attempt1.pdf",
        sha256_hash=same_hash,
        classification_dict={"status": "likely_unrelated", "confidence": 0.92},
    )
    adjudicate_document_submission(
        db=db,
        review_id=item1.id,
        decision="confirm_unrelated",
        reason="Confirmed electricity bill submission.",
        reviewer=officer,
    )
    assert count_confirmed_unrelated_strikes(db, inst.id) == 1

    # Attempt 2: Same file hash submitted again and adjudicated -> strike remains 1 (deduplicated)
    item2 = DocumentSubmissionReview(
        institution_id=inst.id,
        document_sha256=same_hash,
        filename="bill_attempt2_retry.pdf",
        classification="likely_unrelated",
        confidence=0.92,
        review_status="pending",
        is_strike=False,
    )
    db.add(item2)
    db.commit()

    adjudicate_document_submission(
        db=db,
        review_id=item2.id,
        decision="confirm_unrelated",
        reason="Repeated upload of identical electricity bill.",
        reviewer=officer,
    )

    # Strike count MUST remain 1 because sha256 is identical
    assert count_confirmed_unrelated_strikes(db, inst.id) == 1
    assert item2.is_strike is False


def test_seven_strike_escalation_triggers_review_hold_and_admin_unfreeze(client: TestClient, db, auth_headers):
    """
    9. 7 confirmed unrelated submissions within rolling window trigger temporary review hold.
    Existing read access remains intact; Admin can inspect audit trail and unfreeze hold.
    """
    # Create isolated test institution and user
    test_inst = Institution(
        id=uuid.uuid4(),
        aicte_id=f"AICTE-HOLD-TEST-{uuid.uuid4().hex[:6].upper()}",
        name="Escalation Test Institute of Engineering",
        region="Western",
    )
    db.add(test_inst)
    db.commit()

    officer = db.query(User).filter(User.role == UserRole.officer).first()
    admin = db.query(User).filter(User.role == UserRole.admin).first()

    # Simulate 6 distinct confirmed unrelated submissions (threshold is 7)
    for i in range(1, 7):
        h = f"unique_hash_{i}_{uuid.uuid4().hex}"
        rev = record_submission_for_review(
            db=db,
            institution_id=test_inst.id,
            filename=f"unrelated_{i}.pdf",
            sha256_hash=h,
            classification_dict={"status": "likely_unrelated", "confidence": 0.90},
        )
        adjudicate_document_submission(
            db=db,
            review_id=rev.id,
            decision="confirm_unrelated",
            reason=f"Confirmed unrelated file #{i}",
            reviewer=officer,
        )

    db.refresh(test_inst)
    assert count_confirmed_unrelated_strikes(db, test_inst.id) == 6
    assert test_inst.upload_hold_active is False  # Not yet held at 6

    # 7th confirmed unrelated submission triggers hold
    h7 = f"unique_hash_7_{uuid.uuid4().hex}"
    rev7 = record_submission_for_review(
        db=db,
        institution_id=test_inst.id,
        filename="unrelated_7_invoice.pdf",
        sha256_hash=h7,
        classification_dict={"status": "likely_unrelated", "confidence": 0.94},
    )
    adjudicate_document_submission(
        db=db,
        review_id=rev7.id,
        decision="confirm_unrelated",
        reason="Confirmed unrelated invoice #7",
        reviewer=officer,
    )

    db.refresh(test_inst)
    assert count_confirmed_unrelated_strikes(db, test_inst.id) == 7
    assert test_inst.upload_hold_active is True
    assert test_inst.upload_hold_until is not None
    assert "7 confirmed unrelated submissions" in test_inst.upload_hold_reason

    # Verify audit log entry was created
    audit_entry = (
        db.query(WorkflowAuditLog)
        .filter(WorkflowAuditLog.entity_id == test_inst.id, WorkflowAuditLog.action == "institution.upload_hold_placed")
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.actor_id == officer.id

    # Verify notification was sent
    notif = (
        db.query(Notification)
        .filter(Notification.type == "admin_escalation")
        .order_by(Notification.created_at.desc())
        .first()
    )
    assert notif is not None
    assert "Escalation Test Institute" in notif.message

    # Read access remains intact: Officer / Admin can list FDRs
    resp_fdrs = client.get(
        f"/api/v1/institutions/{test_inst.id}/fdrs",
        headers={"Authorization": auth_headers["officer"]["Authorization"]},
    )
    assert resp_fdrs.status_code == 200

    # Institution submits appeal
    test_user = User(
        id=uuid.uuid4(),
        email=f"registrar_{uuid.uuid4().hex[:6]}@testinst.edu",
        full_name="Registrar Test",
        role=UserRole.institution,
        institution_id=test_inst.id,
    )
    db.add(test_user)
    db.commit()

    submit_institution_hold_appeal(
        db=db,
        institution_id=test_inst.id,
        appeal_reason="Staff clerical oversight during batch upload. All future uploads have been verified.",
        user=test_user,
    )
    db.refresh(test_inst)
    assert test_inst.upload_hold_appealed_at is not None
    assert "clerical oversight" in test_inst.upload_hold_appeal_reason

    # Admin unfreezes hold with justification
    unfrozen_inst = admin_unfreeze_institution_hold(
        db=db,
        institution_id=test_inst.id,
        reason="Administrative review approved institution explanation following staff training verification.",
        admin_user=admin,
    )
    assert unfrozen_inst.upload_hold_active is False
    assert unfrozen_inst.upload_hold_until is None

    # Verify unfreeze audit log
    unfreeze_audit = (
        db.query(WorkflowAuditLog)
        .filter(WorkflowAuditLog.entity_id == test_inst.id, WorkflowAuditLog.action == "institution.upload_hold_removed")
        .first()
    )
    assert unfreeze_audit is not None
    assert unfreeze_audit.actor_id == admin.id


def test_hold_auto_expiry():
    """10. Upload hold automatically expires after configured duration."""
    mock_inst = Institution(
        id=uuid.uuid4(),
        aicte_id="AICTE-EXPIRY-001",
        name="Auto Expiry Institute",
        upload_hold_active=True,
        upload_hold_until=datetime.now(UTC) - timedelta(minutes=5),  # In the past
    )
    # Check that check_and_update_institution_hold detects expiry
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        db.add(mock_inst)
        db.commit()

        is_active = check_and_update_institution_hold(db, mock_inst)
        assert is_active is False
        assert mock_inst.upload_hold_active is False
    finally:
        db.close()
