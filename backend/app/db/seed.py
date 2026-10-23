import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.core.logging import logger
from app.core.security import get_password_hash
from app.db.models import (
    FDRDocument,
    FDRRecord,
    Institution,
    InstrumentStatus,
    MockBankRecord,
    Notification,
    ReleaseRequest,
    User,
    UserRole,
    VerificationLog,
    VerificationStatus,
    WorkflowStatus,
)
from datetime import timezone, datetime
from app.db.migrate import run_safe_migrations
from app.db.session import Base, SessionLocal, engine
from app.services.audit import write_audit_log


def seed_database(force: bool = False):
    run_safe_migrations(engine)
    db = SessionLocal()

    try:
        if force:
            logger.info("Clearing existing tables for complete re-seed...")
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.commit()
        else:
            existing_inst = db.query(Institution).first()
            if existing_inst:
                logger.info("Database already contains seeded records. Skipping re-seed.")
                return

        logger.info("Seeding comprehensive institutions, users, FDRs, documents, verification logs, notifications, and hash-chained audit ledger...")

        now = datetime.now(timezone.utc)

        # 1. Institutions
        inst1 = Institution(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            aicte_id="AICTE-1-4928190",
            name="Apex Institute of Technology, Greater Noida",
            region="Northern",
            address="Plot 12, Knowledge Park III, Greater Noida, UP - 201306",
            contact_email="registrar@apexinstitute.edu.in",
            source="PORTAL_REGISTRY",
            last_synced_at=now,
        )
        inst2 = Institution(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            aicte_id="AICTE-1-7890123",
            name="National Institute of Engineering, Bengaluru",
            region="South-Western",
            address="Tech Ring Road, Whitefield, Bengaluru, KA - 560066",
            contact_email="principal@nie-blr.edu.in",
            source="PORTAL_REGISTRY",
            last_synced_at=now,
        )
        inst3 = Institution(
            id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            aicte_id="AICTE-1-3456789",
            name="Delhi Technical Campus, New Delhi",
            region="North-Western",
            address="Institutional Area, Sector 22, Rohini, New Delhi - 110085",
            contact_email="director@dtc-delhi.edu.in",
            source="PORTAL_REGISTRY",
            last_synced_at=now,
        )
        db.add_all([inst1, inst2, inst3])
        db.commit()

        # 2. Users (all 3 roles) with secure hashed demo passwords (Demo@12345)
        demo_pwd_hash = get_password_hash("Demo@12345")
        user_inst = User(
            id=uuid.UUID("aaaaaaa1-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            email="institution@demo.test",
            full_name="Dr. R.K. Sharma (Principal / Custodian)",
            hashed_password=demo_pwd_hash,
            is_active=True,
            role=UserRole.institution,
            institution_id=inst1.id
        )
        user_officer = User(
            id=uuid.UUID("bbbbbbb2-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            email="officer@demo.test",
            full_name="P.K. Mathur, IRS (Regional Vigilance Officer)",
            hashed_password=demo_pwd_hash,
            is_active=True,
            role=UserRole.officer,
            institution_id=None
        )
        user_admin = User(
            id=uuid.UUID("ccccccc3-cccc-cccc-cccc-cccccccccccc"),
            email="admin@demo.test",
            full_name="Sovereign Administrator (Member Secretary Bureau)",
            hashed_password=demo_pwd_hash,
            is_active=True,
            role=UserRole.admin,
            institution_id=None
        )
        db.add_all([user_inst, user_officer, user_admin])
        db.commit()

        today = date.today()

        # 3. Genesis Audit Block
        write_audit_log(
            db=db,
            action="system.genesis",
            entity="system",
            entity_id=None,
            actor_id=user_admin.id,
            actor_role="admin",
            old_status=None,
            new_status="operational",
            remarks="Genesis cryptographic ledger block initialized for AICTE SIH26265 FDR Vault",
            payload={"protocol": "AICTE-SIH26265", "genesis_version": "1.0"}
        )
        db.commit()

        # 4. Seed FDRs across ALL 6 lifecycle statuses
        # 4a. Old Renewed/Superseded FDR
        fdr_old = FDRRecord(
            id=uuid.UUID("f0000000-0000-0000-0000-000000000000"),
            institution_id=inst1.id,
            fdr_number="PNB77490001-OLD",
            bank_name="Punjab National Bank",
            branch="Noida Sector 18 Branch (PUNB0123400)",
            amount=Decimal("4000000.00"),
            issue_date=today - timedelta(days=365 * 5),
            maturity_date=today - timedelta(days=15),
            lien_info="AICTE Joint Lien Clause",
            is_current=False,
            instrument_status=InstrumentStatus.renewed,
            verification_status=VerificationStatus.verified,
            workflow_status=WorkflowStatus.none,
            submitted_by=user_inst.id
        )
        db.add(fdr_old)
        db.commit()

        write_audit_log(
            db=db,
            action="fdr.renewed",
            entity="fdr",
            entity_id=fdr_old.id,
            actor_id=user_officer.id,
            actor_role="officer",
            old_status="active",
            new_status="renewed",
            remarks="FDR superseded by replacement instrument PNB77492011",
            payload={"fdr_number": fdr_old.fdr_number}
        )
        db.commit()

        # 4b. Active & Verified SBI FDR (Matching reference screenshot: 1.5 Crore)
        fdr1 = FDRRecord(
            id=uuid.UUID("f0000001-0000-0000-0000-000000000001"),
            institution_id=inst1.id,
            fdr_number="39482019482",
            bank_name="State Bank of India",
            branch="Parliament Street Branch, New Delhi (SBIN0000691)",
            amount=Decimal("15000000.00"),
            issue_date=today - timedelta(days=365 * 2),
            maturity_date=today + timedelta(days=365 * 3),
            lien_info="Lien marked exclusively in favor of Member Secretary, AICTE New Delhi. Encashment / Premature release restricted without explicit digital token from AICTE Vault.",
            is_current=True,
            instrument_status=InstrumentStatus.active,
            verification_status=VerificationStatus.verified,
            workflow_status=WorkflowStatus.none,
            submitted_by=user_inst.id
        )

        # 4c. Newly submitted FDR awaiting officer verification
        fdr2 = FDRRecord(
            id=uuid.UUID("f0000002-0000-0000-0000-000000000002"),
            institution_id=inst1.id,
            fdr_number="PNB77492011",
            bank_name="Punjab National Bank",
            branch="Noida Sector 18 Branch (PUNB0123400)",
            amount=Decimal("5000000.00"),
            issue_date=today - timedelta(days=10),
            maturity_date=today + timedelta(days=365 * 5),
            lien_info="Under sovereign joint lien to Member Secretary AICTE",
            previous_fdr_id=fdr_old.id,
            is_current=True,
            instrument_status=InstrumentStatus.submitted,
            verification_status=VerificationStatus.pending,
            workflow_status=WorkflowStatus.none,
            submitted_by=user_inst.id
        )

        # 4d. Renewal Due FDR (Maturity within 14 days!)
        fdr3 = FDRRecord(
            id=uuid.UUID("f0000003-0000-0000-0000-000000000003"),
            institution_id=inst2.id,
            fdr_number="CAN88910244",
            bank_name="Canara Bank",
            branch="MG Road Bengaluru Branch (CNRB0000123)",
            amount=Decimal("7500000.00"),
            issue_date=today - timedelta(days=365 * 5),
            maturity_date=today + timedelta(days=14),
            lien_info="AICTE Member Secretary joint pledge",
            is_current=True,
            instrument_status=InstrumentStatus.renewal_due,
            verification_status=VerificationStatus.verified,
            workflow_status=WorkflowStatus.none,
            submitted_by=user_inst.id
        )

        # 4e. Matured FDR needing compliance review
        fdr4 = FDRRecord(
            id=uuid.UUID("f0000004-0000-0000-0000-000000000004"),
            institution_id=inst3.id,
            fdr_number="BOB11029384",
            bank_name="Bank of Baroda",
            branch="Connaught Place New Delhi (BARB0CONNAU)",
            amount=Decimal("3500000.00"),
            issue_date=today - timedelta(days=365 * 5 + 30),
            maturity_date=today - timedelta(days=2),
            lien_info="Lien favor AICTE",
            is_current=True,
            instrument_status=InstrumentStatus.matured,
            verification_status=VerificationStatus.verified,
            workflow_status=WorkflowStatus.none,
            submitted_by=user_inst.id
        )

        # 4f. Released FDR (Fully processed release request under sovereign authorization)
        fdr5 = FDRRecord(
            id=uuid.UUID("f0000005-0000-0000-0000-000000000005"),
            institution_id=inst1.id,
            fdr_number="HDFC9920194",
            bank_name="HDFC Bank",
            branch="Kailash Colony New Delhi (HDFC0000045)",
            amount=Decimal("2500000.00"),
            issue_date=today - timedelta(days=365 * 6),
            maturity_date=today - timedelta(days=100),
            lien_info="Joint custody AICTE",
            is_current=True,
            instrument_status=InstrumentStatus.released,
            verification_status=VerificationStatus.verified,
            workflow_status=WorkflowStatus.completed,
            submitted_by=user_inst.id
        )

        # 4g. Discrepancy flagged FDR
        fdr6 = FDRRecord(
            id=uuid.UUID("f0000006-0000-0000-0000-000000000006"),
            institution_id=inst2.id,
            fdr_number="ICIC5501928",
            bank_name="ICICI Bank",
            branch="Indiranagar Branch, Bengaluru (ICIC0000100)",
            amount=Decimal("4500000.00"),
            issue_date=today - timedelta(days=60),
            maturity_date=today + timedelta(days=365 * 3),
            lien_info="AICTE Joint Lien",
            is_current=True,
            instrument_status=InstrumentStatus.submitted,
            verification_status=VerificationStatus.discrepancy,
            workflow_status=WorkflowStatus.none,
            submitted_by=user_inst.id
        )

        db.add_all([fdr1, fdr2, fdr3, fdr4, fdr5, fdr6])
        db.commit()

        # Audit creation of current FDRs
        for fdr in [fdr1, fdr2, fdr3, fdr4, fdr5, fdr6]:
            write_audit_log(
                db=db,
                action="fdr.created",
                entity="fdr",
                entity_id=fdr.id,
                actor_id=user_inst.id,
                actor_role="institution",
                old_status=None,
                new_status=fdr.instrument_status.value,
                remarks=f"Initial submission of FDR {fdr.fdr_number} by {fdr.institution.name}",
                payload={"bank_name": fdr.bank_name, "amount": str(fdr.amount)}
            )
        db.commit()

        # 5. Seed FDR Documents
        doc1 = FDRDocument(
            id=uuid.UUID("d0000001-0000-0000-0000-000000000001"),
            fdr_id=fdr1.id,
            storage_path="fdr-documents/sbi_39482019482_receipt.pdf",
            doc_type="fdr_receipt",
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            ocr_raw_text="STATE BANK OF INDIA TERM DEPOSIT ADVICE 39482019482 INR 1,50,00,000.00 AICTE JOINT LIEN",
            extracted_json={
                "fdr_number": {"value": "39482019482", "confidence": 0.994},
                "bank_name": {"value": "State Bank of India", "confidence": 0.989},
                "amount": {"value": "15000000.00", "confidence": 0.987},
                "issue_date": {"value": "2023-11-24", "confidence": 0.982},
                "maturity_date": {"value": "2028-11-24", "confidence": 0.962}
            },
            uploaded_by=user_inst.id
        )
        db.add(doc1)

        # 6. Seed Verification Logs
        vlog1 = VerificationLog(
            id=uuid.UUID("eb000001-0000-0000-0000-000000000001"),
            fdr_id=fdr1.id,
            source="SIMULATED_BANK",
            submitted_values={"amount": "15000000.00", "bank_name": "State Bank of India", "fdr_number": "39482019482"},
            confirmed_values={"amount": "15000000.00", "bank_name": "State Bank of India", "fdr_number": "39482019482", "status": "CONFIRMED"},
            discrepancies=[],
            outcome=VerificationStatus.verified,
            resolved_by=user_officer.id,
            resolution_note="Bank confirmation verified against SBI ledger via simulated core banking bridge."
        )

        vlog2 = VerificationLog(
            id=uuid.UUID("eb000002-0000-0000-0000-000000000002"),
            fdr_id=fdr6.id,
            source="SIMULATED_BANK",
            submitted_values={"amount": "4500000.00", "bank_name": "ICICI Bank", "fdr_number": "ICIC5501928"},
            confirmed_values={"amount": "4000000.00", "bank_name": "ICICI Bank", "fdr_number": "ICIC5501928", "status": "AMOUNT_MISMATCH"},
            discrepancies=[{"field": "amount", "submitted": "4500000.00", "confirmed": "4000000.00"}],
            outcome=VerificationStatus.discrepancy,
            resolved_by=None,
            resolution_note="Amount differs between document and bank confirmation — needs review."
        )
        db.add_all([vlog1, vlog2])

        # 7. Seed Release Requests
        rel1 = ReleaseRequest(
            id=uuid.UUID("ee000001-0000-0000-0000-000000000001"),
            fdr_id=fdr5.id,
            requested_by=user_inst.id,
            reason="Course closure and statutory deposit refund compliance completed under AICTE Approval Process Handbook norm.",
            stage=WorkflowStatus.completed,
            assigned_officer=user_officer.id,
            remarks="Completed release approved by Member Secretary Bureau."
        )
        db.add(rel1)

        # 8. Seed Notifications
        n1 = Notification(
            id=uuid.UUID("ed000001-0000-0000-0000-000000000001"),
            user_id=user_inst.id,
            fdr_id=fdr3.id,
            type="maturity_15",
            milestone="maturity_15",
            message="FDR CAN88910244 matures in 14 days. Renewal receipt required to avoid compliance review."
        )
        n2 = Notification(
            id=uuid.UUID("ed000002-0000-0000-0000-000000000002"),
            user_id=user_officer.id,
            fdr_id=fdr4.id,
            type="matured",
            milestone="matured",
            message="FDR BOB11029384 has matured. Review required under applicable AICTE norms."
        )
        n3 = Notification(
            id=uuid.UUID("ed000003-0000-0000-0000-000000000003"),
            user_id=user_officer.id,
            fdr_id=fdr6.id,
            type="discrepancy",
            milestone="discrepancy",
            message="Discrepancy flagged: ICICI Bank FDR ICIC5501928 has an amount mismatch between submission and bank record."
        )
        db.add_all([n1, n2, n3])

        # 9. Mock Bank Records for Simulated Verification Adapter
        bank1 = MockBankRecord(
            fdr_number="39482019482",
            bank_name="State Bank of India",
            branch="Parliament Street Branch, New Delhi",
            amount=Decimal("15000000.00"),
            issue_date=today - timedelta(days=365 * 2),
            maturity_date=today + timedelta(days=365 * 3),
            lien_marked=True,
            status="CONFIRMED"
        )
        bank2 = MockBankRecord(
            fdr_number="PNB77492011",
            bank_name="Punjab National Bank",
            branch="Noida Sector 18 Branch",
            amount=Decimal("5000000.00"),
            issue_date=today - timedelta(days=10),
            maturity_date=today + timedelta(days=365 * 5),
            lien_marked=True,
            status="CONFIRMED"
        )
        bank3 = MockBankRecord(
            fdr_number="CAN88910244",
            bank_name="Canara Bank",
            branch="MG Road Bengaluru Branch",
            amount=Decimal("7500000.00"),
            issue_date=today - timedelta(days=365 * 5),
            maturity_date=today + timedelta(days=14),
            lien_marked=True,
            status="CONFIRMED"
        )
        bank4 = MockBankRecord(
            fdr_number="ICIC5501928",
            bank_name="ICICI Bank",
            branch="Indiranagar Branch, Bengaluru",
            amount=Decimal("4000000.00"),
            issue_date=today - timedelta(days=60),
            maturity_date=today + timedelta(days=365 * 3),
            lien_marked=True,
            status="AMOUNT_MISMATCH"
        )
        db.add_all([bank1, bank2, bank3, bank4])
        db.commit()

        logger.info("Comprehensive seeding completed successfully across all required entities.")

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database(force=True)
