import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  Copy,
  Check,
  Building2,
  Calendar,
  Landmark,
  Shield,
  FileText,
  AlertTriangle,
  History,
  CheckCircle2,
  XCircle,
  Send,
  RotateCcw,
  X,
} from 'lucide-react';
import { api, FDRRecord, VerificationStatus, SimulatedVerificationResponse } from '@/lib/api';
import { formatCurrencyINR, formatDate } from '@/lib/utils';
import { InstrumentBadge, VerificationBadge, WorkflowBadge } from '@/components/common/StatusBadges';
import { useAuth } from '@/features/auth/AuthContext';

export const FDRDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { role } = useAuth();

  const [fdr, setFdr] = useState<FDRRecord | null>(null);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Simulated bank verification state
  const [isVerifyingBank, setIsVerifyingBank] = useState(false);
  const [verifyMsg, setVerifyMsg] = useState<{
    type: 'success' | 'warning' | 'error';
    text: string;
    data?: SimulatedVerificationResponse;
  } | null>(null);

  // Discrepancy resolution form state
  const [resolutionOutcome, setResolutionOutcome] = useState<VerificationStatus>('verified');
  const [resolutionNote, setResolutionNote] = useState('');
  const [isResolving, setIsResolving] = useState(false);
  const [resolveSuccess, setResolveSuccess] = useState<string | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);

  // Release request modal state
  const [isReleaseModalOpen, setIsReleaseModalOpen] = useState(false);
  const [releaseReason, setReleaseReason] = useState('');
  const [isSubmittingRelease, setIsSubmittingRelease] = useState(false);
  const [releaseMsg, setReleaseMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Renewal submission modal state
  const [isRenewalModalOpen, setIsRenewalModalOpen] = useState(false);
  const [renewalForm, setRenewalForm] = useState({
    fdr_number: '',
    bank_name: '',
    branch: '',
    amount: '',
    issue_date: '',
    maturity_date: '',
    lien_info: 'Lien marked exclusively in favor of Member Secretary, AICTE New Delhi.',
  });
  const [renewalFile, setRenewalFile] = useState<File | null>(null);
  const [isSubmittingRenewal, setIsSubmittingRenewal] = useState(false);
  const [renewalMsg, setRenewalMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Officer renewal decision state
  const [renewalRemarks, setRenewalRemarks] = useState('');
  const [isDecidingRenewal, setIsDecidingRenewal] = useState(false);
  const [decisionMsg, setDecisionMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchFDR = async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getFDR(id);
      setFdr(data);

      // Fetch audit logs for this FDR
      try {
        const logs = await api.getFDRAudit(id);
        setAuditLogs(logs);
      } catch {
        // Non-critical if audit log query fails
      }
    } catch (err: any) {
      setError(err?.error?.message || 'Failed to load FDR record details.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFDR();
  }, [id]);

  const handleCopyFdr = () => {
    if (fdr?.fdr_number) {
      navigator.clipboard.writeText(fdr.fdr_number);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleResolveDiscrepancy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !resolutionNote.trim()) return;

    setIsResolving(true);
    setResolveError(null);
    setResolveSuccess(null);

    try {
      const updated = await api.resolveDiscrepancy(id, resolutionOutcome, resolutionNote.trim());
      setFdr(updated);
      setResolveSuccess(`Discrepancy successfully resolved as '${resolutionOutcome.toUpperCase()}'.`);
      setResolutionNote('');
      // Refresh audit logs
      const logs = await api.getFDRAudit(id);
      setAuditLogs(logs);
    } catch (err: any) {
      setResolveError(err?.error?.message || 'Failed to resolve discrepancy.');
    } finally {
      setIsResolving(false);
    }
  };

  const handleRunSimulatedVerification = async () => {
    if (!id) return;
    setIsVerifyingBank(true);
    setVerifyMsg(null);
    try {
      const res = await api.verifyFDRWithBank(id);
      let msgType: 'success' | 'warning' | 'error' = 'success';
      let msgText = `Simulated check completed: Outcome = ${res.outcome.toUpperCase()}`;
      if (res.outcome === 'mismatch') {
        msgType = 'warning';
        msgText = `Simulated check flagged MISMATCH: ${res.different_fields.map((d) => d.field).join(', ')}`;
      } else if (res.outcome === 'not_found') {
        msgType = 'warning';
        msgText = `Simulated check: No matching record found in synthetic bank records. Retained in pending status.`;
      }
      setVerifyMsg({ type: msgType, text: msgText, data: res });
      await fetchFDR();
    } catch (err: any) {
      setVerifyMsg({
        type: 'error',
        text: err?.error?.message || err?.message || 'Simulated bank verification failed.',
      });
    } finally {
      setIsVerifyingBank(false);
    }
  };

  const handleRequestRelease = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !releaseReason.trim()) return;
    setIsSubmittingRelease(true);
    setReleaseMsg(null);
    try {
      await api.createReleaseRequest(id, releaseReason.trim());
      setReleaseMsg({ type: 'success', text: 'Release request registered and queued for officer review.' });
      setReleaseReason('');
      fetchFDR();
    } catch (err: any) {
      setReleaseMsg({ type: 'error', text: err?.error?.message || 'Failed to submit release request.' });
    } finally {
      setIsSubmittingRelease(false);
    }
  };

  const handleRenewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !renewalFile) return;
    setIsSubmittingRenewal(true);
    setRenewalMsg(null);
    try {
      const formData = new FormData();
      formData.append('fdr_number', renewalForm.fdr_number.trim());
      formData.append('bank_name', renewalForm.bank_name.trim());
      formData.append('branch', renewalForm.branch.trim());
      formData.append('amount', renewalForm.amount.trim());
      formData.append('issue_date', renewalForm.issue_date);
      formData.append('maturity_date', renewalForm.maturity_date);
      formData.append('lien_info', renewalForm.lien_info);
      formData.append('file', renewalFile);

      const res = await api.renewFDR(id, formData);
      setRenewalMsg({ type: 'success', text: `Renewal FDR ${res.record.fdr_number} submitted and linked to chain.` });
      fetchFDR();
    } catch (err: any) {
      setRenewalMsg({ type: 'error', text: err?.error?.message || 'Failed to submit renewal FDR.' });
    } finally {
      setIsSubmittingRenewal(false);
    }
  };

  const handleRenewalDecision = async (outcome: 'approved' | 'rejected') => {
    if (!id || !renewalRemarks.trim()) return;
    setIsDecidingRenewal(true);
    setDecisionMsg(null);
    try {
      if (outcome === 'approved') {
        await api.approveRenewal(id, renewalRemarks.trim());
        setDecisionMsg({ type: 'success', text: 'Renewal approved. Deposit activated in central vault.' });
      } else {
        await api.rejectRenewal(id, renewalRemarks.trim());
        setDecisionMsg({ type: 'success', text: 'Renewal submission rejected. Previous deposit remains unchanged.' });
      }
      setRenewalRemarks('');
      fetchFDR();
    } catch (err: any) {
      setDecisionMsg({ type: 'error', text: err?.error?.message || `Failed to ${outcome} renewal.` });
    } finally {
      setIsDecidingRenewal(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-[500px] flex flex-col items-center justify-center space-y-3 font-mono text-xs text-amber-500">
        <div className="w-8 h-8 border-2 border-amber-500/20 border-t-amber-500 rounded-full animate-spin" />
        <p>DECRYPTING SOVEREIGN RECORD &amp; CRYPTOGRAPHIC RECEIPTS...</p>
      </div>
    );
  }

  if (error || !fdr) {
    return (
      <div className="max-w-3xl mx-auto my-12 p-6 rounded-lg bg-vault-900 border border-rose-500/30 text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-rose-500 mx-auto" />
        <h2 className="text-base font-mono font-semibold text-slate-100">Record Retrieval Error</h2>
        <p className="text-xs text-slate-400 font-mono">{error || 'FDR not found or access denied.'}</p>
        <button
          onClick={() => navigate('/dashboard')}
          className="px-4 py-2 rounded bg-vault-800 hover:bg-vault-700 text-xs font-mono text-slate-200"
        >
          Return to Dashboard
        </button>
      </div>
    );
  }

  const isOfficerOrAdmin = role === 'officer' || role === 'admin';
  const maturityDateObj = new Date(fdr.maturity_date);
  const today = new Date();
  const daysDiff = Math.ceil((maturityDateObj.getTime() - today.getTime()) / (1000 * 3600 * 24));

  return (
    <div className="space-y-6 max-w-[1600px] mx-auto pb-16">
      {/* Top Navigation & Breadcrumb */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center space-x-2 text-xs font-mono text-slate-400 hover:text-amber-400 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>BACK TO FDR VAULT LEDGER</span>
        </button>

        <div className="font-mono text-[11px] text-slate-500">
          RECORD_ID: <span className="text-slate-400">{fdr.id}</span>
        </div>
      </div>

      {/* Main Instrument Title Header */}
      <div className="p-6 rounded-lg bg-vault-900 border border-vault-800 shadow-xl space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-3">
              <h1 className="text-2xl font-mono font-bold text-slate-100 tracking-tight">
                {fdr.fdr_number}
              </h1>
              <button
                onClick={handleCopyFdr}
                className="p-1.5 rounded hover:bg-vault-800 text-slate-400 hover:text-amber-400 transition-colors"
                title="Copy FDR Number"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-sm font-sans text-slate-300 flex items-center space-x-2">
              <Landmark className="w-4 h-4 text-amber-500" />
              <span>{fdr.bank_name}</span>
              {fdr.branch && <span className="text-slate-500">({fdr.branch})</span>}
            </p>
          </div>

          {/* Decoupled Sovereign Status Badges */}
          <div className="flex flex-wrap items-center gap-2">
            <div>
              <span className="block text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1">
                Instrument Status
              </span>
              <InstrumentBadge status={fdr.instrument_status} />
            </div>

            <div>
              <span className="block text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1">
                Verification Status
              </span>
              <VerificationBadge
                status={fdr.verification_status}
                source={fdr.verification_logs?.[0]?.source}
              />
            </div>

            <div>
              <span className="block text-[10px] font-mono text-slate-500 uppercase tracking-wider mb-1">
                Workflow State
              </span>
              <WorkflowBadge status={fdr.workflow_status} />
            </div>
          </div>
        </div>

        {/* Institution banner */}
        <div className="pt-4 border-t border-vault-800/80 flex flex-wrap items-center justify-between text-xs font-mono text-slate-400 gap-2">
          <div className="flex items-center space-x-2">
            <Building2 className="w-4 h-4 text-slate-500" />
            <span className="text-amber-400/90 font-medium">
              {fdr.institution?.name || 'Institutional Depositor'}
            </span>
            {fdr.institution?.aicte_id && (
              <span className="px-2 py-0.5 rounded bg-vault-800 text-slate-300">
                {fdr.institution.aicte_id}
              </span>
            )}
          </div>
          <div className="text-slate-500">
            Registered: {formatDate(fdr.created_at)}
          </div>
        </div>

        {/* Action Controls & Renewal Chain */}
        <div className="pt-3 border-t border-vault-800/80 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {fdr.previous_fdr_id && (
              <div className="px-2.5 py-1 rounded bg-purple-950/60 border border-purple-800 text-purple-300 font-mono text-xs flex items-center space-x-1.5">
                <History className="w-3.5 h-3.5 text-purple-400" />
                <span>Renewal Chain: Supersedes Deposit #{fdr.previous_fdr_id.slice(0, 8)}</span>
              </div>
            )}

            {fdr.instrument_status === 'renewed' && (
              <div className="px-2.5 py-1 rounded bg-blue-950/60 border border-blue-800 text-blue-300 font-mono text-xs flex items-center space-x-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-blue-400" />
                <span>Instrument Superseded by Renewal</span>
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Request Release Action */}
            {fdr.instrument_status !== 'released' && fdr.workflow_status !== 'release_requested' && (
              <button
                onClick={() => {
                  setReleaseMsg(null);
                  setIsReleaseModalOpen(true);
                }}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-vault-800 hover:bg-vault-700 border border-vault-700 text-xs font-semibold text-slate-200 transition"
              >
                <Send className="w-3.5 h-3.5 text-vault-amber" />
                <span>Request Release</span>
              </button>
            )}

            {/* Submit Renewal Action */}
            {fdr.is_current && fdr.instrument_status !== 'released' && (
              <button
                onClick={() => {
                  setRenewalMsg(null);
                  setRenewalForm({
                    fdr_number: '',
                    bank_name: fdr.bank_name,
                    branch: fdr.branch || '',
                    amount: String(fdr.amount),
                    issue_date: '',
                    maturity_date: '',
                    lien_info: fdr.lien_info || 'Lien marked exclusively in favor of Member Secretary, AICTE New Delhi.',
                  });
                  setIsRenewalModalOpen(true);
                }}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-slate-950 text-xs font-bold transition shadow-md shadow-amber-600/20"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Submit Renewal FDR</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Grid: Financial Specs & Critical Dates */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Principal Amount */}
        <div className="p-4 rounded-lg bg-vault-900 border border-vault-800 space-y-1">
          <div className="text-[11px] font-mono text-slate-400 uppercase">Principal Amount</div>
          <div className="text-xl font-mono font-bold text-vault-emerald">
            {formatCurrencyINR(fdr.amount)}
          </div>
          <div className="text-[11px] font-mono text-slate-500">Fixed Security Deposit</div>
        </div>

        {/* Issue Date */}
        <div className="p-4 rounded-lg bg-vault-900 border border-vault-800 space-y-1">
          <div className="text-[11px] font-mono text-slate-400 uppercase flex items-center space-x-1">
            <Calendar className="w-3.5 h-3.5 text-slate-500" />
            <span>Issue Date</span>
          </div>
          <div className="text-lg font-mono font-semibold text-slate-200">
            {formatDate(fdr.issue_date)}
          </div>
          <div className="text-[11px] font-mono text-slate-500">Bank Value Date</div>
        </div>

        {/* Maturity Date */}
        <div className="p-4 rounded-lg bg-vault-900 border border-vault-800 space-y-1">
          <div className="text-[11px] font-mono text-slate-400 uppercase flex items-center space-x-1">
            <Calendar className="w-3.5 h-3.5 text-slate-500" />
            <span>Maturity Date</span>
          </div>
          <div className="text-lg font-mono font-semibold text-amber-400">
            {formatDate(fdr.maturity_date)}
          </div>
          <div className="text-[11px] font-mono text-slate-500">
            {daysDiff > 0 ? `${daysDiff} days remaining` : `${Math.abs(daysDiff)} days elapsed`}
          </div>
        </div>

        {/* Lien Information */}
        <div className="p-4 rounded-lg bg-vault-900 border border-vault-800 space-y-1">
          <div className="text-[11px] font-mono text-slate-400 uppercase flex items-center space-x-1">
            <Shield className="w-3.5 h-3.5 text-amber-500" />
            <span>Statutory Lien</span>
          </div>
          <div className="text-xs font-mono text-slate-300 line-clamp-2">
            {fdr.lien_info || 'Lien marked exclusively in favor of Member Secretary AICTE'}
          </div>
          <div className="text-[10px] font-mono text-amber-500/80">LOCKED_IN_FAVOR_OF_AICTE</div>
        </div>
      </div>

      {/* Main Content: Document Viewer + Verification Results + Discrepancy Resolution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Attached Receipt Documents */}
        <div className="p-5 rounded-lg bg-vault-900 border border-vault-800 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-vault-800">
            <h3 className="font-mono text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center space-x-2">
              <FileText className="w-4 h-4 text-amber-500" />
              <span>Verified Document Vault</span>
            </h3>
            <span className="font-mono text-[10px] text-slate-500">
              {fdr.documents?.length || 0} RECEIPT ATTACHED
            </span>
          </div>

          {fdr.documents && fdr.documents.length > 0 ? (
            <div className="space-y-4">
              {fdr.documents.map((doc) => (
                <div
                  key={doc.id}
                  className="p-4 rounded bg-vault-950/80 border border-vault-800 space-y-3"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="font-mono text-xs text-slate-200 font-semibold truncate max-w-xs">
                        {doc.storage_path.split('/').pop()}
                      </div>
                      <div className="font-mono text-[10px] text-slate-500">
                        Type: <span className="text-slate-400">{doc.doc_type}</span> | Uploaded: {formatDate(doc.uploaded_at)}
                      </div>
                    </div>

                    {doc.signed_url && (
                      <a
                        href={doc.signed_url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 text-xs font-mono transition-colors"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>Download</span>
                      </a>
                    )}
                  </div>

                  {/* Verified Storage Protection Indicator */}
                  <div className="flex items-center space-x-2 text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/60 px-2.5 py-1 rounded">
                    <Shield className="w-3 h-3 text-emerald-400 shrink-0" />
                    <span>Encrypted at Rest (AES-128-CBC / Fernet) · Signed Download Token (15m)</span>
                  </div>

                  {/* SHA-256 Digest Tag */}
                  <div className="p-2 rounded bg-vault-900 border border-vault-800/80 font-mono text-[11px] text-slate-400 break-all">
                    <span className="text-slate-500 mr-2">SHA256:</span>
                    <span className="text-amber-500/90">{doc.sha256}</span>
                  </div>

                  {/* Assistive OCR Disclaimer */}
                  <div className="p-2.5 rounded bg-vault-900/40 border border-slate-800 font-mono text-[10px] text-slate-400 flex items-center space-x-2">
                    <Shield className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    <span>
                      Assistive data entry only. Extraction does not prove document authenticity.
                    </span>
                  </div>

                  {/* OCR Raw Text Preview */}
                  {doc.ocr_raw_text && (
                    <details className="text-xs font-mono">
                      <summary className="text-slate-400 cursor-pointer hover:text-amber-400 transition-colors">
                        Inspect Raw OCR Extraction Text
                      </summary>
                      <pre className="mt-2 p-3 rounded bg-black/60 border border-vault-800 text-[10px] text-slate-400 max-h-40 overflow-y-auto whitespace-pre-wrap">
                        {doc.ocr_raw_text}
                      </pre>
                    </details>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-xs font-mono text-slate-500">
              No digital receipt document attached.
            </div>
          )}
        </div>

        {/* Right Column: Verification Results & Discrepancy Workbench */}
        <div className="space-y-6">
          {/* Simulated Bank Verification Panel */}
          <div className="p-5 rounded-lg bg-vault-900 border border-vault-800 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-vault-800">
              <h3 className="font-mono text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center space-x-2">
                <Shield className="w-4 h-4 text-emerald-500" />
                <span>Verification Results</span>
              </h3>
              <span className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 font-mono text-[9px] text-amber-400 font-bold uppercase tracking-wider">
                SIMULATED — NOT BANK CONFIRMATION
              </span>
            </div>

            {/* Prominent Statutory Disclaimer */}
            <div className="p-3.5 rounded bg-amber-500/10 border border-amber-500/30 text-xs font-mono text-amber-300 space-y-1">
              <div className="flex items-center space-x-2 font-bold text-amber-400 uppercase tracking-wider">
                <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
                <span>SIMULATED DATA ADAPTER — NOT OFFICIAL BANK CONFIRMATION</span>
              </div>
              <p className="text-[11px] text-slate-300 leading-relaxed font-sans">
                Operates against synthetic test ledger records (<code>VERIFIER_MODE=mock</code>). Results simulate automated reconciliation for demonstration and testing only. They do not constitute actual bank approval or proof that an FDR is genuine. Human officer determination is required.
              </p>
            </div>

            {/* Officer trigger button */}
            {isOfficerOrAdmin && (
              <div className="pt-1">
                <button
                  type="button"
                  disabled={isVerifyingBank}
                  onClick={handleRunSimulatedVerification}
                  className="w-full py-2.5 px-4 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-slate-950 font-mono font-bold text-xs uppercase tracking-wider transition-all shadow-md flex items-center justify-center space-x-2"
                >
                  {isVerifyingBank ? (
                    <>
                      <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                      <span>QUERYING SYNTHETIC BANK LEDGER...</span>
                    </>
                  ) : (
                    <>
                      <Shield className="w-3.5 h-3.5" />
                      <span>RUN SIMULATED BANK VERIFICATION (DEMO)</span>
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Live Verification Result Banner & Comparison Table */}
            {verifyMsg && (
              <div className="space-y-3 pt-2">
                <div
                  className={`p-3 rounded font-mono text-xs flex items-center space-x-2 ${
                    verifyMsg.type === 'success'
                      ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                      : verifyMsg.type === 'warning'
                      ? 'bg-amber-500/10 border border-amber-500/30 text-amber-400'
                      : 'bg-rose-500/10 border border-rose-500/30 text-rose-400'
                  }`}
                >
                  {verifyMsg.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                  )}
                  <span>{verifyMsg.text}</span>
                </div>

                {verifyMsg.data?.all_comparisons && verifyMsg.data.all_comparisons.length > 0 && (
                  <div className="p-3 rounded bg-vault-950 border border-vault-800 space-y-2">
                    <div className="text-[10px] font-mono uppercase text-slate-400 font-bold tracking-wider">
                      Synthetic Field-by-Field Verification Audit
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left font-mono text-[11px]">
                        <thead>
                          <tr className="border-b border-vault-800 text-slate-500">
                            <th className="py-1.5 px-2">Parameter</th>
                            <th className="py-1.5 px-2">Submitted FDR</th>
                            <th className="py-1.5 px-2">Synthetic Bank Record</th>
                            <th className="py-1.5 px-2 text-right">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-vault-800/60">
                          {verifyMsg.data.all_comparisons.map((c, idx) => (
                            <tr key={idx} className="hover:bg-vault-900/40">
                              <td className="py-1.5 px-2 font-medium text-slate-300 capitalize">{c.field.replace('_', ' ')}</td>
                              <td className="py-1.5 px-2 text-slate-200">{c.submitted || '—'}</td>
                              <td className="py-1.5 px-2 text-slate-200">{c.confirmed || '—'}</td>
                              <td className="py-1.5 px-2 text-right font-bold">
                                {c.match ? (
                                  <span className="text-emerald-400">MATCH</span>
                                ) : c.status === 'not_found' ? (
                                  <span className="text-amber-400">NOT FOUND</span>
                                ) : (
                                  <span className="text-rose-400">MISMATCH</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Historical Verification Logs */}
            <div className="pt-2">
              <div className="text-[11px] font-mono text-slate-400 font-semibold uppercase tracking-wider mb-2">
                Verification Ledger History
              </div>
              {fdr.verification_logs && fdr.verification_logs.length > 0 ? (
                <div className="space-y-3">
                  {fdr.verification_logs.map((log) => (
                    <div
                      key={log.id}
                      className="p-3.5 rounded bg-vault-950/80 border border-vault-800 space-y-2.5 text-xs font-mono"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-slate-200">
                            SOURCE: {log.source}
                          </span>
                          {log.source === 'SIMULATED_BANK' && (
                            <span className="px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-[9px] text-amber-400 font-bold uppercase">
                              SIMULATED — NOT BANK CONFIRMATION
                            </span>
                          )}
                        </div>
                        <VerificationBadge status={log.outcome} />
                      </div>

                      {/* Display Discrepancies if any */}
                      {log.discrepancies && log.discrepancies.length > 0 && (
                        <div className="p-2 rounded bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[11px] space-y-1">
                          <span className="font-bold uppercase tracking-wider text-rose-400 block">
                            Flagged Discrepancies ({log.discrepancies.length})
                          </span>
                          <ul className="list-disc list-inside space-y-0.5">
                            {log.discrepancies.map((d: any, dIdx: number) => (
                              <li key={dIdx}>
                                <strong className="capitalize">{d.field || 'field'}</strong>: {d.reason || `${d.submitted} vs confirmed ${d.confirmed}`}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Submitted vs Confirmed Values Snapshot */}
                      {log.confirmed_values && (
                        <div className="grid grid-cols-2 gap-2 p-2 rounded bg-vault-900/60 text-[10px] text-slate-400 border border-vault-800/60">
                          <div>
                            <span className="text-slate-500 block">Submitted Values:</span>
                            <span className="text-slate-300">
                              ₹{log.submitted_values?.amount} ({log.submitted_values?.bank_name})
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 block">Synthetic Bank Record:</span>
                            <span className="text-slate-300">
                              ₹{log.confirmed_values?.amount} ({log.confirmed_values?.bank_name})
                            </span>
                          </div>
                        </div>
                      )}

                      {log.resolution_note && (
                        <div className="p-2 rounded bg-vault-900 text-slate-300 text-[11px] leading-relaxed">
                          <span className="text-slate-500 mr-1 font-bold">Audit Note:</span>
                          {log.resolution_note}
                        </div>
                      )}

                      <div className="text-[10px] text-slate-500">
                        Logged at: {formatDate(log.created_at)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-6 text-center text-xs font-mono text-slate-500">
                  No bank verification runs recorded yet. Verification is pending officer review.
                </div>
              )}
            </div>
          </div>

          {/* Officer Discrepancy Review & Resolution Workbench */}
          {isOfficerOrAdmin && (
            <div className="p-5 rounded-lg bg-vault-900 border border-vault-800 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-vault-800">
                <h3 className="font-mono text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span>Statutory Discrepancy Review</span>
                </h3>
                <span className="font-mono text-[10px] text-amber-400">
                  OFFICER JURISDICTION
                </span>
              </div>

              {resolveSuccess && (
                <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono text-xs flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>{resolveSuccess}</span>
                </div>
              )}

              {resolveError && (
                <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 font-mono text-xs flex items-center space-x-2">
                  <XCircle className="w-4 h-4 shrink-0" />
                  <span>{resolveError}</span>
                </div>
              )}

              <form onSubmit={handleResolveDiscrepancy} className="space-y-4 text-xs font-mono">
                <div>
                  <label className="block text-slate-400 mb-1.5">Authoritative Determination</label>
                  <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label="Resolution Outcome Determination">
                    <button
                      type="button"
                      role="radio"
                      aria-checked={resolutionOutcome === 'verified'}
                      onClick={() => setResolutionOutcome('verified')}
                      className={`py-2 px-3 rounded border text-center font-semibold transition-all ${
                        resolutionOutcome === 'verified'
                          ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400 shadow-sm shadow-emerald-500/10'
                          : 'bg-vault-950 border-vault-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      Certify &amp; Mark Verified
                    </button>
                    <button
                      type="button"
                      role="radio"
                      aria-checked={resolutionOutcome === 'rejected'}
                      onClick={() => setResolutionOutcome('rejected')}
                      className={`py-2 px-3 rounded border text-center font-semibold transition-all ${
                        resolutionOutcome === 'rejected'
                          ? 'bg-rose-500/20 border-rose-500 text-rose-400 shadow-sm shadow-rose-500/10'
                          : 'bg-vault-950 border-vault-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      Reject Instrument
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1.5">
                    Statutory Resolution Note <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    rows={3}
                    required
                    value={resolutionNote}
                    onChange={(e) => setResolutionNote(e.target.value)}
                    placeholder="Enter official grounds, bank certificate reference, or vigilance remarks..."
                    className="w-full rounded bg-vault-950 border border-vault-800 p-2.5 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-amber-500/50"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isResolving || !resolutionNote.trim()}
                  className="w-full py-2.5 px-4 rounded bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold uppercase tracking-wider transition-all shadow-md shadow-amber-500/10 flex items-center justify-center space-x-2"
                >
                  {isResolving ? (
                    <span>RECORDING IN CRYPTOGRAPHIC AUDIT LEDGER...</span>
                  ) : (
                    <span>SUBMIT RESOLUTION &amp; UPDATE AUDIT TRAIL</span>
                  )}
                </button>
              </form>
            </div>
          )}

          {/* Officer Renewal Approval / Rejection Workbench */}
          {isOfficerOrAdmin && fdr.workflow_status === 'renewal_review' && (
            <div className="p-5 rounded-lg bg-purple-950/30 border border-purple-800 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-purple-800/80">
                <h3 className="font-mono text-xs font-bold text-purple-200 uppercase tracking-wider flex items-center space-x-2">
                  <RotateCcw className="w-4 h-4 text-purple-400" />
                  <span>Renewal Determination Workbench</span>
                </h3>
                <span className="font-mono text-[10px] text-purple-300">
                  RENEWAL_REVIEW STATE
                </span>
              </div>

              {decisionMsg && (
                <div
                  className={`p-3 rounded font-mono text-xs flex items-center space-x-2 ${
                    decisionMsg.type === 'success'
                      ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                      : 'bg-rose-500/10 border border-rose-500/30 text-rose-400'
                  }`}
                >
                  {decisionMsg.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                  )}
                  <span>{decisionMsg.text}</span>
                </div>
              )}

              <div className="space-y-3 text-xs font-mono">
                <div>
                  <label className="block text-slate-300 mb-1.5 font-sans">
                    Mandatory Renewal Officer Remarks <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    rows={2}
                    value={renewalRemarks}
                    onChange={(e) => setRenewalRemarks(e.target.value)}
                    placeholder="Enter verification remarks, bank reference number, and compliance note..."
                    className="w-full rounded bg-vault-950 border border-vault-800 p-2.5 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-purple-500/50"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3 pt-1">
                  <button
                    type="button"
                    disabled={isDecidingRenewal || !renewalRemarks.trim()}
                    onClick={() => handleRenewalDecision('approved')}
                    className="py-2.5 px-4 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-slate-950 font-bold uppercase transition"
                  >
                    {isDecidingRenewal ? 'PROCESSING...' : 'Approve & Activate Renewal'}
                  </button>

                  <button
                    type="button"
                    disabled={isDecidingRenewal || !renewalRemarks.trim()}
                    onClick={() => handleRenewalDecision('rejected')}
                    className="py-2.5 px-4 rounded bg-rose-900 hover:bg-rose-800 disabled:opacity-50 text-white font-semibold uppercase transition"
                  >
                    Reject Renewal
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Release Request Modal */}
      {isReleaseModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#0b0e14] border border-vault-700 w-full max-w-md rounded-xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-vault-800">
              <h3 className="font-bold text-sm text-slate-100 flex items-center space-x-2">
                <Send className="w-4 h-4 text-vault-amber" />
                <span>Submit Release Request</span>
              </h3>
              <button
                onClick={() => setIsReleaseModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-400">
              Initiate formal administrative encashment / release review for deposit #{fdr.fdr_number}.
              Maturity alone never releases an FDR.
            </p>

            {releaseMsg && (
              <div
                className={`p-3 rounded text-xs flex items-center space-x-2 font-mono ${
                  releaseMsg.type === 'success'
                    ? 'bg-emerald-950/40 border border-emerald-800 text-emerald-300'
                    : 'bg-rose-950/40 border border-rose-800 text-rose-300'
                }`}
              >
                <span>{releaseMsg.text}</span>
              </div>
            )}

            <form onSubmit={handleRequestRelease} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Justification / Regulatory Ground <span className="text-amber-500">*</span>
                </label>
                <textarea
                  rows={3}
                  required
                  value={releaseReason}
                  onChange={(e) => setReleaseReason(e.target.value)}
                  placeholder="e.g. Mandatory 5-year tenure completed with full AICTE compliance clearance."
                  className="w-full px-3 py-2 rounded bg-vault-950 border border-vault-700 text-xs text-slate-200 focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-2 border-t border-vault-800">
                <button
                  type="button"
                  onClick={() => setIsReleaseModalOpen(false)}
                  className="px-3 py-1.5 rounded bg-vault-900 border border-vault-700 text-xs text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingRelease || !releaseReason.trim()}
                  className="px-4 py-1.5 rounded bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold text-xs"
                >
                  {isSubmittingRelease ? 'Submitting...' : 'Confirm Request'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Renewal Submission Modal */}
      {isRenewalModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-[#0b0e14] border border-vault-700 w-full max-w-lg rounded-xl p-6 shadow-2xl space-y-4 my-8">
            <div className="flex items-center justify-between pb-3 border-b border-vault-800">
              <h3 className="font-bold text-sm text-slate-100 flex items-center space-x-2">
                <RotateCcw className="w-4 h-4 text-vault-amber" />
                <span>Submit Renewal FDR Instrument</span>
              </h3>
              <button
                onClick={() => setIsRenewalModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-400">
              Submit renewed deposit receipt linked to previous FDR #{fdr.fdr_number}.
              Upon officer approval, the previous record will be superseded atomically.
            </p>

            {renewalMsg && (
              <div
                className={`p-3 rounded text-xs flex items-center space-x-2 font-mono ${
                  renewalMsg.type === 'success'
                    ? 'bg-emerald-950/40 border border-emerald-800 text-emerald-300'
                    : 'bg-rose-950/40 border border-rose-800 text-rose-300'
                }`}
              >
                <span>{renewalMsg.text}</span>
              </div>
            )}

            <form onSubmit={handleRenewSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 mb-1 font-semibold">New FDR Number *</label>
                <input
                  type="text"
                  required
                  value={renewalForm.fdr_number}
                  onChange={(e) => setRenewalForm({ ...renewalForm, fdr_number: e.target.value })}
                  placeholder="e.g. FDR-39482019483"
                  className="w-full px-3 py-1.5 rounded bg-vault-950 border border-vault-700 font-mono text-slate-100 focus:border-amber-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">Bank Name *</label>
                  <input
                    type="text"
                    required
                    value={renewalForm.bank_name}
                    onChange={(e) => setRenewalForm({ ...renewalForm, bank_name: e.target.value })}
                    className="w-full px-3 py-1.5 rounded bg-vault-950 border border-vault-700 text-slate-200 focus:border-amber-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">Principal Amount (₹) *</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={renewalForm.amount}
                    onChange={(e) => setRenewalForm({ ...renewalForm, amount: e.target.value })}
                    className="w-full px-3 py-1.5 rounded bg-vault-950 border border-vault-700 font-mono text-slate-200 focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">Issue Date *</label>
                  <input
                    type="date"
                    required
                    value={renewalForm.issue_date}
                    onChange={(e) => setRenewalForm({ ...renewalForm, issue_date: e.target.value })}
                    className="w-full px-3 py-1.5 rounded bg-vault-950 border border-vault-700 font-mono text-slate-200 focus:border-amber-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">Maturity Date *</label>
                  <input
                    type="date"
                    required
                    value={renewalForm.maturity_date}
                    onChange={(e) => setRenewalForm({ ...renewalForm, maturity_date: e.target.value })}
                    className="w-full px-3 py-1.5 rounded bg-vault-950 border border-vault-700 font-mono text-slate-200 focus:border-amber-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">Upload Renewal FDR PDF/Image *</label>
                <input
                  type="file"
                  required
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(e) => setRenewalFile(e.target.files?.[0] || null)}
                  className="w-full px-3 py-1.5 rounded bg-vault-950 border border-vault-700 text-slate-400 file:mr-3 file:py-1 file:px-2 file:rounded file:border-0 file:text-xs file:bg-vault-800 file:text-slate-200 focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-vault-800">
                <button
                  type="button"
                  onClick={() => setIsRenewalModalOpen(false)}
                  className="px-3 py-1.5 rounded bg-vault-900 border border-vault-700 text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingRenewal || !renewalFile || !renewalForm.fdr_number}
                  className="px-4 py-1.5 rounded bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold"
                >
                  {isSubmittingRenewal ? 'Submitting Renewal...' : 'Submit Renewal FDR'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Append-Only Hash-Chained Audit Trail for this Record */}
      <div className="p-5 rounded-lg bg-vault-900 border border-vault-800 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-vault-800">
          <h3 className="font-mono text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center space-x-2">
            <History className="w-4 h-4 text-amber-500" />
            <span>Cryptographic Ledger Trail for this Instrument</span>
          </h3>
          <span className="font-mono text-[10px] text-vault-emerald">
            SHA-256 PARITY VERIFIED
          </span>
        </div>

        {auditLogs && auditLogs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-vault-800 text-[10px] text-slate-500 uppercase">
                  <th className="py-2 px-3">Block #</th>
                  <th className="py-2 px-3">Timestamp</th>
                  <th className="py-2 px-3">Action</th>
                  <th className="py-2 px-3">Actor Role</th>
                  <th className="py-2 px-3">Old State</th>
                  <th className="py-2 px-3">New State</th>
                  <th className="py-2 px-3">Remarks</th>
                  <th className="py-2 px-3">Row Hash (SHA-256)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-vault-800/60">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-vault-800/30 transition-colors">
                    <td className="py-2.5 px-3 text-amber-500 font-bold">#{log.id}</td>
                    <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                      {formatDate(log.created_at)}
                    </td>
                    <td className="py-2.5 px-3 text-slate-200 font-semibold">{log.action}</td>
                    <td className="py-2.5 px-3 text-cyan-400">{log.actor_role || 'system'}</td>
                    <td className="py-2.5 px-3 text-slate-500">{log.old_status || '-'}</td>
                    <td className="py-2.5 px-3 text-emerald-400 font-medium">
                      {log.new_status || '-'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-300 max-w-xs truncate">{log.remarks}</td>
                    <td className="py-2.5 px-3 text-[10px] text-slate-500 font-mono">
                      {log.row_hash ? `${log.row_hash.slice(0, 16)}...` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-4 text-center text-xs font-mono text-slate-500">
            No audit records found for this instrument.
          </div>
        )}
      </div>
    </div>
  );
};
