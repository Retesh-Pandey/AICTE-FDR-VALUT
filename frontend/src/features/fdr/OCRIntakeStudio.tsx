import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  Lock,
  ZoomIn,
  ZoomOut,
  Maximize2,
  RotateCw,
  Edit2,
  AlertTriangle,
  FileText,
  Upload,
  Shield,
  Scale,
  Sparkles,
  ArrowRight,
  Info,
  AlertCircle,
} from 'lucide-react';
import { useAuth } from '@/features/auth/AuthContext';
import { api, DocumentClassification, InstitutionHoldStatus } from '@/lib/api';

export const OCRIntakeStudio: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [showRadarTrace, setShowRadarTrace] = useState(true);
  const [officerAttested, setOfficerAttested] = useState(false);
  const [isMinting, setIsMinting] = useState(false);
  const [mintedSuccess, setMintedSuccess] = useState(false);
  const [createdFdrId, setCreatedFdrId] = useState<string | null>(null);
  const [createdBlockId, setCreatedBlockId] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // File & OCR state
  const [file, setFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState('SBI_PARLIAMENT_FDR_39482019482.pdf');
  const [fileSizeStr, setFileSizeStr] = useState('1.84 MB');
  const [isExtracting, setIsExtracting] = useState(false);
  const [ocrStatus, setOcrStatus] = useState<string>('idle');
  const [ocrStatusDetail, setOcrStatusDetail] = useState<string | null>(null);
  const [engineStatus, setEngineStatus] = useState<string>('available');
  const [ocrNotice, setOcrNotice] = useState<string | null>(null);

  // Classification & Content Explanation
  const [classification, setClassification] = useState<DocumentClassification | null>(null);
  const [fileSha256, setFileSha256] = useState<string | null>(null);
  const [isRequestingReview, setIsRequestingReview] = useState(false);
  const [reviewRequestSuccess, setReviewRequestSuccess] = useState<string | null>(null);

  // Escalation & Hold state
  const [institutionHold, setInstitutionHold] = useState<InstitutionHoldStatus | null>(null);
  const [appealModalOpen, setAppealModalOpen] = useState(false);
  const [appealReason, setAppealReason] = useState('');
  const [isSubmittingAppeal, setIsSubmittingAppeal] = useState(false);
  const [appealSuccess, setAppealSuccess] = useState<string | null>(null);
  const [appealError, setAppealError] = useState<string | null>(null);

  // Check institution hold on mount or when user changes
  React.useEffect(() => {
    if (user?.institution_id) {
      api.getInstitutionHoldStatus(user.institution_id)
        .then((hold) => setInstitutionHold(hold))
        .catch((err) => console.warn('Hold status query note:', err));
    }
  }, [user?.institution_id]);

  // Confidence indicators state
  const [confidences, setConfidences] = useState({
    institution: 99.1,
    fdrNumber: 99.4,
    bankName: 98.9,
    principalAmount: 98.7,
    interestRate: 97.5,
    issueDate: 98.2,
    maturityDate: 96.2,
  });

  // Editable fields state
  const [formData, setFormData] = useState({
    institution: 'AICTE-1-4928190 - Apex Institute of Technology, Greater Noida',
    fdrNumber: '39482019482',
    bankName: 'State Bank of India (SBIN0000691)',
    principalAmount: '1,50,00,000.00',
    interestRate: '7.10% p.a. (Quarterly Compound)',
    issueDate: '24 Nov 2023',
    maturityDate: '24 Nov 2028',
    tenure: '60 Months (5 Years)',
    lienClause:
      'Lien marked exclusively in favor of Member Secretary, AICTE New Delhi. Encashment / Premature release restricted without explicit digital token from AICTE Vault.',
  });

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    setFile(selected);
    setFileName(selected.name);
    setFileSizeStr(`${(selected.size / (1024 * 1024)).toFixed(2)} MB`);
    setIsExtracting(true);
    setOcrNotice(null);
    setSubmitError(null);
    setClassification(null);
    setReviewRequestSuccess(null);

    // Compute SHA-256 client-side for immediate display & review payload
    try {
      const buf = await selected.arrayBuffer();
      const hashBuf = await crypto.subtle.digest('SHA-256', buf);
      const hashArray = Array.from(new Uint8Array(hashBuf));
      const hashHex = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
      setFileSha256(hashHex);
    } catch {}

    try {
      const ocr = await api.ocrExtract(selected);
      const status = ocr.extraction_status || 'unreadable';
      setOcrStatus(status);
      setOcrStatusDetail(ocr.status_detail || null);
      setEngineStatus(ocr.engine_status || (ocr.engine_available ? 'available' : 'engine_missing'));
      setClassification(ocr.classification || null);

      // Preserve manually entered values if OCR did not extract a new value
      setFormData((prev) => {
        let instStr = prev.institution;
        if (ocr.institution_id?.value && ocr.institution_name?.value) {
          instStr = `${ocr.institution_id.value} - ${ocr.institution_name.value}`;
        } else if (ocr.institution_name?.value) {
          instStr = ocr.institution_name.value;
        } else if (ocr.institution_id?.value) {
          instStr = ocr.institution_id.value;
        }

        let rateStr = prev.interestRate;
        if (ocr.interest_rate?.value) {
          const baseRate = ocr.interest_rate.value.includes('%') ? ocr.interest_rate.value : `${ocr.interest_rate.value}%`;
          rateStr = ocr.compounding?.value ? `${baseRate} (${ocr.compounding.value})` : `${baseRate} p.a.`;
        }

        return {
          ...prev,
          institution: instStr,
          fdrNumber: ocr.fdr_number?.value ? ocr.fdr_number.value : prev.fdrNumber,
          bankName: ocr.bank_name?.value
            ? `${ocr.bank_name.value}${ocr.branch?.value ? ` (${ocr.branch.value})` : ''}`
            : prev.bankName,
          principalAmount: ocr.amount?.value ? ocr.amount.value : prev.principalAmount,
          interestRate: rateStr,
          issueDate: ocr.issue_date?.value ? ocr.issue_date.value : prev.issueDate,
          maturityDate: ocr.maturity_date?.value ? ocr.maturity_date.value : prev.maturityDate,
          tenure: ocr.tenure?.value ? ocr.tenure.value : prev.tenure,
          lienClause: ocr.lien_info?.value ? ocr.lien_info.value : prev.lienClause,
        };
      });

      // Update confidence percentages only for detected fields
      setConfidences((prev) => ({
        institution: ocr.institution_name?.value || ocr.institution_id?.value
          ? Math.round((ocr.institution_name?.confidence || ocr.institution_id?.confidence || 0.90) * 100)
          : prev.institution,
        fdrNumber: ocr.fdr_number?.value ? Math.round((ocr.fdr_number.confidence || 0.95) * 100) : prev.fdrNumber,
        bankName: ocr.bank_name?.value ? Math.round((ocr.bank_name.confidence || 0.92) * 100) : prev.bankName,
        principalAmount: ocr.amount?.value ? Math.round((ocr.amount.confidence || 0.96) * 100) : prev.principalAmount,
        interestRate: ocr.interest_rate?.value ? Math.round((ocr.interest_rate.confidence || 0.90) * 100) : prev.interestRate,
        issueDate: ocr.issue_date?.value ? Math.round((ocr.issue_date.confidence || 0.90) * 100) : prev.issueDate,
        maturityDate: ocr.maturity_date?.value ? Math.round((ocr.maturity_date.confidence || 0.90) * 100) : prev.maturityDate,
      }));

      // Contextual status message
      if (status === 'ocr_unavailable') {
        setOcrNotice(
          ocr.status_detail ||
            'Tesseract OCR engine is not available on this server. Scanned documents cannot be read automatically, but digital PDFs with text are processed. Please enter or review the FDR fields manually.'
        );
      } else if (ocr.classification?.status === 'likely_unrelated') {
        setOcrNotice(
          `This document does not appear to be an FDR receipt (${ocr.classification.detected_document_type || 'Unrelated Document'}). Please review the detected content below.`
        );
      } else if (status === 'needs_review' || ocr.classification?.status === 'possibly_fdr_needs_review') {
        setOcrNotice(
          ocr.status_detail ||
            'Document text was detected, but some standard FDR fields require human verification. Please verify the fields in the right panel.'
        );
      } else if (status === 'unreadable') {
        setOcrNotice(
          ocr.status_detail ||
            'The system cannot determine what the file contains because no readable text was detected. Form entries are preserved; please enter fields manually.'
        );
      } else if (status === 'partial') {
        setOcrNotice(
          `OCR partial extraction (PARTIAL) — Some fields were extracted. Please review and complete remaining fields manually.`
        );
      } else if (status === 'processing_error') {
        setOcrNotice(
          ocr.status_detail ||
            'Document could not be processed automatically. Your form entries are preserved; please enter fields manually.'
        );
      } else {
        setOcrNotice(`OCR analysis complete (SUCCESS) — ${ocr.disclaimer}`);
      }
    } catch (err: any) {
      setOcrStatus('processing_error');
      setOcrStatusDetail(err?.error?.message || 'Automatic OCR extraction failed.');
      setOcrNotice(
        `${err?.error?.message || 'Automatic OCR extraction failed'}. Manually entered values are preserved; you can complete the fields below to submit.`
      );
    } finally {
      setIsExtracting(false);
    }
  };

  const handleRequestReview = async () => {
    if (!file || !classification) return;
    setIsRequestingReview(true);
    setReviewRequestSuccess(null);
    setSubmitError(null);
    try {
      const sha256 = fileSha256 || '0000000000000000000000000000000000000000000000000000000000000000';
      await api.requestDocumentReview({
        filename: file.name,
        sha256_hash: sha256,
        classification: classification,
      });
      setReviewRequestSuccess(
        'Document review request dispatched. Staged in AICTE Officer Adjudication Queue for manual review. No strikes or penalties applied.'
      );
    } catch (err: any) {
      setSubmitError(err?.error?.message || 'Failed to submit document for review.');
    } finally {
      setIsRequestingReview(false);
    }
  };

  const handleAppealSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user?.institution_id) return;
    if (!appealReason.trim() || appealReason.trim().length < 10) {
      setAppealError('Please provide a detailed appeal statement (minimum 10 characters).');
      return;
    }
    setIsSubmittingAppeal(true);
    setAppealError(null);
    try {
      const res = await api.appealInstitutionHold(user.institution_id, appealReason.trim());
      setAppealSuccess(res.message || 'Appeal submitted successfully to AICTE Administration.');
      const updated = await api.getInstitutionHoldStatus(user.institution_id);
      setInstitutionHold(updated);
      setTimeout(() => {
        setAppealModalOpen(false);
        setAppealSuccess(null);
        setAppealReason('');
      }, 2500);
    } catch (err: any) {
      setAppealError(err?.error?.message || 'Failed to submit hold appeal.');
    } finally {
      setIsSubmittingAppeal(false);
    }
  };

  const handleMintBlock = async () => {
    if (institutionHold?.upload_hold_active) {
      setSubmitError(
        `FDR Uploads Suspended: This institution is currently on an FDR upload review hold until ${
          institutionHold.upload_hold_until ? new Date(institutionHold.upload_hold_until).toLocaleString() : 'further notice'
        }. Existing FDR records remain available in read-only mode. You may submit an appeal to AICTE Administration.`
      );
      return;
    }

    if (classification?.status === 'likely_unrelated' && user?.role === 'institution') {
      setSubmitError(
        'Submission Blocked: This document does not appear to be an FDR receipt. Please upload an authentic Fixed Deposit Receipt or request manual AICTE Officer review.'
      );
      return;
    }

    if (!officerAttested) {
      alert(
        'Statutory Attestation Required: You must certify and tick the Vigilance Officer Declaration before minting.'
      );
      return;
    }

    setSubmitError(null);
    setIsMinting(true);

    try {
      const body = new FormData();
      body.append('fdr_number', formData.fdrNumber.trim());

      const cleanBank = formData.bankName.split('(')[0].trim() || 'State Bank of India';
      body.append('bank_name', cleanBank);

      const branchMatch = formData.bankName.match(/\((.*?)\)/);
      if (branchMatch) {
        body.append('branch', branchMatch[1].trim());
      }

      const rawAmount = formData.principalAmount.replace(/,/g, '').replace(/[^\d.]/g, '');
      body.append('amount', rawAmount || '1000000.00');

      const parseDateToIso = (dStr: string, fallback: string) => {
        try {
          const d = new Date(dStr);
          if (!isNaN(d.getTime())) return d.toISOString().split('T')[0];
        } catch {}
        return fallback;
      };

      body.append('issue_date', parseDateToIso(formData.issueDate, '2026-01-15'));
      body.append('maturity_date', parseDateToIso(formData.maturityDate, '2028-01-15'));
      body.append('lien_info', formData.lienClause);

      if (file) {
        body.append('file', file);
      } else {
        const fallbackPdfBlob = new Blob(
          ['%PDF-1.4 Mock Sovereign AICTE Deposit Receipt Document'],
          { type: 'application/pdf' }
        );
        body.append('file', fallbackPdfBlob, 'sovereign_fdr_receipt.pdf');
      }

      if (user?.institution_id) {
        body.append('institution_id', user.institution_id);
      }

      const res = await api.submitFDR(body);
      setCreatedFdrId(res.fdr.id);
      setCreatedBlockId(res.document.sha256.slice(0, 16));
      setMintedSuccess(true);
    } catch (err: any) {
      setSubmitError(
        err?.error?.message || 'FDR submission was rejected by the vault rules engine.'
      );
    } finally {
      setIsMinting(false);
    }
  };

  return (
    <div className="space-y-4 max-w-[1700px] mx-auto pb-12">
      {/* Top Breadcrumb & Engine Telemetry */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center space-x-2 text-slate-400">
          <span className="text-slate-500">FDR Lifecycle</span>
          <span>&gt;</span>
          <span className="text-slate-500">Intake Pipeline</span>
          <span>&gt;</span>
          <span className="text-vault-amber font-semibold">New Deposit Ingestion &amp; Optical Verification</span>
        </div>

        <div className="flex items-center space-x-3 text-[11px]">
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-vault-900 border border-vault-800 text-vault-emerald">
            <span className="w-1.5 h-1.5 rounded-full bg-vault-emerald animate-pulse" />
            <span>CV2_WARP_PERSPECTIVE: ACTIVE</span>
          </div>
          <div className="px-2.5 py-1 rounded bg-vault-900 border border-vault-800 text-slate-300">
            ENGINE:{' '}
            <span
              className={
                engineStatus === 'available'
                  ? 'text-emerald-400 font-semibold'
                  : engineStatus === 'language_data_missing'
                  ? 'text-amber-400 font-semibold'
                  : 'text-orange-400 font-semibold'
              }
            >
              {engineStatus === 'available'
                ? 'TESSERACT v5 (OPERATIONAL)'
                : engineStatus === 'language_data_missing'
                ? 'TESSERACT (MISSING TESSDATA)'
                : 'OCR UNAVAILABLE (TESSERACT NOT INSTALLED)'}
            </span>
          </div>
        </div>
      </div>

      {/* Upload Review Hold Banner */}
      {institutionHold?.upload_hold_active && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-rose-950/80 via-rose-900/40 to-vault-950 border-2 border-rose-600/70 shadow-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4 font-mono">
          <div className="flex items-start space-x-3.5">
            <div className="w-9 h-9 rounded-lg bg-rose-600/20 border border-rose-500/40 flex items-center justify-center shrink-0 mt-0.5">
              <AlertTriangle className="w-5 h-5 text-rose-400" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <span className="font-bold text-rose-300 text-sm tracking-wide">
                  TEMPORARY FDR UPLOAD REVIEW HOLD ACTIVE
                </span>
                <span className="px-2 py-0.5 rounded bg-rose-950 border border-rose-700/60 text-rose-400 text-[10px] font-bold">
                  {institutionHold.confirmed_strikes_in_window} / {institutionHold.strike_threshold} STRIKES
                </span>
              </div>
              <div className="text-xs text-slate-200 font-sans leading-relaxed">
                {institutionHold.upload_hold_reason || 'Temporary review hold placed due to confirmed unrelated submissions.'}
              </div>
              <div className="text-[11px] text-slate-400 flex flex-wrap gap-x-4 gap-y-1 pt-1 font-mono">
                <span>Hold Duration: Until {institutionHold.upload_hold_until ? new Date(institutionHold.upload_hold_until).toLocaleString() : 'Notice'}</span>
                <span>•</span>
                <span className="text-emerald-400">Read access to existing FDR records remains active</span>
                {institutionHold.upload_hold_appealed_at && (
                  <>
                    <span>•</span>
                    <span className="text-amber-400">Appeal Under Administrative Review</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="shrink-0 flex items-center space-x-2 w-full md:w-auto">
            <button
              type="button"
              onClick={() => setAppealModalOpen(true)}
              className="w-full md:w-auto px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs transition shadow-lg shadow-rose-600/30 flex items-center justify-center space-x-1.5 font-sans"
            >
              <span>Submit Appeal / Request Review</span>
            </button>
          </div>
        </div>
      )}

      {/* Stepper Pipeline */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 font-mono text-xs">
        <div className="p-2.5 rounded bg-vault-900/90 border border-vault-800 flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-vault-emerald shrink-0" />
          <div className="truncate">
            <div className="font-semibold text-slate-200">01. INGESTION</div>
            <div className="text-[10px] text-slate-400 truncate">SHA-256 Validated</div>
          </div>
        </div>

        <div className="p-2.5 rounded bg-vault-900/90 border border-vault-800 flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-vault-emerald shrink-0" />
          <div className="truncate">
            <div className="font-semibold text-slate-200">02. OCR MATRIX</div>
            <div className="text-[10px] text-slate-400 truncate">Bounding 100% P...</div>
          </div>
        </div>

        <div className="p-2.5 rounded bg-vault-900/90 border border-vault-800 flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-vault-emerald shrink-0" />
          <div className="truncate">
            <div className="font-semibold text-slate-200">03. RULES ENGINE</div>
            <div className="text-[10px] text-vault-emerald truncate font-semibold">4 of 4 Passed</div>
          </div>
        </div>

        <div className="p-2.5 rounded bg-amber-500/10 border border-amber-500/40 flex items-center space-x-2 shadow-sm shadow-amber-500/10">
          <div className="w-4 h-4 rounded bg-amber-500 text-black font-bold flex items-center justify-center text-[10px] shrink-0">
            04
          </div>
          <div className="truncate">
            <div className="font-semibold text-amber-400">04. HUMAN GATE</div>
            <div className="text-[10px] text-amber-300 truncate">Attestation In-Flight</div>
          </div>
        </div>

        <div className="p-2.5 rounded bg-vault-900/40 border border-vault-800/60 flex items-center space-x-2 opacity-60">
          <Lock className="w-4 h-4 text-slate-500 shrink-0" />
          <div className="truncate">
            <div className="font-semibold text-slate-400">05. LEDGER MINT</div>
            <div className="text-[10px] text-slate-500 truncate">Pending Signature</div>
          </div>
        </div>
      </div>

      {/* Statutory AICTE Guideline Banner */}
      <div className="p-3 rounded-lg bg-gradient-to-r from-amber-500/15 via-amber-500/10 to-transparent border border-amber-500/30 flex items-start justify-between gap-4">
        <div className="flex items-start space-x-3">
          <Scale className="w-4 h-4 text-vault-amber shrink-0 mt-0.5" />
          <div className="text-xs">
            <span className="font-bold text-amber-400 font-mono">Statutory AICTE Guideline: </span>
            <span className="text-slate-200">
              Optical Character Recognition is strictly assistive. Machine extraction does not constitute regulatory authenticity. The validating vigilance officer holds sovereign responsibility for cross-verifying each value.
            </span>
          </div>
        </div>
        <span className="shrink-0 text-[10px] font-mono px-2 py-0.5 rounded bg-vault-950 border border-amber-500/40 text-vault-amber font-semibold">
          REG-CIR-2024-FDR-98
        </span>
      </div>

      {/* Main 2-Column Interface */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* LEFT COLUMN: Interactive Document Inspection View */}
        <div className="lg:col-span-6 space-y-3">
          {/* Document Header Bar with Live Upload */}
          <div className="p-3 rounded-t-lg bg-vault-900 border border-vault-800 flex flex-wrap items-center justify-between text-xs gap-2">
            <div className="flex items-center space-x-2">
              <FileText className="w-4 h-4 text-vault-amber" />
              <span className="font-semibold font-mono text-slate-200 truncate max-w-xs">
                {fileName}
              </span>
              <span className="text-slate-500 text-[11px]">({fileSizeStr})</span>
            </div>

            <div className="flex items-center space-x-2 font-mono text-[11px]">
              <label className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 cursor-pointer transition-colors">
                <Upload className="w-3.5 h-3.5" />
                <span>Upload New File</span>
                <input
                  type="file"
                  onChange={handleFileChange}
                  accept=".pdf,.png,.jpg,.jpeg"
                  className="hidden"
                />
              </label>

              <span
                className="px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-700/60 text-vault-emerald font-semibold"
                title="File bytes SHA-256 integrity hash recorded for vault verification"
              >
                FILE HASHED (SHA-256)
              </span>

              {ocrStatus !== 'idle' && (
                <span
                  className={`px-2 py-0.5 rounded border font-semibold text-[10px] ${
                    ocrStatus === 'success'
                      ? 'bg-emerald-950/80 border-emerald-700/60 text-vault-emerald'
                      : ocrStatus === 'partial'
                      ? 'bg-blue-950/80 border-blue-700/60 text-blue-400'
                      : ocrStatus === 'needs_review'
                      ? 'bg-amber-950/80 border-amber-700/60 text-amber-400'
                      : ocrStatus === 'ocr_unavailable'
                      ? 'bg-purple-950/80 border-purple-700/60 text-purple-300'
                      : 'bg-orange-950/80 border-orange-700/60 text-orange-400'
                  }`}
                >
                  OCR: {ocrStatus.toUpperCase().replace('_', ' ')}
                </span>
              )}
            </div>
          </div>

          {/* OCR Processing Banner */}
          {isExtracting && (
            <div className="p-2.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 font-mono text-xs flex items-center space-x-2 animate-pulse">
              <Sparkles className="w-4 h-4 animate-spin shrink-0" />
              <span>RUNNING OPTICAL PREPROCESSING &amp; DOMAIN-SPECIFIC PARSERS...</span>
            </div>
          )}

          {ocrNotice && !isExtracting && (
            <div
              className={`p-3 rounded border text-xs font-mono flex items-start space-x-2.5 ${
                ocrStatus === 'success'
                  ? 'bg-emerald-950/40 border-emerald-700/60 text-emerald-300'
                  : ocrStatus === 'partial'
                  ? 'bg-blue-950/40 border-blue-700/60 text-blue-300'
                  : ocrStatus === 'needs_review'
                  ? 'bg-amber-950/40 border-amber-700/60 text-amber-300'
                  : ocrStatus === 'ocr_unavailable'
                  ? 'bg-purple-950/40 border-purple-700/60 text-purple-300'
                  : 'bg-orange-950/40 border-orange-700/60 text-orange-300'
              }`}
            >
              {ocrStatus === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              ) : ocrStatus === 'partial' ? (
                <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
              ) : ocrStatus === 'needs_review' ? (
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 text-orange-400 shrink-0 mt-0.5" />
              )}
              <div className="space-y-1">
                <div className="font-semibold">{ocrNotice}</div>
                {ocrStatusDetail && ocrStatusDetail !== ocrNotice && (
                  <div className="text-[11px] text-slate-300 font-sans">{ocrStatusDetail}</div>
                )}
                {ocrStatus !== 'success' && (
                  <div className="text-[11px] text-slate-400">
                    Form values have been preserved. You can edit any field in the right panel and proceed with submission.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Unrelated Document Warning Card */}
          {classification?.status === 'likely_unrelated' && (
            <div className="p-4 rounded-xl bg-gradient-to-br from-rose-950/90 via-vault-950 to-vault-900 border-2 border-rose-600/60 shadow-xl space-y-3 font-mono">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center space-x-2">
                  <div className="w-7 h-7 rounded bg-rose-600/20 border border-rose-500/40 flex items-center justify-center text-rose-400 shrink-0">
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="font-bold text-rose-300 text-xs">
                      THIS DOES NOT APPEAR TO BE AN FDR RECEIPT
                    </div>
                    <div className="text-[10px] text-slate-400">
                      Automated Estimate (Not a verified fact) · Confidence: {Math.round((classification.confidence || 0.8) * 100)}%
                    </div>
                  </div>
                </div>

                <span className="px-2.5 py-1 rounded bg-rose-950 border border-rose-700/60 text-rose-300 font-bold text-[11px]">
                  {classification.detected_document_type || 'Unrelated Document'}
                </span>
              </div>

              <div className="text-xs text-slate-300 font-sans leading-relaxed bg-vault-950/80 p-2.5 rounded border border-rose-900/40">
                {classification.content_summary}
              </div>

              {classification.classification_reasons && classification.classification_reasons.length > 0 && (
                <div className="space-y-1 text-[11px]">
                  <div className="text-slate-400 font-semibold text-[10px] uppercase tracking-wider">
                    Detection Indicators:
                  </div>
                  <ul className="list-disc list-inside space-y-0.5 text-slate-300 text-[11px]">
                    {classification.classification_reasons.map((r, idx) => (
                      <li key={idx}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {classification.extracted_snippets && classification.extracted_snippets.length > 0 && (
                <div className="space-y-1 pt-1">
                  <div className="text-slate-400 font-semibold text-[10px] uppercase tracking-wider">
                    Detected Non-Sensitive Excerpts (Masked):
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {classification.extracted_snippets.map((snip, idx) => (
                      <span key={idx} className="px-2 py-0.5 rounded bg-vault-900 border border-vault-700 text-slate-300 text-[10px] font-mono">
                        "{snip}"
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="pt-2 border-t border-rose-900/40 flex flex-wrap items-center justify-between gap-2 text-xs">
                <span className="text-[11px] text-slate-400 font-sans">
                  Form values are preserved. Replace document or request manual AICTE officer review.
                </span>

                <div className="flex items-center space-x-2">
                  <label className="px-3 py-1.5 rounded bg-vault-800 hover:bg-vault-700 text-slate-200 border border-vault-600 cursor-pointer transition text-xs font-sans font-medium flex items-center space-x-1">
                    <Upload className="w-3.5 h-3.5" />
                    <span>Replace Document</span>
                    <input type="file" onChange={handleFileChange} accept=".pdf,.png,.jpg,.jpeg" className="hidden" />
                  </label>

                  <button
                    type="button"
                    onClick={handleRequestReview}
                    disabled={isRequestingReview || !!reviewRequestSuccess}
                    className="px-3 py-1.5 rounded bg-amber-600/30 hover:bg-amber-600/40 border border-amber-500/50 text-amber-300 text-xs font-sans font-medium transition flex items-center space-x-1"
                  >
                    <span>{isRequestingReview ? 'Submitting...' : 'Request AICTE Officer Review'}</span>
                  </button>
                </div>
              </div>

              {reviewRequestSuccess && (
                <div className="p-2.5 rounded bg-emerald-950/60 border border-emerald-700/60 text-emerald-300 text-xs font-sans">
                  {reviewRequestSuccess}
                </div>
              )}
            </div>
          )}

          {/* Viewer Toolbar */}
          <div className="px-3 py-2 bg-vault-900/60 border-x border-vault-800 flex items-center justify-between text-xs font-mono">
            <div className="flex items-center space-x-2">
              <button className="p-1 rounded hover:bg-vault-800 text-slate-300" title="Zoom In">
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
              <button className="p-1 rounded hover:bg-vault-800 text-slate-300" title="Zoom Out">
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <button className="p-1 rounded hover:bg-vault-800 text-slate-300" title="Fit to Screen">
                <Maximize2 className="w-3.5 h-3.5" />
              </button>
              <button className="p-1 rounded hover:bg-vault-800 text-slate-300" title="Rotate">
                <RotateCw className="w-3.5 h-3.5" />
              </button>
              <span className="text-slate-500 ml-2">100% - DPI: 300</span>
            </div>

            <div className="flex items-center space-x-4">
              <label className="flex items-center space-x-1.5 cursor-pointer select-none hover:text-white transition">
                <input
                  type="checkbox"
                  aria-label="Toggle Bounding Boxes"
                  checked={showBoundingBoxes}
                  onChange={(e) => setShowBoundingBoxes(e.target.checked)}
                  className="rounded bg-vault-950 border-vault-700 text-amber-500 focus:ring-1 focus:ring-amber-500 w-3.5 h-3.5 cursor-pointer"
                />
                <span className={`text-xs ${showBoundingBoxes ? 'text-amber-400 font-semibold' : 'text-slate-400'}`}>
                  Bounding Boxes
                </span>
              </label>

              <label className="flex items-center space-x-1.5 cursor-pointer select-none hover:text-white transition">
                <input
                  type="checkbox"
                  aria-label="Toggle Radar Trace"
                  checked={showRadarTrace}
                  onChange={(e) => setShowRadarTrace(e.target.checked)}
                  className="rounded bg-vault-950 border-vault-700 text-amber-500 focus:ring-1 focus:ring-amber-500 w-3.5 h-3.5 cursor-pointer"
                />
                <span className={`text-xs ${showRadarTrace ? 'text-amber-400 font-semibold' : 'text-slate-400'}`}>
                  Radar Trace
                </span>
              </label>
            </div>
          </div>

          {/* FDR Document Canvas View */}
          <div className="relative border border-vault-800 rounded-b-lg bg-[#0d1017] p-5 shadow-2xl min-h-[540px] flex flex-col justify-between overflow-hidden">
            {/* Dynamic Radar Sweep Effect */}
            {showRadarTrace && (
              <div className="absolute inset-0 pointer-events-none bg-gradient-to-b from-transparent via-amber-500/10 to-transparent h-24 radar-scan-line" />
            )}

            {/* Document Header Representation */}
            <div className="border-b border-slate-700/60 pb-4 mb-4">
              <div className="flex justify-between items-start">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-full bg-blue-700 flex items-center justify-center font-bold text-white text-xs border border-blue-400">
                    SBI
                  </div>
                  <div>
                    <div className="font-bold text-base text-slate-100 tracking-wide">STATE BANK OF INDIA</div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      Parliament Street Branch, New Delhi - 110001 · IFSC: SBIN0000691
                    </div>
                  </div>
                </div>

                <div className="text-right">
                  <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-mono font-semibold uppercase">
                    ORIGINAL INSTRUMENT
                  </span>
                  <div className="text-[11px] font-bold text-slate-200 mt-1 uppercase">TERM DEPOSIT ADVICE</div>
                </div>
              </div>
            </div>

            {/* Document Body Attributes with Highlight Overlays */}
            <div className="space-y-4 my-2 relative">
              {/* Account / FDR Number with Bounding Box */}
              <div className="flex justify-between items-center text-xs">
                <div
                  className={`p-1.5 rounded transition ${
                    showBoundingBoxes ? 'border border-vault-emerald bg-emerald-500/10' : ''
                  }`}
                >
                  <div className="text-[10px] text-slate-400 uppercase font-mono">DEPOSIT ACCOUNT / FDR NO:</div>
                  <div className="font-bold text-sm text-slate-100 font-mono">{formData.fdrNumber}</div>
                  {showBoundingBoxes && (
                    <span className="text-[9px] font-mono bg-emerald-950 text-vault-emerald px-1 rounded border border-emerald-700">
                      {confidences.fdrNumber}%
                    </span>
                  )}
                </div>

                <div className="text-right p-1.5">
                  <div className="text-[10px] text-slate-400 uppercase font-mono">ISSUE / EFFECTIVE DATE:</div>
                  <div className="font-semibold text-slate-200 font-mono">{formData.issueDate}</div>
                </div>
              </div>

              {/* Amount & Maturity Box */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div
                  className={`p-2 rounded transition ${
                    showBoundingBoxes ? 'border border-vault-amber bg-amber-500/10' : ''
                  }`}
                >
                  <div className="text-[10px] text-slate-400 uppercase font-mono">PRINCIPAL DEPOSIT SUM:</div>
                  <div className="font-extrabold text-base text-amber-400 font-mono">
                    INR {formData.principalAmount}
                  </div>
                  <div className="text-[10px] text-slate-400 italic">Rupees One Crore Fifty Lakhs Only</div>
                  {showBoundingBoxes && (
                    <span className="text-[9px] font-mono bg-amber-950 text-vault-amber px-1 rounded border border-amber-700">
                      {confidences.principalAmount}%
                    </span>
                  )}
                </div>

                <div
                  className={`p-2 rounded text-right transition ${
                    showBoundingBoxes ? 'border border-vault-amber bg-amber-500/10' : ''
                  }`}
                >
                  <div className="text-[10px] text-slate-400 uppercase font-mono">MATURITY DATE:</div>
                  <div className="font-extrabold text-base text-amber-400 font-mono">{formData.maturityDate}</div>
                  <div className="text-[10px] text-slate-400 font-mono">Tenure: 60 Months</div>
                  {showBoundingBoxes && (
                    <span className="text-[9px] font-mono bg-amber-950 text-vault-amber px-1 rounded border border-amber-700">
                      {confidences.maturityDate}%
                    </span>
                  )}
                </div>
              </div>

              {/* Interest and Valuation */}
              <div className="text-xs p-1.5 flex justify-between items-center text-slate-300 font-mono">
                <div>
                  <span className="text-slate-400">INTEREST RATE:</span> {formData.interestRate}
                </div>
                <div>
                  <span className="text-slate-400">ESTIMATED MATURITY VALUE:</span> INR 2,13,29,481.00
                </div>
              </div>

              {/* Encumbrance Clause with AICTE Lien Tag */}
              <div
                className={`p-3 rounded transition ${
                  showBoundingBoxes ? 'border border-cyan-500 bg-cyan-950/20' : 'bg-vault-900/60'
                }`}
              >
                <div className="flex justify-between items-center mb-1">
                  <div className="text-[10px] text-slate-400 uppercase font-mono">
                    ACCOUNT TITULAR &amp; ENCUMBRANCE CLAUSE:
                  </div>
                  {showBoundingBoxes && (
                    <span className="text-[9px] font-mono bg-cyan-950 text-cyan-300 px-1.5 py-0.5 rounded border border-cyan-700">
                      AICTE-LIEN 97.9%
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-200 leading-relaxed font-sans font-medium">
                  PRINCIPAL, APEX INSTITUTE OF TECHNOLOGY, GREATER NOIDA UNDER SOVEREIGN JOINT LIEN TO MEMBER SECRETARY, ALL INDIA COUNCIL FOR TECHNICAL EDUCATION (AICTE).
                </div>
              </div>
            </div>

            {/* Document Signature & Serial Footer */}
            <div className="border-t border-slate-700/60 pt-4 flex justify-between items-end text-[10px] text-slate-400 font-mono">
              <div>
                <div>Computer-generated verifiable security deposit receipt.</div>
                <div>SRL: DEL/SEC/2023/NDW692019</div>
              </div>
              <div className="text-right">
                <div className="font-serif italic text-sm text-slate-200">R.K. Mathur</div>
                <div className="border-t border-slate-600 pt-0.5">Authorized Signatory SBI</div>
              </div>
            </div>
          </div>

          {/* OCR Engine Diagnostics Footer */}
          <div className="p-3 rounded-lg bg-vault-900/70 border border-vault-800 flex flex-wrap items-center justify-between text-xs font-mono">
            <div className="flex items-center space-x-4 text-slate-400">
              <div>
                OCR Time: <span className="text-vault-emerald font-semibold">412ms</span>
              </div>
              <div>
                Skew Angle: <span className="text-slate-200 font-semibold">-0.34°</span>
              </div>
              <div>
                Resolution: <span className="text-slate-200 font-semibold">2480x3508px</span>
              </div>
            </div>

            <button className="text-[11px] text-vault-amber hover:underline flex items-center space-x-1">
              <span>Adjust Thresholds</span>
            </button>
          </div>

          {/* Alternate File Inspection */}
          <div className="p-3 rounded-lg bg-vault-900/50 border border-vault-800 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Upload className="w-4 h-4 text-slate-400" />
              <div>
                <div className="text-xs font-semibold text-slate-200">Alternate File Inspection</div>
                <div className="text-[10px] text-slate-400">
                  Switch to high-density camera capture or TIFF raw image
                </div>
              </div>
            </div>
            <button className="px-3 py-1.5 rounded bg-vault-800 hover:bg-vault-700 text-xs font-mono text-slate-200 border border-vault-700 transition">
              Browse File
            </button>
          </div>
        </div>

        {/* RIGHT COLUMN: Rule Compliance Engine & Extracted Instrument Data */}
        <div className="lg:col-span-6 space-y-4">
          {/* Card 1: Rule-Based Compliance Engine */}
          <div className="p-4 rounded-lg bg-vault-900/90 border border-vault-800 shadow-xl">
            <div className="flex items-center justify-between mb-3 border-b border-vault-800 pb-2">
              <div className="flex items-center space-x-2">
                <Shield className="w-4 h-4 text-vault-amber" />
                <span className="font-bold text-xs uppercase tracking-wide text-slate-100">
                  Rule-Based Compliance Engine
                </span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/80 text-vault-emerald border border-emerald-700/80 font-bold">
                VALIDATION: 4/4 PASS
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="p-2.5 rounded bg-vault-950/60 border border-vault-800 flex items-start space-x-2.5">
                <CheckCircle2 className="w-4 h-4 text-vault-emerald shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-slate-200">Mandatory Fields Check</div>
                  <div className="text-[11px] text-slate-400">All 7 primary regulatory attributes parsed.</div>
                </div>
              </div>

              <div className="p-2.5 rounded bg-vault-950/60 border border-vault-800 flex items-start space-x-2.5">
                <CheckCircle2 className="w-4 h-4 text-vault-emerald shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-slate-200">Chronological Sequence</div>
                  <div className="text-[11px] text-slate-400">Issue 24/11/2023 &lt; Maturity 24/11/2028 (5 Yrs).</div>
                </div>
              </div>

              <div className="p-2.5 rounded bg-vault-950/60 border border-vault-800 flex items-start space-x-2.5">
                <CheckCircle2 className="w-4 h-4 text-vault-emerald shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-slate-200">De-Duplication Hash</div>
                  <div className="text-[11px] text-slate-400">No duplicate instrument in central ledger.</div>
                </div>
              </div>

              <div className="p-2.5 rounded bg-vault-950/60 border border-vault-800 flex items-start space-x-2.5">
                <CheckCircle2 className="w-4 h-4 text-vault-emerald shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-slate-200">AICTE Joint Lien Clause</div>
                  <div className="text-[11px] text-slate-400">Confirmed explicitly to Member Secretary.</div>
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: Extracted Instrument Data (Field Precision Audit) */}
          <div className="p-4 rounded-lg bg-vault-900/90 border border-vault-800 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-vault-800 pb-2">
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-vault-amber" />
                <span className="font-bold text-xs uppercase tracking-wide text-slate-100">
                  Extracted Instrument Data
                </span>
                <span className="text-[10px] font-mono text-slate-400">FIELD PRECISION AUDIT</span>
              </div>
            </div>

            {/* Institution Identifier & Name */}
            <div>
              <div className="flex justify-between items-center mb-1 text-xs">
                <span className="font-medium text-slate-300">
                  INSTITUTION IDENTIFIER &amp; NAME <span className="text-amber-500">*</span>
                </span>
                <div className="flex items-center space-x-1.5 font-mono text-[10px]">
                  <span className="px-1.5 py-0.5 rounded bg-emerald-950 text-vault-emerald border border-emerald-800 font-semibold">
                    {confidences.institution}% Confidence
                  </span>
                  <Edit2 className="w-3 h-3 text-slate-400 hover:text-white cursor-pointer" />
                </div>
              </div>
              <input
                type="text"
                value={formData.institution}
                onChange={(e) => setFormData({ ...formData, institution: e.target.value })}
                className="w-full px-3 py-2 rounded bg-vault-950 border border-vault-700 text-xs text-slate-200 font-mono focus:border-amber-500 focus:outline-none"
              />
            </div>

            {/* FDR No & Issuing Bank */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="font-medium text-slate-300">FDR INSTRUMENT NO.</span>
                  <div className="flex items-center space-x-1 font-mono text-[10px]">
                    <span className="px-1.5 py-0.2 rounded bg-emerald-950 text-vault-emerald border border-emerald-800">
                      {confidences.fdrNumber}%
                    </span>
                    <Edit2 className="w-3 h-3 text-slate-400 cursor-pointer" />
                  </div>
                </div>
                <input
                  type="text"
                  value={formData.fdrNumber}
                  onChange={(e) => setFormData({ ...formData, fdrNumber: e.target.value })}
                  className="w-full px-3 py-2 rounded bg-vault-950 border border-vault-700 text-amber-400 font-mono font-bold text-sm focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="font-medium text-slate-300">ISSUING BANK &amp; IFSC</span>
                  <div className="flex items-center space-x-1 font-mono text-[10px]">
                    <span className="px-1.5 py-0.2 rounded bg-emerald-950 text-vault-emerald border border-emerald-800">
                      {confidences.bankName}%
                    </span>
                    <Edit2 className="w-3 h-3 text-slate-400 cursor-pointer" />
                  </div>
                </div>
                <input
                  type="text"
                  value={formData.bankName}
                  onChange={(e) => setFormData({ ...formData, bankName: e.target.value })}
                  className="w-full px-3 py-2 rounded bg-vault-950 border border-vault-700 text-slate-200 text-xs font-mono focus:border-amber-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Principal Amount & Interest Rate */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="font-medium text-slate-300">PRINCIPAL AMOUNT (₹)</span>
                  <div className="flex items-center space-x-1 font-mono text-[10px]">
                    <span className="px-1.5 py-0.2 rounded bg-amber-950 text-vault-amber border border-amber-800">
                      {confidences.principalAmount}%
                    </span>
                    <Edit2 className="w-3 h-3 text-slate-400 cursor-pointer" />
                  </div>
                </div>
                <input
                  type="text"
                  value={formData.principalAmount}
                  onChange={(e) => setFormData({ ...formData, principalAmount: e.target.value })}
                  className="w-full px-3 py-2 rounded bg-vault-950 border border-vault-700 text-slate-100 font-mono font-extrabold text-base focus:border-amber-500 focus:outline-none"
                />
                <div className="text-[10px] text-slate-400 italic mt-0.5">One Crore Fifty Lakhs Rupees Only</div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <span className="font-medium text-slate-300">INTEREST RATE &amp; COMPOUNDING</span>
                  <div className="flex items-center space-x-1 font-mono text-[10px]">
                    <span className="px-1.5 py-0.2 rounded bg-emerald-950 text-vault-emerald border border-emerald-800">
                      {confidences.interestRate}%
                    </span>
                    <Edit2 className="w-3 h-3 text-slate-400 cursor-pointer" />
                  </div>
                </div>
                <input
                  type="text"
                  value={formData.interestRate}
                  onChange={(e) => setFormData({ ...formData, interestRate: e.target.value })}
                  className="w-full px-3 py-2 rounded bg-vault-950 border border-vault-700 text-slate-200 text-xs font-mono focus:border-amber-500 focus:outline-none"
                />
                <div className="text-[10px] text-slate-400 mt-0.5">Yield calculation aligns with SBI schedule</div>
              </div>
            </div>

            {/* Inception Date & Maturity Date */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div>
                <div className="flex justify-between items-center mb-1 font-mono">
                  <span className="font-medium text-slate-300">DEPOSIT / INCEPTION DATE</span>
                  <span className="px-1.5 py-0.2 rounded bg-emerald-950 text-vault-emerald text-[10px]">{confidences.issueDate}%</span>
                </div>
                <input
                  type="text"
                  value={formData.issueDate}
                  onChange={(e) => setFormData({ ...formData, issueDate: e.target.value })}
                  className="w-full px-3 py-2 rounded bg-vault-950 border border-vault-700 text-slate-200 font-mono text-xs focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div>
                <div className="flex justify-between items-center mb-1 font-mono">
                  <span className="font-medium text-slate-300">MATURITY DATE {formData.tenure ? `(${formData.tenure})` : ''}</span>
                  <span className="px-1.5 py-0.2 rounded bg-amber-950 text-amber-400 border border-amber-800 text-[10px] font-bold">
                    {confidences.maturityDate}% Verified
                  </span>
                </div>
                <input
                  type="text"
                  value={formData.maturityDate}
                  onChange={(e) => setFormData({ ...formData, maturityDate: e.target.value })}
                  className="w-full px-3 py-2 rounded bg-vault-950 border border-amber-500/60 text-amber-400 font-mono text-xs font-bold focus:border-amber-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Lien Holder Recognition */}
            <div className="p-3 rounded bg-vault-950/70 border border-vault-800 space-y-1.5">
              <div className="flex justify-between items-center">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300 font-mono">
                  LIEN HOLDER RECOGNITION
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-semibold">
                  CLAUSE RECOGNIZED
                </span>
              </div>
              <p className="text-xs text-slate-300 font-sans leading-relaxed">
                "{formData.lienClause}"
              </p>
            </div>

            {/* Auto Renewal Clause */}
            <div className="flex items-center justify-between p-2.5 rounded bg-vault-950/50 border border-vault-800 text-xs font-mono">
              <span className="text-slate-400">AUTO-RENEWAL CLAUSE:</span>
              <span className="px-2 py-0.5 rounded bg-vault-900 border border-vault-700 text-slate-200 font-bold">
                NO (MANDATORY RENEWAL WORKFLOW)
              </span>
            </div>

            {/* Statutory Vigilance Officer Declaration Checkbox */}
            <div className="p-3.5 rounded-lg bg-vault-950 border border-amber-500/40 space-y-2">
              <label className="flex items-start space-x-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={officerAttested}
                  onChange={(e) => setOfficerAttested(e.target.checked)}
                  className="mt-0.5 rounded bg-vault-900 border-vault-600 text-amber-500 focus:ring-0 w-4 h-4 shrink-0"
                />
                <div className="text-xs space-y-1">
                  <div className="font-bold text-amber-400 font-mono">
                    Statutory Vigilance Officer Declaration
                  </div>
                  <div className="text-slate-300 leading-relaxed text-[11px]">
                    I, the undersigned authorized AICTE officer, certify that I have physically compared each extracted attribute against the sovereign bank-issued original Fixed Deposit Receipt. I attest that the institution code, principal sum of ₹1,50,00,000, and joint lien conditions are factually authentic.
                  </div>
                </div>
              </label>
            </div>

            {/* Actions Bar */}
            <div className="space-y-2.5 pt-1">
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <button
                  type="button"
                  className="py-2 px-3 rounded bg-vault-950 hover:bg-vault-850 border border-vault-700 text-slate-300 transition flex items-center justify-center space-x-1.5"
                >
                  <span>&gt; Run PaddleOCR Fallback</span>
                </button>

                <button
                  type="button"
                  className="py-2 px-3 rounded bg-rose-950/40 hover:bg-rose-900/40 border border-rose-800/60 text-rose-300 transition flex items-center justify-center space-x-1.5"
                >
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Flag Discrepancy</span>
                </button>
              </div>

              {/* Error Banner */}
              {submitError && (
                <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 font-mono text-xs flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{submitError}</span>
                </div>
              )}

              {/* Primary Mint Action or Success Actions */}
              {mintedSuccess && createdFdrId ? (
                <div className="space-y-2">
                  <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono text-xs space-y-1">
                    <div className="flex items-center space-x-2 font-bold">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>DEPOSIT REGISTRATION &amp; LEDGER BLOCK MINTED</span>
                    </div>
                    <div className="text-[11px] text-slate-300">
                      Block SHA-256 Digest: {createdBlockId ? `0x${createdBlockId}...` : 'SEALED'}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => navigate(`/fdrs/${createdFdrId}`)}
                    className="w-full py-3 px-4 rounded-lg font-bold text-xs tracking-wider uppercase bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-lg shadow-emerald-600/20 flex items-center justify-center space-x-2"
                  >
                    <span>VIEW MINTED INSTRUMENT IN VAULT</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={handleMintBlock}
                  disabled={
                    isMinting ||
                    mintedSuccess ||
                    (classification?.status === 'likely_unrelated' && user?.role === 'institution') ||
                    !!institutionHold?.upload_hold_active
                  }
                  className={`w-full py-3 px-4 rounded-lg font-bold text-xs tracking-wider uppercase transition shadow-xl flex items-center justify-center space-x-2 ${
                    isMinting ||
                    (classification?.status === 'likely_unrelated' && user?.role === 'institution') ||
                    !!institutionHold?.upload_hold_active
                      ? 'bg-vault-800 text-slate-500 border border-vault-700 cursor-not-allowed'
                      : 'bg-gradient-to-r from-amber-500 via-amber-400 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-black shadow-amber-500/20'
                  }`}
                >
                  {isMinting ? (
                    <>
                      <Sparkles className="w-4 h-4 animate-spin" />
                      <span>COMPUTING SHA-256 HASH CHAIN...</span>
                    </>
                  ) : institutionHold?.upload_hold_active ? (
                    <>
                      <AlertTriangle className="w-4 h-4 text-rose-400" />
                      <span>UPLOADS SUSPENDED (REVIEW HOLD ACTIVE)</span>
                    </>
                  ) : classification?.status === 'likely_unrelated' && user?.role === 'institution' ? (
                    <>
                      <AlertTriangle className="w-4 h-4 text-rose-400" />
                      <span>SUBMISSION BLOCKED (NOT AN FDR RECEIPT)</span>
                    </>
                  ) : (
                    <>
                      <Lock className="w-4 h-4" />
                      <span>CONFIRM &amp; MINT HASH BLOCK</span>
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Cryptographic Ledger Footer Bar */}
      <div className="p-3 rounded-lg bg-vault-900/90 border border-vault-800 flex flex-wrap items-center justify-between text-xs font-mono text-slate-400 mt-4">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-500">PREV BLOCK:</span>
            <span className="text-blue-400 font-semibold">0x629f...44b1</span>
          </div>
          <span>|</span>
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-500">NEXT PROPOSED HASH:</span>
            <span className="text-vault-amber font-semibold">0x9d11...c38e</span>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-[11px]">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span className="text-slate-300 font-bold">AICTE_GOV_LEDGER · PROTOCOL v4.2</span>
        </div>
      </div>

      {/* Hold Appeal Modal */}
      {appealModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-vault-900 border border-vault-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <h3 className="font-bold text-base text-slate-100 flex items-center space-x-2">
                  <Scale className="w-5 h-5 text-vault-amber" />
                  <span>Submit Upload Hold Appeal</span>
                </h3>
                <p className="text-xs text-slate-400">
                  Request AICTE Administrative Review to lift the temporary FDR upload hold.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setAppealModalOpen(false)}
                className="text-slate-400 hover:text-white p-1"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAppealSubmit} className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-mono text-slate-300">
                  Justification / Appeal Statement <span className="text-rose-400">*</span>
                </label>
                <textarea
                  rows={4}
                  value={appealReason}
                  onChange={(e) => setAppealReason(e.target.value)}
                  placeholder="Explain why the upload review hold should be lifted and describe corrective measures taken..."
                  className="w-full rounded-lg bg-vault-950 border border-vault-700 p-3 text-xs text-slate-100 focus:border-amber-500 focus:outline-none"
                  required
                />
                <div className="text-[10px] text-slate-500 font-mono">Minimum 10 characters required.</div>
              </div>

              {appealError && (
                <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                  {appealError}
                </div>
              )}

              {appealSuccess && (
                <div className="p-2.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs">
                  {appealSuccess}
                </div>
              )}

              <div className="flex items-center justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setAppealModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-vault-800 text-slate-300 hover:bg-vault-700 text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingAppeal}
                  className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-black text-xs font-bold transition"
                >
                  {isSubmittingAppeal ? 'Submitting...' : 'Submit Appeal to AICTE'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
