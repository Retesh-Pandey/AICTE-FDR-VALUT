import io
import logging
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.ocr.classifier import DocumentClassificationResult, classify_document
from app.services.ocr.parsers import (
    find_fdr_number,
    match_bank,
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

logger = logging.getLogger(__name__)

DISCLAIMER_TEXT = "Assistive data entry only. Extraction does not prove document authenticity or verify bank records."


class OCRExtractor:
    def __init__(self):
        self._tesseract_checked: bool = False
        self._tesseract_available: bool = False
        self._tesseract_status: str = "engine_missing"  # 'available' | 'engine_missing' | 'language_data_missing'
        self._tesseract_reason: str = ""
        self._tesseract_version: Optional[str] = None
        self._tesseract_languages: List[str] = []
        self._tesseract_binary: Optional[str] = None

    def check_ocr_engine_available(self, force_refresh: bool = False) -> Tuple[bool, str]:
        """
        Validates if Tesseract OCR executable and Python wrapper are functional,
        distinguishing between:
          - OCR engine available
          - OCR engine executable missing
          - Language data (e.g. 'eng.traineddata') missing
        Caches result to avoid repeatedly executing version probes.
        """
        if self._tesseract_checked and not force_refresh:
            return self._tesseract_available, self._tesseract_reason

        # 1. Verify Pillow import
        try:
            from PIL import Image, ImageEnhance, ImageOps
        except ImportError as e:
            self._tesseract_checked = True
            self._tesseract_available = False
            self._tesseract_status = "engine_missing"
            self._tesseract_reason = f"Pillow library is missing: {e}"
            return False, self._tesseract_reason

        # 2. Verify pytesseract import
        try:
            import pytesseract
        except ImportError as e:
            self._tesseract_checked = True
            self._tesseract_available = False
            self._tesseract_status = "engine_missing"
            self._tesseract_reason = f"pytesseract library is missing: {e}"
            return False, self._tesseract_reason

        # 3. Locate Tesseract executable binary
        cmd_candidates = []
        if settings.TESSERACT_CMD:
            cmd_candidates.append(settings.TESSERACT_CMD)

        path_lookup = shutil.which("tesseract")
        if path_lookup:
            cmd_candidates.append(path_lookup)

        # Standard Windows default locations
        if os.name == "nt":
            standard_win_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
                os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
                r"C:\Users\retes\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
            ]
            for wp in standard_win_paths:
                if os.path.isfile(wp) and wp not in cmd_candidates:
                    cmd_candidates.append(wp)

        found_binary = None
        for cand in cmd_candidates:
            if cand and (os.path.isfile(cand) or shutil.which(cand)):
                found_binary = cand
                break

        if not found_binary:
            self._tesseract_checked = True
            self._tesseract_available = False
            self._tesseract_status = "engine_missing"
            self._tesseract_reason = (
                "Tesseract executable binary not found in system PATH or standard locations. "
                "For scanned document OCR, install Tesseract OCR on the host (e.g. apt install tesseract-ocr, "
                "or Windows installer) or set TESSERACT_CMD."
            )
            return False, self._tesseract_reason

        self._tesseract_binary = found_binary

        # Configure TESSDATA_PREFIX if not already set and tessdata directory exists alongside binary
        tessdata_dir = os.path.join(os.path.dirname(found_binary), "tessdata")
        if os.path.isdir(tessdata_dir) and "TESSDATA_PREFIX" not in os.environ:
            os.environ["TESSDATA_PREFIX"] = tessdata_dir

        # Set and test execution & version
        try:
            pytesseract.pytesseract.tesseract_cmd = found_binary
            ver = str(pytesseract.get_tesseract_version())
            self._tesseract_version = ver
        except Exception as e:
            self._tesseract_checked = True
            self._tesseract_available = False
            self._tesseract_status = "engine_missing"
            self._tesseract_reason = f"Tesseract execution failed: {e}"
            return False, self._tesseract_reason

        # Check language data availability (tessdata check)
        langs = []
        try:
            langs = pytesseract.get_languages()
            self._tesseract_languages = langs
        except Exception as e:
            logger.debug(f"Could not retrieve languages via pytesseract: {e}")

        if langs and "eng" not in langs:
            self._tesseract_checked = True
            self._tesseract_available = False
            self._tesseract_status = "language_data_missing"
            self._tesseract_reason = (
                f"Tesseract binary found at {found_binary}, but required English language data "
                f"('eng.traineddata') is missing. Available languages: {langs}."
            )
            return False, self._tesseract_reason

        self._tesseract_checked = True
        self._tesseract_available = True
        self._tesseract_status = "available"
        self._tesseract_reason = f"Tesseract v{ver} operational at {found_binary}"
        return True, self._tesseract_reason

    def get_engine_diagnostic(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Returns structured diagnostic status of OCR subsystem."""
        self.check_ocr_engine_available(force_refresh=force_refresh)
        return {
            "available": self._tesseract_available,
            "status": self._tesseract_status,
            "reason": self._tesseract_reason,
            "version": self._tesseract_version,
            "languages": self._tesseract_languages,
            "binary_path": self._tesseract_binary,
        }

    def detect_file_type(self, content: bytes, filename: str) -> str:
        """
        Inspects magic bytes and filename extension.
        Returns: 'pdf', 'png', 'jpeg', or 'unsupported'.
        """
        if content.startswith(b"%PDF"):
            return "pdf"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if content.startswith(b"\xff\xd8\xff"):
            return "jpeg"

        ext = filename.lower().split(".")[-1] if "." in filename else ""
        if ext == "pdf":
            return "pdf"
        elif ext == "png":
            return "png"
        elif ext in ("jpg", "jpeg"):
            return "jpeg"

        return "unsupported"

    def preprocess_image(self, img):
        """
        Normalizes EXIF orientation and applies grayscale + contrast boost for scan clarity.
        """
        try:
            from PIL import ImageEnhance, ImageOps

            # 1. Rotate upright based on EXIF camera orientation
            normalized = ImageOps.exif_transpose(img)
            # 2. Convert to grayscale
            gray = normalized.convert("L")
            # 3. Boost contrast to separate text from background grain
            enhancer = ImageEnhance.Contrast(gray)
            return enhancer.enhance(1.8)
        except Exception as e:
            logger.debug(f"Image preprocessing fallback used: {e}")
            return img

    def extract_text_from_pdf(self, content: bytes, max_pages: int = 10) -> Tuple[str, bool, str, bool]:
        """
        Extracts text from PDF.
        Returns: (extracted_text, is_scanned_pdf, error_message, engine_available)
        """
        text_parts = []
        pdf_opened = False
        doc = None

        # Strategy 1: PyMuPDF embedded text across all pages up to max_pages
        try:
            import pymupdf

            doc = pymupdf.open(stream=content, filetype="pdf")
            pdf_opened = True
            if doc.is_encrypted:
                doc.close()
                return "", False, "The PDF document is password-protected or encrypted.", True

            num_pages = min(len(doc), max_pages)
            for page_num in range(num_pages):
                page = doc[page_num]
                pt = page.get_text()
                if pt and pt.strip():
                    text_parts.append(pt.strip())
        except Exception as e:
            logger.debug(f"PyMuPDF embedded text extraction note: {e}")
        finally:
            if doc:
                try:
                    doc.close()
                except Exception:
                    pass

        # Strategy 2: pypdf fallback if empty
        if not text_parts or not "".join(text_parts).strip():
            try:
                import pypdf

                reader = pypdf.PdfReader(io.BytesIO(content))
                pdf_opened = True
                if getattr(reader, "is_encrypted", False):
                    return "", False, "The PDF document is password-protected or encrypted.", True

                num_pages = min(len(reader.pages), max_pages)
                for page_num in range(num_pages):
                    pt = reader.pages[page_num].extract_text()
                    if pt and pt.strip():
                        text_parts.append(pt.strip())
            except Exception as e:
                logger.debug(f"pypdf embedded text fallback note: {e}")

        # If neither library could even open or parse the PDF structure:
        if not pdf_opened:
            return "", False, "Document could not be processed: file is corrupt or is not a valid PDF document.", True

        embedded_text = "\n".join(text_parts).strip()
        words = re.findall(r"\w+", embedded_text)

        # If the PDF contains readable embedded text, use it directly without requiring raster OCR
        if len(words) >= 5:
            return embedded_text, False, "", True

        # Document has no embedded text or insufficient text -> Fallback to raster page OCR
        engine_ok, reason = self.check_ocr_engine_available()
        if not engine_ok:
            if embedded_text:
                return embedded_text, False, "", False
            logger.info("Scanned PDF detected without sufficient embedded text; Tesseract OCR is unavailable.")
            return (
                "",
                True,
                "This PDF is a scanned or image-only document. The Tesseract OCR engine is not installed on this server to read scans. Please enter FDR fields manually.",
                False,
            )

        # Strategy 3: Raster pixmap rendering + Tesseract OCR across pages
        try:
            import pymupdf
            import pytesseract
            from PIL import Image

            ocr_parts = []
            doc = pymupdf.open(stream=content, filetype="pdf")
            num_pages = min(len(doc), max_pages)
            for page_num in range(num_pages):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                preprocessed = self.preprocess_image(img)
                page_ocr = pytesseract.image_to_string(preprocessed, config="--psm 6")
                if not page_ocr.strip():
                    page_ocr = pytesseract.image_to_string(preprocessed)
                if page_ocr.strip():
                    ocr_parts.append(page_ocr.strip())
            doc.close()

            raster_text = "\n".join(ocr_parts).strip()
            if raster_text:
                combined = f"{embedded_text}\n{raster_text}".strip() if embedded_text else raster_text
                return combined, True, "", True
            elif embedded_text:
                return embedded_text, False, "", True

            return "", True, "", True
        except Exception as e:
            logger.warning(f"Raster OCR execution error: {e}")
            if embedded_text:
                return embedded_text, False, "", True
            return "", True, f"Error occurred during OCR image processing: {str(e)}", True

    def extract_text_from_image_bytes(self, content: bytes) -> Tuple[str, str, bool]:
        """
        Extracts text from PNG/JPG image bytes.
        Returns: (extracted_text, error_message, engine_available)
        """
        engine_ok, reason = self.check_ocr_engine_available()
        if not engine_ok:
            return (
                "",
                "Uploaded file is an image (PNG/JPG). The Tesseract OCR engine is not installed on this server to perform optical character recognition. Please enter FDR fields manually.",
                False,
            )

        try:
            from PIL import Image
            import pytesseract

            img = Image.open(io.BytesIO(content))
            preprocessed = self.preprocess_image(img)
            text = pytesseract.image_to_string(preprocessed, config="--psm 6")
            if not text.strip():
                text = pytesseract.image_to_string(preprocessed)
            return text.strip(), "", True
        except Exception as e:
            logger.warning(f"Image OCR execution error: {e}")
            return "", f"Failed to perform OCR on image: {str(e)}", True

    def extract_fields(self, content: bytes, filename: str) -> Dict[str, Any]:
        """
        Coordinates document reading, type detection, text extraction, domain parsing,
        and structured FDR vs non-FDR classification.
        Returns a structured dictionary matching OCRResponse.
        Never throws unhandled exceptions on corrupt, empty, or unsupported documents.
        Never logs sensitive document text or customer records.
        """
        engine_ok, engine_reason = self.check_ocr_engine_available()

        # Guard 1: Empty file check
        if not content or len(content) == 0:
            classification = classify_document("", filename=filename, is_unreadable=True)
            return self._build_empty_response(
                status="processing_error",
                status_detail="Uploaded file is empty (0 bytes). Please select a valid document.",
                engine_available=engine_ok,
                classification=classification,
            )

        # Guard 1b: File size check
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if len(content) > max_bytes:
            classification = classify_document("", filename=filename, is_corrupt=True)
            return self._build_empty_response(
                status="processing_error",
                status_detail=f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_MB}MB. Please upload a compressed document.",
                engine_available=engine_ok,
                classification=classification,
            )

        # Guard 2: File type detection
        file_type = self.detect_file_type(content, filename)
        if file_type == "unsupported":
            classification = classify_document("", filename=filename, is_corrupt=True)
            return self._build_empty_response(
                status="processing_error",
                status_detail="Unsupported file format. Please upload a PDF, PNG, JPG, or JPEG document.",
                engine_available=engine_ok,
                classification=classification,
            )

        raw_text = ""
        engine_available = True
        status_detail = None

        if file_type == "pdf":
            raw_text, is_scanned, err_msg, engine_available = self.extract_text_from_pdf(
                content, max_pages=settings.MAX_OCR_PAGES
            )
            if not engine_available:
                logger.info(f"PDF OCR unavailable for {filename}: {err_msg}")
                classification = classify_document("", filename=filename, ocr_unavailable=True)
                return self._build_empty_response(
                    status="ocr_unavailable",
                    status_detail=err_msg,
                    engine_available=False,
                    classification=classification,
                )
            if err_msg and not raw_text:
                classification = classify_document("", filename=filename, is_corrupt=True)
                return self._build_empty_response(
                    status="processing_error",
                    status_detail=err_msg,
                    engine_available=True,
                    classification=classification,
                )
        else:
            # Image file (PNG / JPEG)
            raw_text, err_msg, engine_available = self.extract_text_from_image_bytes(content)
            if not engine_available:
                logger.info(f"Image OCR unavailable for {filename}: {err_msg}")
                classification = classify_document("", filename=filename, ocr_unavailable=True)
                return self._build_empty_response(
                    status="ocr_unavailable",
                    status_detail=err_msg,
                    engine_available=False,
                    classification=classification,
                )
            if err_msg and not raw_text:
                classification = classify_document("", filename=filename, is_corrupt=True)
                return self._build_empty_response(
                    status="processing_error",
                    status_detail=err_msg,
                    engine_available=True,
                    classification=classification,
                )

        # Check if raw_text is completely empty (e.g. blank scan or unreadable file)
        if not raw_text.strip():
            logger.info(f"Document {filename} processed, but no readable text detected.")
            classification = classify_document("", filename=filename, is_unreadable=True)
            return self._build_empty_response(
                status="unreadable",
                status_detail="No readable text could be detected in this document (blank, faint, or unreadable scan). Please enter FDR fields manually.",
                engine_available=engine_available,
                classification=classification,
            )

        # Domain Parsing of Fields
        # 1. Bank matching
        bank_match = match_bank(raw_text)
        bank_name = bank_match[0] if bank_match else None
        bank_conf = bank_match[1] if bank_match else 0.0

        # 2. FDR Number
        fdr_num = find_fdr_number(raw_text)
        fdr_conf = 0.92 if fdr_num else 0.0

        # 3. IFSC Code
        ifsc_val = parse_ifsc(raw_text)
        ifsc_conf = 0.95 if ifsc_val else 0.0

        # 4. Branch detection
        branch = None
        branch_conf = 0.0
        branch_match = re.search(
            r"(?:Branch(?:\s*Name)?|Branch\s*Code)[:\s\-]+([A-Za-z0-9\s,\.]{4,35})",
            raw_text,
            re.IGNORECASE,
        )
        if branch_match:
            branch = branch_match.group(1).split("\n")[0].strip()
            branch_conf = 0.85

        # 5. Principal Amount parsing
        amount_val = parse_amount(raw_text)
        amount_str = str(amount_val) if amount_val is not None else None
        amount_conf = 0.94 if amount_val is not None else 0.0

        # 6. Interest Rate
        roi_val = parse_interest_rate(raw_text)
        roi_conf = 0.90 if roi_val else 0.0

        # 7. Issue and Maturity Dates
        issue_date_str = None
        issue_conf = 0.0
        maturity_date_str = None
        maturity_conf = 0.0

        issue_match = re.search(
            r"(?:Date of (?:Issue|Deposit)|Issue Date|Value Date|Effective Date)[:\s\-]+([^\n\r]{6,30})",
            raw_text,
            re.IGNORECASE,
        )
        if issue_match:
            parsed_issue = parse_date(issue_match.group(1))
            if parsed_issue:
                issue_date_str = parsed_issue.isoformat()
                issue_conf = 0.90

        maturity_match = re.search(
            r"(?:Maturity Date|Due Date|Expiry Date|Date of Maturity)[:\s\-]+([^\n\r]{6,30})",
            raw_text,
            re.IGNORECASE,
        )
        if maturity_match:
            parsed_mat = parse_date(maturity_match.group(1))
            if parsed_mat:
                maturity_date_str = parsed_mat.isoformat()
                maturity_conf = 0.90

        # Fallback date pairing if labels were not identified directly
        if not issue_date_str or not maturity_date_str:
            all_dates = []
            for line in raw_text.splitlines():
                d = parse_date(line)
                if d and d not in all_dates:
                    all_dates.append(d)

            all_dates.sort()
            if len(all_dates) >= 2:
                if not issue_date_str:
                    parsed_issue = all_dates[0]
                    issue_date_str = parsed_issue.isoformat()
                    issue_conf = 0.70
                if not maturity_date_str:
                    parsed_mat = all_dates[-1]
                    maturity_date_str = parsed_mat.isoformat()
                    maturity_conf = 0.70
            elif len(all_dates) == 1 and not issue_date_str:
                parsed_issue = all_dates[0]
                issue_date_str = parsed_issue.isoformat()
                issue_conf = 0.60

        # 8. Compounding & Tenure
        compounding_val = parse_compounding(raw_text)
        compounding_conf = 0.90 if compounding_val else 0.0

        tenure_val = parse_tenure(raw_text, parsed_issue if 'parsed_issue' in locals() else None, parsed_mat if 'parsed_mat' in locals() else None)
        tenure_conf = 0.90 if tenure_val else 0.0

        # 9. Institution Identifier & Name
        inst_id_val = parse_institution_id(raw_text)
        inst_id_conf = 0.92 if inst_id_val else 0.0

        inst_name_val = parse_institution_name(raw_text)
        inst_name_conf = 0.88 if inst_name_val else 0.0

        # 10. Lien Information
        lien_val = parse_lien_info(raw_text)
        lien_conf = 0.88 if lien_val else 0.0

        # --- Document Classification Evaluation ---
        dates_count = sum(1 for d in [issue_date_str, maturity_date_str] if d)
        classification = classify_document(
            text=raw_text,
            filename=filename,
            bank_matched=bank_name,
            fdr_number_matched=fdr_num,
            amount_matched=amount_val,
            dates_matched=dates_count,
            lien_matched=lien_val,
        )

        # Determine overall extraction status
        filled_count = sum(1 for v in [fdr_num, bank_name, amount_str, issue_date_str, maturity_date_str] if v)
        if filled_count >= 4:
            status = "success"
            status_detail = "FDR fields successfully extracted with high confidence. Please review before submission."
        elif filled_count >= 1:
            status = "partial"
            status_detail = "Partial extraction: some fields were extracted. Please review and fill in missing fields manually."
        else:
            status = "needs_review"
            status_detail = "Document text was recognized, but standard FDR fields were not identified. Please enter or verify fields manually."

        logger.info(
            f"OCR extraction completed for {filename}: status={status}, classification={classification.status}, text_length={len(raw_text)}"
        )

        effective_engine_available = engine_available or bool(raw_text.strip())

        return {
            "fdr_number": {"value": fdr_num, "confidence": fdr_conf},
            "bank_name": {"value": bank_name, "confidence": bank_conf},
            "ifsc": {"value": ifsc_val, "confidence": ifsc_conf},
            "branch": {"value": branch, "confidence": branch_conf},
            "amount": {"value": amount_str, "confidence": amount_conf},
            "interest_rate": {"value": roi_val, "confidence": roi_conf},
            "compounding": {"value": compounding_val, "confidence": compounding_conf},
            "tenure": {"value": tenure_val, "confidence": tenure_conf},
            "issue_date": {"value": issue_date_str, "confidence": issue_conf},
            "maturity_date": {"value": maturity_date_str, "confidence": maturity_conf},
            "institution_name": {"value": inst_name_val, "confidence": inst_name_conf},
            "institution_id": {"value": inst_id_val, "confidence": inst_id_conf},
            "lien_info": {"value": lien_val, "confidence": lien_conf},
            "raw_text": raw_text[:200],  # Masked snippet only
            "extraction_status": status,
            "status_detail": status_detail,
            "engine_available": effective_engine_available,
            "engine_status": self._tesseract_status if not effective_engine_available else "available",
            "classification": classification.to_dict(),
            "disclaimer": DISCLAIMER_TEXT,
        }

    def _build_empty_response(
        self,
        status: str,
        status_detail: str,
        engine_available: bool = True,
        classification: Optional[DocumentClassificationResult] = None,
    ) -> Dict[str, Any]:
        """Constructs an empty structured response with appropriate status, classification, and diagnostics."""
        if not classification:
            classification = classify_document(
                "",
                is_unreadable=(status == "unreadable"),
                ocr_unavailable=(status == "ocr_unavailable"),
                is_corrupt=(status in ("corrupt_or_unsupported", "processing_error")),
            )

        return {
            "fdr_number": {"value": None, "confidence": 0.0},
            "bank_name": {"value": None, "confidence": 0.0},
            "ifsc": {"value": None, "confidence": 0.0},
            "branch": {"value": None, "confidence": 0.0},
            "amount": {"value": None, "confidence": 0.0},
            "interest_rate": {"value": None, "confidence": 0.0},
            "compounding": {"value": None, "confidence": 0.0},
            "tenure": {"value": None, "confidence": 0.0},
            "issue_date": {"value": None, "confidence": 0.0},
            "maturity_date": {"value": None, "confidence": 0.0},
            "institution_name": {"value": None, "confidence": 0.0},
            "institution_id": {"value": None, "confidence": 0.0},
            "lien_info": {"value": None, "confidence": 0.0},
            "raw_text": "",
            "extraction_status": status,
            "status_detail": status_detail,
            "engine_available": engine_available,
            "engine_status": self._tesseract_status if not engine_available else "available",
            "classification": classification.to_dict(),
            "disclaimer": DISCLAIMER_TEXT,
        }


ocr_extractor = OCRExtractor()
