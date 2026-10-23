import os
from pathlib import Path
import pymupdf

SAMPLE_DIR = Path("sample-data")
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)


def create_clean_fdr():
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4 size
    text = """
    ======================================================================
                         STATE BANK OF INDIA
                 PARLIAMENT STREET BRANCH, NEW DELHI (00691)
    ======================================================================
    
    SPECIAL TERM DEPOSIT / FIXED DEPOSIT RECEIPT
    
    Receipt No: FDR-SBI-2026-8801
    Account No: 39482910382
    Date of Issue: 15/01/2026
    
    Received from:
    APEX INSTITUTE OF TECHNOLOGY
    AICTE ID: AICTE-1-4928190
    
    Principal Amount: Rs. 50,00,000.00
    (Rupees Fifty Lakh Only)
    
    Term of Deposit: 12 Months
    Interest Rate: 7.25% p.a.
    Maturity Date: 15/01/2027
    Maturity Value: ₹ 53,72,500.00
    
    Lien Marked To: Member Secretary, All India Council for Technical Education
    Branch Code: 00691
    Authorized Signatory: SBI-DELHI-BRANCH-MGR
    ======================================================================
    """
    page.insert_text((40, 60), text, fontsize=11)
    doc.save(SAMPLE_DIR / "fdr_clean.pdf")
    doc.close()
    print("Generated sample-data/fdr_clean.pdf")


def create_lakh_crore_fdr():
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    text = """
    ======================================================================
                       PUNJAB NATIONAL BANK
                   SECTOR 62 BRANCH, NOIDA (UP)
    ======================================================================
    
    FIXED DEPOSIT RECEIPT
    
    FDR Number: PNB/2026/0091
    Customer ID: PNB9821038
    Date of Deposit: 10-Mar-2026
    
    Depositor:
    BHARAT POLYTECHNIC COLLEGE
    
    Deposit Amount: Rs. 1,25,00,000.00
    (Rupees One Crore Twenty Five Lakh Only)
    
    Tenure: 36 Months
    Interest Rate: 7.40%
    Date of Maturity: 10-Mar-2029
    
    Lien: Marked in favor of AICTE
    Branch: Sector 62 Noida
    ======================================================================
    """
    page.insert_text((40, 60), text, fontsize=11)
    doc.save(SAMPLE_DIR / "fdr_lakh_crore_format.pdf")
    doc.close()
    print("Generated sample-data/fdr_lakh_crore_format.pdf")


def create_mismatch_case():
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    text = """
    ======================================================================
                            CANARA BANK
                       M.G. ROAD BRANCH, BENGALURU
    ======================================================================
    
    TERM DEPOSIT RECEIPT
    
    Receipt No: CAN-7762-2026
    Issue Date: 01/02/2026
    
    Institution: SARASWATI INSTITUTE OF SCIENCE
    
    Amount: INR 10,00,000.00
    (Rupees Ten Lakh Only)
    
    Maturity Date: 01/02/2027
    Lien: AICTE Security Deposit
    ======================================================================
    """
    page.insert_text((40, 60), text, fontsize=11)
    doc.save(SAMPLE_DIR / "fdr_mismatch_case.pdf")
    doc.close()
    print("Generated sample-data/fdr_mismatch_case.pdf")


def create_unreadable_sample():
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    # Blank page without text
    doc.save(SAMPLE_DIR / "fdr_unreadable_sample.pdf")
    doc.close()
    print("Generated sample-data/fdr_unreadable_sample.pdf")


if __name__ == "__main__":
    create_clean_fdr()
    create_lakh_crore_fdr()
    create_mismatch_case()
    create_unreadable_sample()
