from datetime import date
from decimal import Decimal
from pathlib import Path

from app.services.ocr.extract import ocr_extractor
from app.services.ocr.parsers import (
    find_fdr_number,
    match_bank,
    parse_amount,
    parse_date,
)


def test_parse_amount_indian_currency_formats():
    """Verify parse_amount handles >= 25 diverse Indian and international currency formats."""
    test_cases = [
        ("₹ 50,00,000.00", Decimal("5000000.00")),
        ("Rs. 5,00,000.00", Decimal("500000.00")),
        ("Rs 1,25,00,000.00", Decimal("12500000.00")),
        ("INR 10,50,000.50", Decimal("1050000.50")),
        ("50,00,000/-", Decimal("5000000.00")),
        ("₹ 1,00,00,000.00", Decimal("10000000.00")),
        ("Principal: Rs. 25,00,000", Decimal("2500000.00")),
        ("Amount (Rs.): 7,50,000.00", Decimal("750000.00")),
        ("Amount: 15,00,000/-", Decimal("1500000.00")),
        ("Deposit Amount: Rs. 2,00,00,000.00", Decimal("20000000.00")),
        ("Rs. 500000", Decimal("500000.00")),
        ("500000.00", Decimal("500000.00")),
        ("₹ 3,50,000", Decimal("350000.00")),
        ("INR 45,00,000/-", Decimal("4500000.00")),
        ("Rs. 10,000.00", Decimal("10000.00")),
        ("1,00,000", Decimal("100000.00")),
        ("25,00,000.75", Decimal("2500000.75")),
        ("Principal Amount: ₹ 8,00,000.00", Decimal("800000.00")),
        ("Rs 99,99,999.00", Decimal("9999999.00")),
        ("₹ 12,00,000/-", Decimal("1200000.00")),
        ("INR 5,50,000", Decimal("550000.00")),
        ("Amount: 30,00,000.00", Decimal("3000000.00")),
        ("Rs. 1,50,000/-", Decimal("150000.00")),
        ("₹ 75,00,000.00", Decimal("7500000.00")),
        ("1000000/-", Decimal("1000000.00")),
        ("Deposit: INR 65,00,000.00", Decimal("6500000.00")),
    ]

    for raw_str, expected in test_cases:
        res = parse_amount(raw_str)
        assert res == expected, f"Failed parsing '{raw_str}': expected {expected}, got {res}"


def test_parse_amount_invalid_inputs():
    """Verify parse_amount returns None for unparseable or non-numeric strings."""
    assert parse_amount("") is None
    assert parse_amount("NIL") is None
    assert parse_amount("None") is None
    assert parse_amount("Zero") is None
    assert parse_amount("No deposit") is None


def test_parse_date_formats():
    """Verify parse_date handles varied Indian banking date representations."""
    assert parse_date("15/01/2026") == date(2026, 1, 15)
    assert parse_date("15-01-2026") == date(2026, 1, 15)
    assert parse_date("15.01.2026") == date(2026, 1, 15)
    assert parse_date("15-Jan-2026") == date(2026, 1, 15)
    assert parse_date("15-JAN-2026") == date(2026, 1, 15)
    assert parse_date("15 January 2026") == date(2026, 1, 15)
    assert parse_date("15 Jan 2026") == date(2026, 1, 15)
    assert parse_date("2026-01-15") == date(2026, 1, 15)
    assert parse_date("January 15, 2026") == date(2026, 1, 15)
    assert parse_date("10-Mar-2029") == date(2029, 3, 10)
    assert parse_date("01/02/2027") == date(2027, 2, 1)


def test_parse_date_invalid_inputs():
    """Verify parse_date returns None on corrupt or out-of-range text."""
    assert parse_date("") is None
    assert parse_date("invalid-date-format") is None
    assert parse_date("32/13/2026") is None


def test_find_fdr_number():
    """Verify find_fdr_number identifies receipt identifiers across labels."""
    assert find_fdr_number("Receipt No: FDR-SBI-2026-8801") == "FDR-SBI-2026-8801"
    assert find_fdr_number("FDR Number: PNB/2026/0091") == "PNB/2026/0091"
    assert find_fdr_number("Fixed Deposit Receipt No: CAN-7762-2026") == "CAN-7762-2026"
    assert find_fdr_number("Deposit A/c No: 39482910382") == "39482910382"
    assert find_fdr_number("FDR No: HDFC-2026-1109") == "HDFC-2026-1109"
    assert find_fdr_number("Nothing here") is None


def test_match_bank():
    """Verify match_bank accurately identifies canonical Indian banks."""
    res1 = match_bank("State Bank of India Parliament Street Branch")
    assert res1 is not None
    assert res1[0] == "State Bank of India"
    assert res1[1] >= 0.90

    res2 = match_bank("Punjab National Bank Sector 62")
    assert res2 is not None
    assert res2[0] == "Punjab National Bank"

    res3 = match_bank("Canara Bank Bangalore")
    assert res3 is not None
    assert res3[0] == "Canara Bank"

    res4 = match_bank("HDFC Bank Connaught Place")
    assert res4 is not None
    assert res4[0] == "HDFC Bank"

    assert match_bank("Unknown Foreign Institution") is None


def test_ocr_extraction_on_sample_pdfs():
    """Verify OCR extractor on actual sample PDFs."""
    clean_path = Path("sample-data/fdr_clean.pdf")
    if clean_path.exists():
        clean_bytes = clean_path.read_bytes()
        extracted = ocr_extractor.extract_fields(clean_bytes, "fdr_clean.pdf")

        assert extracted["extraction_status"] == "success"
        assert extracted["bank_name"]["value"] == "State Bank of India"
        assert extracted["fdr_number"]["value"] == "FDR-SBI-2026-8801"
        assert extracted["amount"]["value"] == "5000000.00"
        assert extracted["issue_date"]["value"] == "2026-01-15"
        assert extracted["maturity_date"]["value"] == "2027-01-15"
        assert "disclaimer" in extracted
        assert "Assistive data entry only" in extracted["disclaimer"]

    # Test unreadable sample handles gracefully
    unreadable_path = Path("sample-data/fdr_unreadable_sample.pdf")
    if unreadable_path.exists():
        unreadable_bytes = unreadable_path.read_bytes()
        extracted_unreadable = ocr_extractor.extract_fields(unreadable_bytes, "fdr_unreadable_sample.pdf")
        assert extracted_unreadable["extraction_status"] == "unreadable"
        assert extracted_unreadable["bank_name"]["value"] is None
        assert extracted_unreadable["fdr_number"]["value"] is None
        assert "disclaimer" in extracted_unreadable
