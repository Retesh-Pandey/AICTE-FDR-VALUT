import React, { useEffect, useState, useMemo } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  FileText,
  Shield,
  Search,
  RefreshCw,
  ExternalLink,
  Building2,
  Building,
  Landmark,
  AlertCircle,
  Copy,
  Check,
  XCircle,
  Send,
  FileCheck2,
  FileX2,
  Scale,
  Ban,
  ShieldAlert,
} from 'lucide-react';
import {
  api,
  FDRRecord,
  VerificationStatus,
  SimulatedVerificationResponse,
  InstitutionRegistrationResponse,
  DocumentReviewItem,
  InstitutionHoldStatus,
} from '@/lib/api';
import { formatCurrencyINR, formatDate } from '@/lib/utils';
import {
  InstrumentBadge,
  VerificationBadge,
  WorkflowBadge,
} from '@/components/common/StatusBadges';
import { useAuth } from '@/features/auth/AuthContext';

export const OfficerVerificationPage: React.FC = () => {
  const { user } = useAuth();

  // FDR list state
  const [fdrs, setFdrs] = useState<FDRRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedFdr, setSelectedFdr] = useState<FDRRecord | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  // Filters & search
  const [filterTab, setFilterTab] = useState<'all' | 'pending' | 'discrepancy' | 'verified'>('pending');
  const [searchQuery, setSearchQuery] = useState('');

  // Simulated verification state
  const [isVerifyingBank, setIsVerifyingBank] = useState(false);
  const [simulatedResult, setSimulatedResult] = useState<SimulatedVerificationResponse | null>(null);
  const [simulatedError, setSimulatedError] = useState<string | null>(null);

  // Resolution state
  const [resolutionOutcome, setResolutionOutcome] = useState<VerificationStatus>('verified');
  const [resolutionNote, setResolutionNote] = useState('');
  const [isResolving, setIsResolving] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Copy feedback
  const [copied, setCopied] = useState(false);

  // Mode switcher: FDR Verification vs Institution Onboarding vs Document Review Queue vs Upload Holds
  const [activeWorkbenchTab, setActiveWorkbenchTab] = useState<'fdrs' | 'onboarding' | 'document_review' | 'upload_holds'>('fdrs');

  // Document Review Queue state
  const [reviewItems, setReviewItems] = useState<DocumentReviewItem[]>([]);
  const [isLoadingReview, setIsLoadingReview] = useState(false);
  const [reviewListError, setReviewListError] = useState<string | null>(null);
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [reviewFilter, setReviewFilter] = useState<'all' | 'pending' | 'confirmed_unrelated' | 'overridden_as_fdr' | 'dismissed'>('pending');
  const [reviewSearch, setReviewSearch] = useState('');
  const [adjudicationDecision, setAdjudicationDecision] = useState<'confirm_unrelated' | 'override_as_fdr' | 'dismiss'>('confirm_unrelated');
  const [adjudicationReason, setAdjudicationReason] = useState('');
  const [isAdjudicating, setIsAdjudicating] = useState(false);
  const [reviewSuccess, setReviewSuccess] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  // Institution Upload Holds & Appeals state (Admin)
  const [heldInstitutions, setHeldInstitutions] = useState<InstitutionHoldStatus[]>([]);
  const [isLoadingHeld, setIsLoadingHeld] = useState(false);
  const [heldListError, setHeldListError] = useState<string | null>(null);
  const [selectedHeldInstId, setSelectedHeldInstId] = useState<string | null>(null);
  const [unfreezeReason, setUnfreezeReason] = useState('');
  const [extendDays, setExtendDays] = useState(14);
  const [extendReason, setExtendReason] = useState('');
  const [isManagingHold, setIsManagingHold] = useState(false);
  const [holdActionSuccess, setHoldActionSuccess] = useState<string | null>(null);
  const [holdActionError, setHoldActionError] = useState<string | null>(null);

  // Institution Onboarding Adjudication state
  const [regRequests, setRegRequests] = useState<InstitutionRegistrationResponse[]>([]);
  const [isLoadingRegs, setIsLoadingRegs] = useState(false);
  const [regListError, setRegListError] = useState<string | null>(null);
  const [selectedRegId, setSelectedRegId] = useState<string | null>(null);
  const [regFilter, setRegFilter] = useState<'all' | 'pending_verification' | 'approved' | 'rejected' | 'duplicate'>('pending_verification');
  const [regSearch, setRegSearch] = useState('');
  const [regDecision, setRegDecision] = useState<'approved' | 'rejected' | 'duplicate'>('approved');
  const [regReason, setRegReason] = useState('');
  const [isSubmittingRegReview, setIsSubmittingRegReview] = useState(false);
  const [regActionSuccess, setRegActionSuccess] = useState<string | null>(null);
  const [regActionError, setRegActionError] = useState<string | null>(null);

  // Load FDR list
  const loadFDRList = async () => {
    setIsLoadingList(true);
    setListError(null);
    try {
      const res = await api.listFDRs({ limit: 50 });
      setFdrs(res.items || []);
      if (res.items && res.items.length > 0 && !selectedId) {
        // default select first pending or first item
        const firstPending = res.items.find(
          (f) => f.verification_status === 'pending' || f.verification_status === 'discrepancy'
        );
        setSelectedId(firstPending ? firstPending.id : res.items[0].id);
      }
    } catch (err: any) {
      setListError(err?.error?.message || 'Failed to load FDR verification queue.');
    } finally {
      setIsLoadingList(false);
    }
  };

  // Load Institution Onboarding requests
  const loadRegRequests = async () => {
    setIsLoadingRegs(true);
    setRegListError(null);
    try {
      const data = await api.listRegistrationRequests();
      setRegRequests(data || []);
      if (data && data.length > 0 && !selectedRegId) {
        const firstPending = data.find((r) => r.status === 'pending_verification') || data[0];
        setSelectedRegId(firstPending.id);
      }
    } catch (err: any) {
      setRegListError(err?.error?.message || 'Failed to load institution registration requests.');
    } finally {
      setIsLoadingRegs(false);
    }
  };

  // Load Document Review Queue
  const loadReviewQueue = async () => {
    setIsLoadingReview(true);
    setReviewListError(null);
    try {
      const items = await api.listReviewQueue(reviewFilter === 'all' ? undefined : reviewFilter);
      setReviewItems(items || []);
      if (items && items.length > 0 && !selectedReviewId) {
        const firstPending = items.find((i) => i.review_status === 'pending') || items[0];
        setSelectedReviewId(firstPending.id);
      }
    } catch (err: any) {
      setReviewListError(err?.error?.message || 'Failed to load document review queue.');
    } finally {
      setIsLoadingReview(false);
    }
  };

  // Load Held Institutions (Admin)
  const loadHeldInstitutions = async () => {
    if (user?.role !== 'admin') return;
    setIsLoadingHeld(true);
    setHeldListError(null);
    try {
      const held = await api.listHeldInstitutions();
      setHeldInstitutions(held || []);
      if (held && held.length > 0 && !selectedHeldInstId) {
        setSelectedHeldInstId(held[0].institution_id);
      }
    } catch (err: any) {
      setHeldListError(err?.error?.message || 'Failed to load held institutions list.');
    } finally {
      setIsLoadingHeld(false);
    }
  };

  useEffect(() => {
    loadFDRList();
    loadRegRequests();
    loadReviewQueue();
    if (user?.role === 'admin') {
      loadHeldInstitutions();
    }
  }, [user?.role]);

  // Document Review Adjudication Handler
  const handleAdjudicateReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReviewId) return;
    if (!adjudicationReason.trim() || adjudicationReason.trim().length < 5) {
      setReviewError('A detailed justification (minimum 5 characters) is required for document adjudication.');
      return;
    }

    setIsAdjudicating(true);
    setReviewError(null);
    setReviewSuccess(null);
    try {
      const updated = await api.adjudicateReview(selectedReviewId, adjudicationDecision, adjudicationReason.trim());
      setReviewItems((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setReviewSuccess(
        `Adjudication recorded: Document marked as ${adjudicationDecision.toUpperCase().replace('_', ' ')}. ${
          updated.is_strike ? 'Strike recorded toward temporary hold threshold.' : 'No strike assigned.'
        }`
      );
      setAdjudicationReason('');
      if (user?.role === 'admin') {
        loadHeldInstitutions();
      }
    } catch (err: any) {
      setReviewError(err?.error?.message || 'Failed to adjudicate document submission.');
    } finally {
      setIsAdjudicating(false);
    }
  };

  // Admin Unfreeze Handler
  const handleAdminUnfreeze = async (institutionId: string) => {
    if (!unfreezeReason.trim() || unfreezeReason.trim().length < 5) {
      setHoldActionError('A justification (minimum 5 characters) is required to remove an upload hold.');
      return;
    }
    setIsManagingHold(true);
    setHoldActionError(null);
    setHoldActionSuccess(null);
    try {
      const res = await api.adminUnfreezeHold(institutionId, unfreezeReason.trim());
      setHoldActionSuccess(res.message);
      setUnfreezeReason('');
      await loadHeldInstitutions();
    } catch (err: any) {
      setHoldActionError(err?.error?.message || 'Failed to unfreeze institution.');
    } finally {
      setIsManagingHold(false);
    }
  };

  // Admin Extend Hold Handler
  const handleAdminExtend = async (institutionId: string) => {
    if (!extendReason.trim() || extendReason.trim().length < 5) {
      setHoldActionError('A justification (minimum 5 characters) is required to extend an upload hold.');
      return;
    }
    setIsManagingHold(true);
    setHoldActionError(null);
    setHoldActionSuccess(null);
    try {
      const res = await api.adminExtendHold(institutionId, extendDays, extendReason.trim());
      setHoldActionSuccess(res.message);
      setExtendReason('');
      await loadHeldInstitutions();
    } catch (err: any) {
      setHoldActionError(err?.error?.message || 'Failed to extend upload hold.');
    } finally {
      setIsManagingHold(false);
    }
  };

  const handleAdjudicateRegRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRegId) return;
    if (!regReason.trim() || regReason.trim().length < 5) {
      setRegActionError('A statutory reason of at least 5 characters is mandatory for adjudicating onboarding requests.');
      return;
    }

    setIsSubmittingRegReview(true);
    setRegActionError(null);
    setRegActionSuccess(null);
    try {
      const updated = await api.reviewRegistrationRequest(selectedRegId, regDecision, regReason.trim());
      setRegRequests((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      setRegActionSuccess(
        `Decision applied successfully: Request ${updated.tracking_reference} for '${updated.institution_name}' is now ${updated.status.toUpperCase()}.`
      );
      setRegReason('');
    } catch (err: any) {
      setRegActionError(err?.error?.message || 'Failed to submit adjudication decision.');
    } finally {
      setIsSubmittingRegReview(false);
    }
  };

  // Load detail when selectedId changes
  useEffect(() => {
    if (!selectedId) {
      setSelectedFdr(null);
      setSimulatedResult(null);
      return;
    }
    let isMounted = true;
    setIsLoadingDetail(true);
    setActionSuccess(null);
    setActionError(null);
    setSimulatedResult(null);
    setSimulatedError(null);
    setResolutionNote('');

    api
      .getFDR(selectedId)
      .then((data) => {
        if (!isMounted) return;
        setSelectedFdr(data);
        // Pre-fill resolution outcome based on current status
        if (data.verification_status === 'discrepancy') {
          setResolutionOutcome('discrepancy');
        } else {
          setResolutionOutcome('verified');
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setActionError(err?.error?.message || 'Failed to fetch FDR details.');
      })
      .finally(() => {
        if (isMounted) setIsLoadingDetail(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedId]);

  // Filtered items
  const filteredFdrs = useMemo(() => {
    return fdrs.filter((item) => {
      // Tab filter
      if (filterTab === 'pending' && item.verification_status !== 'pending') return false;
      if (filterTab === 'discrepancy' && item.verification_status !== 'discrepancy') return false;
      if (filterTab === 'verified' && item.verification_status !== 'verified') return false;

      // Text query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const fdrNum = item.fdr_number?.toLowerCase() || '';
        const bankName = item.bank_name?.toLowerCase() || '';
        const instName = item.institution?.name?.toLowerCase() || '';
        const aicteId = item.institution?.aicte_id?.toLowerCase() || '';
        return (
          fdrNum.includes(q) ||
          bankName.includes(q) ||
          instName.includes(q) ||
          aicteId.includes(q)
        );
      }
      return true;
    });
  }, [fdrs, filterTab, searchQuery]);

  // Trigger Simulated Bank Verification
  const handleRunSimulatedCheck = async () => {
    if (!selectedId) return;
    setIsVerifyingBank(true);
    setSimulatedError(null);
    try {
      const res = await api.verifyFDRWithBank(selectedId);
      setSimulatedResult(res);
      // Refresh FDR detail to get updated verification logs
      const updated = await api.getFDR(selectedId);
      setSelectedFdr(updated);
      // Also update in list
      setFdrs((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
    } catch (err: any) {
      setSimulatedError(
        err?.error?.message || 'Simulated core-banking cross-verification failed.'
      );
    } finally {
      setIsVerifyingBank(false);
    }
  };

  // Resolve Discrepancy or Submit Officer Decision
  const handleResolveDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedId) return;
    if (!resolutionNote.trim() || resolutionNote.trim().length < 5) {
      setActionError('A detailed resolution note (at least 5 characters) is required.');
      return;
    }

    setIsResolving(true);
    setActionError(null);
    setActionSuccess(null);

    try {
      const updated = await api.resolveDiscrepancy(
        selectedId,
        resolutionOutcome,
        resolutionNote.trim()
      );
      setSelectedFdr(updated);
      setFdrs((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
      setActionSuccess(
        `Decision applied successfully: Status updated to ${resolutionOutcome.toUpperCase()} with audit ledger entry.`
      );
      setResolutionNote('');
    } catch (err: any) {
      setActionError(
        err?.error?.message || 'Failed to submit regulatory officer decision.'
      );
    } finally {
      setIsResolving(false);
    }
  };

  const handleCopyFdr = () => {
    if (selectedFdr?.fdr_number) {
      navigator.clipboard.writeText(selectedFdr.fdr_number);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const filteredRegRequests = useMemo(() => {
    return regRequests.filter((r) => {
      const matchesFilter =
        regFilter === 'all'
          ? true
          : r.status.toLowerCase() === regFilter.toLowerCase();
      const q = regSearch.toLowerCase().trim();
      const matchesSearch =
        !q ||
        r.institution_name.toLowerCase().includes(q) ||
        (r.aicte_id && r.aicte_id.toLowerCase().includes(q)) ||
        r.official_email.toLowerCase().includes(q) ||
        r.tracking_reference.toLowerCase().includes(q);
      return matchesFilter && matchesSearch;
    });
  }, [regRequests, regFilter, regSearch]);

  const selectedReg = useMemo(() => {
    return regRequests.find((r) => r.id === selectedRegId) || null;
  }, [regRequests, selectedRegId]);

  const filteredReviewItems = useMemo(() => {
    return reviewItems.filter((item) => {
      const matchesFilter =
        reviewFilter === 'all' ? true : item.review_status.toLowerCase() === reviewFilter.toLowerCase();
      const q = reviewSearch.toLowerCase().trim();
      const matchesSearch =
        !q ||
        item.filename.toLowerCase().includes(q) ||
        (item.institution_name && item.institution_name.toLowerCase().includes(q)) ||
        (item.detected_document_type && item.detected_document_type.toLowerCase().includes(q)) ||
        item.document_sha256.toLowerCase().includes(q);
      return matchesFilter && matchesSearch;
    });
  }, [reviewItems, reviewFilter, reviewSearch]);

  const selectedReviewItem = useMemo(() => {
    return reviewItems.find((item) => item.id === selectedReviewId) || null;
  }, [reviewItems, selectedReviewId]);

  const selectedHeldInst = useMemo(() => {
    return heldInstitutions.find((h) => h.institution_id === selectedHeldInstId) || null;
  }, [heldInstitutions, selectedHeldInstId]);

  return (
    <div className="space-y-4 max-w-[1700px] mx-auto pb-12">
      {/* Top Breadcrumb & Sovereign Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center space-x-2 text-slate-400">
          <span className="text-slate-500">AICTE Regulatory Directorate</span>
          <span>&gt;</span>
          <span className="text-slate-500">Vigilance &amp; Verification</span>
          <span>&gt;</span>
          <span className="text-vault-amber font-semibold">Regulatory Review &amp; Adjudication Workbench</span>
        </div>

        <div className="flex items-center space-x-3 text-[11px]">
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-vault-900 border border-vault-800 text-vault-emerald">
            <span className="w-1.5 h-1.5 rounded-full bg-vault-emerald animate-pulse" />
            <span>CORE_VERIFIER: SIMULATED ADAPTER ACTIVE</span>
          </div>
          <div className="px-2.5 py-1 rounded bg-vault-900 border border-vault-800 text-slate-300">
            OFFICER: <span className="text-amber-400 font-semibold">{user?.email || 'OFFICER'}</span>
          </div>
        </div>
      </div>

      {/* Workbench Switcher Navigation */}
      <div className="flex flex-wrap items-center gap-2 border-b border-vault-800 pb-3">
        <button
          type="button"
          onClick={() => setActiveWorkbenchTab('fdrs')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-mono transition ${
            activeWorkbenchTab === 'fdrs'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/50 font-bold shadow'
              : 'bg-vault-900 border border-vault-800 text-slate-400 hover:text-white'
          }`}
        >
          <FileCheck2 className="w-4 h-4 text-vault-amber" />
          <span>FDR Deposit Authenticity Queue</span>
          <span className="px-2 py-0.5 rounded-full bg-vault-950 text-[10px] font-bold text-amber-400 border border-amber-500/30">
            {fdrs.filter((f) => f.verification_status === 'pending' || f.verification_status === 'discrepancy').length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveWorkbenchTab('onboarding')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-mono transition ${
            activeWorkbenchTab === 'onboarding'
              ? 'bg-blue-500/20 text-blue-300 border border-blue-500/50 font-bold shadow'
              : 'bg-vault-900 border border-vault-800 text-slate-400 hover:text-white'
          }`}
        >
          <Building className="w-4 h-4 text-blue-400" />
          <span>Institution Onboarding Requests</span>
          <span className="px-2 py-0.5 rounded-full bg-blue-950 text-[10px] font-bold text-blue-300 border border-blue-800">
            {regRequests.filter((r) => r.status === 'pending_verification').length} pending
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveWorkbenchTab('document_review')}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-mono transition ${
            activeWorkbenchTab === 'document_review'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/50 font-bold shadow'
              : 'bg-vault-900 border border-vault-800 text-slate-400 hover:text-white'
          }`}
        >
          <FileX2 className="w-4 h-4 text-purple-400" />
          <span>Non-FDR &amp; Intake Review Queue</span>
          <span className="px-2 py-0.5 rounded-full bg-purple-950 text-[10px] font-bold text-purple-300 border border-purple-800">
            {reviewItems.filter((i) => i.review_status === 'pending').length} pending
          </span>
        </button>

        {user?.role === 'admin' && (
          <button
            type="button"
            onClick={() => setActiveWorkbenchTab('upload_holds')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-mono transition ${
              activeWorkbenchTab === 'upload_holds'
                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/50 font-bold shadow'
                : 'bg-vault-900 border border-vault-800 text-slate-400 hover:text-white'
            }`}
          >
            <Ban className="w-4 h-4 text-rose-400" />
            <span>Upload Holds &amp; Appeals</span>
            <span className="px-2 py-0.5 rounded-full bg-rose-950 text-[10px] font-bold text-rose-300 border border-rose-800">
              {heldInstitutions.length} held
            </span>
          </button>
        )}
      </div>

      {/* WORKBENCH 1: FDR DEPOSIT VERIFICATION */}
      {activeWorkbenchTab === 'fdrs' && (
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Column: Verification Queue */}
        <div className="lg:col-span-4 space-y-3">
          <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-4 shadow-xl">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <FileCheck2 className="w-4 h-4 text-vault-amber" />
                <h2 className="font-semibold text-sm text-slate-100">Verification Queue</h2>
              </div>
              <button
                onClick={loadFDRList}
                disabled={isLoadingList}
                className="text-slate-400 hover:text-slate-200 transition-colors p-1"
                title="Refresh Queue"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoadingList ? 'animate-spin' : ''}`} />
              </button>
            </div>

            {/* Filter Tabs */}
            <div className="grid grid-cols-4 gap-1 p-1 bg-vault-950 rounded-lg border border-vault-800 text-xs font-mono mb-3">
              <button
                onClick={() => setFilterTab('all')}
                className={`py-1.5 rounded text-center transition-all ${
                  filterTab === 'all'
                    ? 'bg-vault-800 text-slate-100 font-semibold shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                All ({fdrs.length})
              </button>
              <button
                onClick={() => setFilterTab('pending')}
                className={`py-1.5 rounded text-center transition-all ${
                  filterTab === 'pending'
                    ? 'bg-amber-950/80 text-amber-300 border border-amber-800/60 font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Pending
              </button>
              <button
                onClick={() => setFilterTab('discrepancy')}
                className={`py-1.5 rounded text-center transition-all ${
                  filterTab === 'discrepancy'
                    ? 'bg-rose-950/80 text-rose-300 border border-rose-800/60 font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Flagged
              </button>
              <button
                onClick={() => setFilterTab('verified')}
                className={`py-1.5 rounded text-center transition-all ${
                  filterTab === 'verified'
                    ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/60 font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Verified
              </button>
            </div>

            {/* Search Input */}
            <div className="relative mb-3">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search FDR, Bank, or Institution..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-vault-950 border border-vault-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/50"
              />
            </div>

            {/* Queue List */}
            {isLoadingList ? (
              <div className="py-12 text-center text-xs font-mono text-slate-500">
                <RefreshCw className="w-5 h-5 mx-auto mb-2 animate-spin text-amber-500" />
                LOADING REGULATORY QUEUE...
              </div>
            ) : listError ? (
              <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-400 text-xs">
                {listError}
              </div>
            ) : filteredFdrs.length === 0 ? (
              <div className="py-12 text-center text-xs font-mono text-slate-500">
                NO FDRs MATCH CURRENT FILTER
              </div>
            ) : (
              <div className="space-y-2 max-h-[calc(100vh-320px)] overflow-y-auto pr-1">
                {filteredFdrs.map((item) => {
                  const isSelected = item.id === selectedId;
                  return (
                    <button
                      key={item.id}
                      onClick={() => setSelectedId(item.id)}
                      className={`w-full text-left p-3 rounded-lg border transition-all ${
                        isSelected
                          ? 'bg-vault-800/90 border-amber-500/60 shadow-lg shadow-amber-500/5 ring-1 ring-amber-500/30'
                          : 'bg-vault-950/60 border-vault-800/80 hover:bg-vault-800/50 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-mono font-semibold text-xs text-slate-200">
                          {item.fdr_number}
                        </span>
                        <VerificationBadge status={item.verification_status} />
                      </div>
                      <div className="text-[11px] text-slate-400 truncate font-sans">
                        {item.institution?.name || 'Unknown Institution'}
                      </div>
                      <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-vault-800/60 text-[10px] font-mono text-slate-400">
                        <span className="text-amber-400 font-semibold">
                          {formatCurrencyINR(item.amount)}
                        </span>
                        <span>{item.bank_name.split('(')[0].trim()}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Inspection, Document Access, Simulated Verification & Resolution */}
        <div className="lg:col-span-8 space-y-4">
          {!selectedId ? (
            <div className="bg-vault-900/50 border border-vault-800 rounded-xl p-12 text-center font-mono text-xs text-slate-500">
              <Shield className="w-10 h-10 mx-auto mb-3 text-slate-600" />
              SELECT AN FDR RECORD FROM THE QUEUE TO COMMENCE REGULATORY AUDIT &amp; VERIFICATION
            </div>
          ) : isLoadingDetail ? (
            <div className="bg-vault-900/50 border border-vault-800 rounded-xl p-16 text-center font-mono text-xs text-slate-400">
              <RefreshCw className="w-6 h-6 mx-auto mb-3 animate-spin text-amber-500" />
              RETRIEVING ENCRYPTED FDR RECORD &amp; AUDIT TRAIL...
            </div>
          ) : !selectedFdr ? (
            <div className="bg-vault-900/50 border border-vault-800 rounded-xl p-12 text-center text-xs text-rose-400">
              FDR details could not be loaded.
            </div>
          ) : (
            <>
              {/* FDR Header Card */}
              <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-5 shadow-xl space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-lg font-bold text-slate-100 tracking-wide">
                        {selectedFdr.fdr_number}
                      </span>
                      <button
                        onClick={handleCopyFdr}
                        className="text-slate-400 hover:text-slate-200 transition-colors p-1"
                        title="Copy FDR Number"
                      >
                        {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>
                    <div className="flex items-center space-x-2 text-xs text-slate-400 mt-1">
                      <Building2 className="w-3.5 h-3.5 text-slate-500" />
                      <span className="font-medium text-slate-300">
                        {selectedFdr.institution?.name || 'Affiliated Institution'}
                      </span>
                      {selectedFdr.institution?.aicte_id && (
                        <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-vault-950 border border-vault-800 text-amber-400">
                          {selectedFdr.institution.aicte_id}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <VerificationBadge status={selectedFdr.verification_status} />
                    <InstrumentBadge status={selectedFdr.instrument_status} />
                    <WorkflowBadge status={selectedFdr.workflow_status} />
                  </div>
                </div>

                {/* Grid of Key Instrument Data */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-vault-800/80 font-mono text-xs">
                  <div className="p-3 bg-vault-950/80 rounded-lg border border-vault-800/80">
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">
                      Principal Amount
                    </div>
                    <div className="text-sm font-bold text-amber-400">
                      {formatCurrencyINR(selectedFdr.amount)}
                    </div>
                  </div>

                  <div className="p-3 bg-vault-950/80 rounded-lg border border-vault-800/80">
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">
                      Banking Institution
                    </div>
                    <div className="text-xs font-semibold text-slate-200 truncate" title={selectedFdr.bank_name}>
                      {selectedFdr.bank_name}
                    </div>
                    {selectedFdr.branch && (
                      <div className="text-[10px] text-slate-400 truncate">Br: {selectedFdr.branch}</div>
                    )}
                  </div>

                  <div className="p-3 bg-vault-950/80 rounded-lg border border-vault-800/80">
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">
                      Issue &amp; Maturity
                    </div>
                    <div className="text-[11px] text-slate-300">
                      Iss: {formatDate(selectedFdr.issue_date)}
                    </div>
                    <div className="text-[11px] text-amber-400 font-semibold">
                      Mat: {formatDate(selectedFdr.maturity_date)}
                    </div>
                  </div>

                  <div className="p-3 bg-vault-950/80 rounded-lg border border-vault-800/80">
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">
                      Lien Exclusivity
                    </div>
                    <div className="text-[11px] text-slate-300 line-clamp-2" title={selectedFdr.lien_info || 'AICTE Lien Marked'}>
                      {selectedFdr.lien_info || 'In favor of Member Secretary, AICTE'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Document Access Section */}
              <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-5 shadow-xl space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-vault-amber" />
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200 font-mono">
                      Associated Document &amp; Cryptographic Evidence
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">
                    {selectedFdr.documents?.length || 0} FILE(S) ATTACHED
                  </span>
                </div>

                {selectedFdr.documents && selectedFdr.documents.length > 0 ? (
                  <div className="space-y-2">
                    {selectedFdr.documents.map((doc) => (
                      <div
                        key={doc.id}
                        className="p-3 rounded-lg bg-vault-950 border border-vault-800/80 flex flex-wrap items-center justify-between gap-3 font-mono text-xs"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center space-x-2">
                            <span className="px-1.5 py-0.5 rounded bg-vault-900 text-slate-300 text-[10px] uppercase font-semibold border border-vault-800">
                              {doc.doc_type}
                            </span>
                            <span className="text-slate-300 font-sans text-xs">
                              {doc.storage_path.split('/').pop()}
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-500 flex items-center space-x-2">
                            <span>SHA-256:</span>
                            <span className="text-emerald-400 font-mono">
                              {doc.sha256}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center space-x-2">
                          <a
                            href={doc.signed_url || `/api/v1/fdrs/documents/${doc.id}/download`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-vault-800 hover:bg-vault-700 text-slate-200 text-xs font-sans font-medium transition-colors border border-vault-700"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            <span>Inspect Document</span>
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 bg-vault-950/60 rounded-lg border border-vault-800 text-center text-xs font-mono text-slate-500">
                    NO DIGITAL ATTACHMENT PRESENT
                  </div>
                )}
              </div>

              {/* Simulated Bank Verification Section */}
              <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-5 shadow-xl space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center space-x-2">
                    <Landmark className="w-4 h-4 text-amber-400" />
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200 font-mono">
                        Core-Banking Cross-Verification Check
                      </h3>
                      <div className="text-[11px] text-slate-400 font-sans">
                        Independent cross-referencing against banking core ledger records
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={handleRunSimulatedCheck}
                    disabled={isVerifyingBank}
                    className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-vault-950 font-semibold text-xs shadow-lg shadow-amber-500/10 transition-all disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isVerifyingBank ? 'animate-spin' : ''}`} />
                    <span>{isVerifyingBank ? 'Checking Mock Ledger...' : 'Run Simulated Core-Banking Check'}</span>
                  </button>
                </div>

                {/* Mandatory Disclaimer Badge */}
                <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-800/50 flex items-start space-x-2.5 text-xs text-amber-300">
                  <AlertCircle className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
                  <div>
                    <span className="font-bold tracking-wide font-mono mr-1">
                      SIMULATED — NOT BANK CONFIRMATION:
                    </span>
                    <span className="text-amber-200/90">
                      Cross-checks are executed against synthetic regulatory sandbox records. This simulated response does not constitute real commercial bank verification or guarantee document authenticity.
                    </span>
                  </div>
                </div>

                {simulatedError && (
                  <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-400 text-xs">
                    {simulatedError}
                  </div>
                )}

                {/* Simulated Verification Result Diff Table */}
                {(simulatedResult || (selectedFdr.verification_logs && selectedFdr.verification_logs.length > 0)) && (
                  <div className="space-y-3 pt-2">
                    {(() => {
                      const latestLog = selectedFdr.verification_logs?.[0];
                      const outcome = simulatedResult?.outcome || latestLog?.outcome || 'pending';

                      return (
                        <div className="border border-vault-800 rounded-lg overflow-hidden bg-vault-950">
                          <div className="p-3 bg-vault-900 border-b border-vault-800 flex items-center justify-between text-xs font-mono">
                            <span className="text-slate-300">
                              VERIFICATION OUTCOME:{' '}
                              <span
                                className={`font-bold uppercase ${
                                  outcome === 'match' || outcome === 'verified'
                                    ? 'text-emerald-400'
                                    : outcome === 'mismatch' || outcome === 'discrepancy'
                                    ? 'text-rose-400'
                                    : 'text-amber-400'
                                }`}
                              >
                                {outcome}
                              </span>
                            </span>
                            <span className="text-[10px] text-slate-500">
                              SOURCE: SIMULATED_BANK_ADAPTER
                            </span>
                          </div>

                          <div className="overflow-x-auto">
                            {simulatedResult?.all_comparisons && simulatedResult.all_comparisons.length > 0 ? (
                              <table className="w-full text-xs text-left">
                                <thead className="bg-vault-900/60 font-mono text-[10px] text-slate-400 border-b border-vault-800">
                                  <tr>
                                    <th className="p-2.5">FIELD SPECIFIER</th>
                                    <th className="p-2.5">SUBMITTED VALUE</th>
                                    <th className="p-2.5">CONFIRMED (SIMULATED RECORD)</th>
                                    <th className="p-2.5 text-right">DISCREPANCY STATUS</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-vault-800/60 font-mono text-xs">
                                  {simulatedResult.all_comparisons.map((c, idx) => (
                                    <tr key={idx}>
                                      <td className="p-2.5 text-slate-400 font-sans capitalize">{c.field.replace('_', ' ')}</td>
                                      <td className="p-2.5 text-slate-200">{c.submitted || '—'}</td>
                                      <td className="p-2.5 text-slate-200">{c.confirmed || '—'}</td>
                                      <td className="p-2.5 text-right">
                                        {c.match ? (
                                          <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px] font-bold">
                                            MATCH
                                          </span>
                                        ) : c.status === 'not_found' ? (
                                          <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800 text-[10px] font-bold">
                                            NOT FOUND
                                          </span>
                                        ) : (
                                          <span className="px-2 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-800 text-[10px] font-bold">
                                            MISMATCH
                                          </span>
                                        )}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            ) : (
                              <table className="w-full text-xs text-left">
                                <thead className="bg-vault-900/60 font-mono text-[10px] text-slate-400 border-b border-vault-800">
                                  <tr>
                                    <th className="p-2.5">FIELD SPECIFIER</th>
                                    <th className="p-2.5">SUBMITTED VALUE</th>
                                    <th className="p-2.5">CONFIRMED (SIMULATED RECORD)</th>
                                    <th className="p-2.5 text-right">DISCREPANCY STATUS</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-vault-800/60 font-mono text-xs">
                                  <tr>
                                    <td className="p-2.5 text-slate-400 font-sans">FDR Number</td>
                                    <td className="p-2.5 text-slate-200">{latestLog?.submitted_values?.fdr_number || selectedFdr.fdr_number}</td>
                                    <td className="p-2.5 text-slate-200">{latestLog?.confirmed_values?.fdr_number || '—'}</td>
                                    <td className="p-2.5 text-right">
                                      {latestLog?.discrepancies?.some((d: any) => d.field === 'fdr_number') ? (
                                        <span className="px-2 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-800 text-[10px]">
                                          MISMATCH
                                        </span>
                                      ) : (
                                        <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px]">
                                          MATCH
                                        </span>
                                      )}
                                    </td>
                                  </tr>
                                  <tr>
                                    <td className="p-2.5 text-slate-400 font-sans">Principal Amount</td>
                                    <td className="p-2.5 text-slate-200">{latestLog?.submitted_values?.amount ? formatCurrencyINR(latestLog.submitted_values.amount) : formatCurrencyINR(selectedFdr.amount)}</td>
                                    <td className="p-2.5 text-slate-200">{latestLog?.confirmed_values?.amount ? formatCurrencyINR(latestLog.confirmed_values.amount) : '—'}</td>
                                    <td className="p-2.5 text-right">
                                      {latestLog?.discrepancies?.some((d: any) => d.field === 'amount') ? (
                                        <span className="px-2 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-800 text-[10px]">
                                          MISMATCH
                                        </span>
                                      ) : (
                                        <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px]">
                                          MATCH
                                        </span>
                                      )}
                                    </td>
                                  </tr>
                                </tbody>
                              </table>
                            )}
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                )}
              </div>

              {/* Officer Decision & Discrepancy Resolution Panel */}
              <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-5 shadow-xl space-y-4">
                <div className="flex items-center space-x-2">
                  <Shield className="w-4 h-4 text-vault-amber" />
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200 font-mono">
                    Officer Resolution &amp; Statutory Attestation
                  </h3>
                </div>

                {actionSuccess && (
                  <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800/60 text-emerald-400 text-xs">
                    {actionSuccess}
                  </div>
                )}
                {actionError && (
                  <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-400 text-xs">
                    {actionError}
                  </div>
                )}

                <form onSubmit={handleResolveDecision} className="space-y-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-2 font-mono">
                      DECISION / OUTCOME ACTION:
                    </label>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <button
                        type="button"
                        onClick={() => setResolutionOutcome('verified')}
                        className={`p-3 rounded-lg border text-left transition-all font-mono text-xs ${
                          resolutionOutcome === 'verified'
                            ? 'bg-emerald-950/80 border-emerald-500 text-emerald-300 ring-1 ring-emerald-500/30'
                            : 'bg-vault-950 border-vault-800 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <div className="font-bold flex items-center space-x-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          <span>MARK VERIFIED</span>
                        </div>
                        <div className="text-[10px] text-slate-400 mt-1 font-sans">
                          Instrument matches statutory &amp; regulatory norms.
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => setResolutionOutcome('discrepancy')}
                        className={`p-3 rounded-lg border text-left transition-all font-mono text-xs ${
                          resolutionOutcome === 'discrepancy'
                            ? 'bg-rose-950/80 border-rose-500 text-rose-300 ring-1 ring-rose-500/30'
                            : 'bg-vault-950 border-vault-800 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <div className="font-bold flex items-center space-x-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                          <span>FLAG DISCREPANCY</span>
                        </div>
                        <div className="text-[10px] text-slate-400 mt-1 font-sans">
                          Values conflict with mock bank or institution norms.
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => setResolutionOutcome('rejected')}
                        className={`p-3 rounded-lg border text-left transition-all font-mono text-xs ${
                          resolutionOutcome === 'rejected'
                            ? 'bg-slate-900 border-rose-400 text-rose-400 ring-1 ring-rose-400/30'
                            : 'bg-vault-950 border-vault-800 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        <div className="font-bold flex items-center space-x-1.5">
                          <XCircle className="w-3.5 h-3.5 text-rose-400" />
                          <span>REJECT RECORD</span>
                        </div>
                        <div className="text-[10px] text-slate-400 mt-1 font-sans">
                          Invalid, corrupted, or illegitimate submission.
                        </div>
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-mono font-medium text-slate-300 mb-1.5">
                      STATUTORY OFFICER REMARKS / RESOLUTION NOTE (MANDATORY):
                    </label>
                    <textarea
                      rows={3}
                      value={resolutionNote}
                      onChange={(e) => setResolutionNote(e.target.value)}
                      placeholder="Specify regulatory findings, verification checks, or reasons for flagging/approval..."
                      className="w-full p-2.5 bg-vault-950 border border-vault-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500/50 font-mono"
                    />
                  </div>

                  <div className="flex items-center justify-end">
                    <button
                      type="submit"
                      disabled={isResolving || !resolutionNote.trim()}
                      className="inline-flex items-center space-x-2 px-5 py-2 rounded-lg bg-vault-amber hover:bg-amber-400 text-vault-950 font-semibold text-xs transition-colors disabled:opacity-50 shadow-lg shadow-amber-500/10"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>{isResolving ? 'Recording Decision...' : 'Commit Sovereign Decision'}</span>
                    </button>
                  </div>
                </form>
              </div>
            </>
          )}
        </div>
      </div>
      )}

      {/* WORKBENCH 2: INSTITUTION ONBOARDING REQUESTS ADJUDICATION */}
      {activeWorkbenchTab === 'onboarding' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Column: Onboarding Requests Queue */}
          <div className="lg:col-span-4 space-y-3">
            <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-4 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <Building className="w-4 h-4 text-blue-400" />
                  <h2 className="font-semibold text-sm text-slate-100">Onboarding Queue</h2>
                </div>
                <button
                  type="button"
                  onClick={loadRegRequests}
                  disabled={isLoadingRegs}
                  className="text-slate-400 hover:text-slate-200 transition-colors p-1"
                  title="Refresh Onboarding Queue"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoadingRegs ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {/* Filter Tabs */}
              <div className="grid grid-cols-5 gap-1 p-1 bg-vault-950 rounded-lg border border-vault-800 text-[11px] font-mono mb-3">
                <button
                  type="button"
                  onClick={() => setRegFilter('pending_verification')}
                  className={`py-1.5 rounded text-center transition-all ${
                    regFilter === 'pending_verification'
                      ? 'bg-amber-950/80 text-amber-300 border border-amber-800/60 font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Pending
                </button>
                <button
                  type="button"
                  onClick={() => setRegFilter('approved')}
                  className={`py-1.5 rounded text-center transition-all ${
                    regFilter === 'approved'
                      ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/60 font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Approved
                </button>
                <button
                  type="button"
                  onClick={() => setRegFilter('rejected')}
                  className={`py-1.5 rounded text-center transition-all ${
                    regFilter === 'rejected'
                      ? 'bg-rose-950/80 text-rose-300 border border-rose-800/60 font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Rejected
                </button>
                <button
                  type="button"
                  onClick={() => setRegFilter('duplicate')}
                  className={`py-1.5 rounded text-center transition-all ${
                    regFilter === 'duplicate'
                      ? 'bg-purple-950/80 text-purple-300 border border-purple-800/60 font-semibold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Duplicate
                </button>
                <button
                  type="button"
                  onClick={() => setRegFilter('all')}
                  className={`py-1.5 rounded text-center transition-all ${
                    regFilter === 'all'
                      ? 'bg-vault-800 text-slate-100 font-semibold shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  All ({regRequests.length})
                </button>
              </div>

              {/* Search Input */}
              <div className="relative mb-3">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search college, ref, or email..."
                  value={regSearch}
                  onChange={(e) => setRegSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-vault-950 border border-vault-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/50"
                />
              </div>

              {/* Request List */}
              {isLoadingRegs ? (
                <div className="py-12 text-center text-xs font-mono text-slate-500">
                  <RefreshCw className="w-5 h-5 mx-auto mb-2 animate-spin text-blue-400" />
                  <span>Loading onboarding requests...</span>
                </div>
              ) : regListError ? (
                <div className="p-3 text-xs font-mono text-rose-400 bg-rose-950/40 rounded-lg border border-rose-800">
                  {regListError}
                </div>
              ) : filteredRegRequests.length === 0 ? (
                <div className="py-12 text-center text-xs font-mono text-slate-500">
                  No institution registration requests found for selected filter.
                </div>
              ) : (
                <div className="space-y-2 max-h-[620px] overflow-y-auto pr-1">
                  {filteredRegRequests.map((req) => {
                    const isSelected = req.id === selectedRegId;
                    const isPending = req.status === 'pending_verification';
                    const isApproved = req.status === 'approved';
                    const isRejected = req.status === 'rejected';

                    return (
                      <div
                        key={req.id}
                        onClick={() => {
                          setSelectedRegId(req.id);
                          setRegActionSuccess(null);
                          setRegActionError(null);
                          setRegReason('');
                        }}
                        className={`p-3 rounded-lg border cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-blue-950/30 border-blue-500/80 shadow-md ring-1 ring-blue-500/50'
                            : 'bg-vault-950/60 border-vault-800/80 hover:bg-vault-800/50 hover:border-vault-700'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2 mb-1.5">
                          <div className="font-semibold text-xs text-slate-200 leading-tight">
                            {req.institution_name}
                          </div>
                          <span
                            className={`text-[9px] font-mono px-2 py-0.5 rounded font-bold uppercase tracking-wider shrink-0 border ${
                              isPending
                                ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                                : isApproved
                                ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                                : isRejected
                                ? 'bg-rose-500/10 text-rose-300 border-rose-500/30'
                                : 'bg-purple-500/10 text-purple-300 border-purple-500/30'
                            }`}
                          >
                            {req.status.replace('_', ' ')}
                          </span>
                        </div>

                        <div className="text-[10px] font-mono text-slate-400 space-y-0.5">
                          <div>Ref: <span className="text-slate-300 font-bold">{req.tracking_reference}</span></div>
                          <div className="truncate">Email: {req.official_email}</div>
                          <div className="flex items-center justify-between text-slate-500 pt-1">
                            <span>Region: {req.region || 'Northern'}</span>
                            <span>{new Date(req.created_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Detailed Adjudication Inspector */}
          <div className="lg:col-span-8 space-y-4">
            {!selectedReg ? (
              <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-12 text-center text-xs font-mono text-slate-500">
                <Building className="w-8 h-8 mx-auto mb-3 text-slate-600" />
                <p>Select an institution registration request from the left queue to inspect details and record regulatory approval decisions.</p>
              </div>
            ) : (
              <>
                {/* Header Card */}
                <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-5 shadow-xl space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/30 font-bold">
                          {selectedReg.tracking_reference}
                        </span>
                        <span className="text-xs font-mono text-slate-500">
                          Submitted on {new Date(selectedReg.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <h1 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
                        <span>{selectedReg.institution_name}</span>
                      </h1>
                    </div>

                    <div className="flex items-center space-x-2">
                      <span
                        className={`text-xs font-mono px-3 py-1 rounded-md font-bold uppercase tracking-wider border ${
                          selectedReg.status === 'pending_verification'
                            ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                            : selectedReg.status === 'approved'
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                            : selectedReg.status === 'rejected'
                            ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                            : 'bg-purple-500/20 text-purple-300 border-purple-500/40'
                        }`}
                      >
                        STATUS: {selectedReg.status.replace('_', ' ').toUpperCase()}
                      </span>
                    </div>
                  </div>

                  {/* Institutional Data Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-3 border-t border-vault-800/80 text-xs font-mono">
                    <div className="p-2.5 rounded-lg bg-vault-950 border border-vault-800/80">
                      <div className="text-[10px] text-slate-500">PERMANENT AICTE ID</div>
                      <div className="font-bold text-slate-200 mt-0.5">
                        {selectedReg.aicte_id || 'Not Provided (To be assigned)'}
                      </div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-vault-950 border border-vault-800/80">
                      <div className="text-[10px] text-slate-500">AICTE REGION</div>
                      <div className="font-bold text-slate-200 mt-0.5">{selectedReg.region || 'Northern'}</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-vault-950 border border-vault-800/80">
                      <div className="text-[10px] text-slate-500">CONTACT PERSON</div>
                      <div className="font-bold text-slate-200 mt-0.5">{selectedReg.contact_person}</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-vault-950 border border-vault-800/80 sm:col-span-2">
                      <div className="text-[10px] text-slate-500">OFFICIAL CONTACT EMAIL</div>
                      <div className="font-bold text-blue-400 mt-0.5">{selectedReg.official_email}</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-vault-950 border border-vault-800/80">
                      <div className="text-[10px] text-slate-500">TRACKING IDENTIFIER</div>
                      <div className="font-bold text-amber-400 mt-0.5">{selectedReg.tracking_reference}</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-vault-950 border border-vault-800/80 sm:col-span-3">
                      <div className="text-[10px] text-slate-500">CAMPUS ADDRESS</div>
                      <div className="text-slate-300 mt-0.5 font-sans text-xs">
                        {selectedReg.address || 'Address details pending statutory verification.'}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Statutory Isolation Notice */}
                <div className="p-4 rounded-xl bg-blue-950/30 border border-blue-500/40 text-blue-200 text-xs font-mono space-y-1">
                  <div className="font-bold flex items-center space-x-2 text-blue-300">
                    <Shield className="w-4 h-4 text-blue-400" />
                    <span>Multi-Tenant Segregation Enforcement:</span>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed font-sans">
                    This institution and its contact applicants have zero access to the FDR vault, ledger, or documents. Upon authorized approval, the institution is cataloged in the active registry and linked to verified credentials.
                  </p>
                </div>

                {/* Action Feedback Alerts */}
                {regActionSuccess && (
                  <div className="p-3.5 rounded-lg bg-emerald-950/60 border border-emerald-800/80 text-emerald-300 text-xs font-mono flex items-start space-x-2">
                    <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5 text-emerald-400" />
                    <span>{regActionSuccess}</span>
                  </div>
                )}

                {regActionError && (
                  <div className="p-3.5 rounded-lg bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs font-mono flex items-start space-x-2">
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
                    <span>{regActionError}</span>
                  </div>
                )}

                {/* Adjudication Workbench (If Pending) */}
                {selectedReg.status === 'pending_verification' ? (
                  <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-5 shadow-xl space-y-4">
                    <div className="flex items-center space-x-2 border-b border-vault-800 pb-3">
                      <FileCheck2 className="w-4 h-4 text-vault-amber" />
                      <h2 className="text-sm font-bold text-slate-100 font-mono uppercase tracking-wider">
                        Statutory Regulatory Adjudication
                      </h2>
                    </div>

                    <form onSubmit={handleAdjudicateRegRequest} className="space-y-4">
                      <div>
                        <label className="block text-xs font-mono font-medium text-slate-300 mb-2">
                          SELECT REGULATORY DECISION:
                        </label>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          <button
                            type="button"
                            onClick={() => setRegDecision('approved')}
                            className={`p-3 rounded-lg border text-left transition-all ${
                              regDecision === 'approved'
                                ? 'bg-emerald-950/70 border-emerald-500 ring-1 ring-emerald-500/60 text-emerald-200'
                                : 'bg-vault-950 border-vault-800 text-slate-400 hover:border-slate-700'
                            }`}
                          >
                            <div className="font-bold flex items-center space-x-1.5 text-xs font-mono">
                              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                              <span>APPROVE INSTITUTION</span>
                            </div>
                            <div className="text-[10px] text-slate-400 mt-1 font-sans">
                              Registers active institution, establishes AICTE tenancy, updates ledger.
                            </div>
                          </button>

                          <button
                            type="button"
                            onClick={() => setRegDecision('rejected')}
                            className={`p-3 rounded-lg border text-left transition-all ${
                              regDecision === 'rejected'
                                ? 'bg-rose-950/70 border-rose-500 ring-1 ring-rose-500/60 text-rose-200'
                                : 'bg-vault-950 border-vault-800 text-slate-400 hover:border-slate-700'
                            }`}
                          >
                            <div className="font-bold flex items-center space-x-1.5 text-xs font-mono">
                              <XCircle className="w-4 h-4 text-rose-400" />
                              <span>REJECT APPLICATION</span>
                            </div>
                            <div className="text-[10px] text-slate-400 mt-1 font-sans">
                              Rejects unverified or fraudulent college registration.
                            </div>
                          </button>

                          <button
                            type="button"
                            onClick={() => setRegDecision('duplicate')}
                            className={`p-3 rounded-lg border text-left transition-all ${
                              regDecision === 'duplicate'
                                ? 'bg-purple-950/70 border-purple-500 ring-1 ring-purple-500/60 text-purple-200'
                                : 'bg-vault-950 border-vault-800 text-slate-400 hover:border-slate-700'
                            }`}
                          >
                            <div className="font-bold flex items-center space-x-1.5 text-xs font-mono">
                              <Copy className="w-4 h-4 text-purple-400" />
                              <span>MARK DUPLICATE</span>
                            </div>
                            <div className="text-[10px] text-slate-400 mt-1 font-sans">
                              Identifies duplicate of an already registered college.
                            </div>
                          </button>
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs font-mono font-medium text-slate-300 mb-1.5">
                          OFFICER STATUTORY REASON / VERIFICATION GROUNDS (MANDATORY):
                        </label>
                        <textarea
                          rows={3}
                          value={regReason}
                          onChange={(e) => setRegReason(e.target.value)}
                          placeholder="Specify verification grounds, state gazette code, AICTE Approval Letter reference, or reasons for rejection/duplicate..."
                          className="w-full p-2.5 bg-vault-950 border border-vault-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono"
                        />
                      </div>

                      <div className="flex items-center justify-end">
                        <button
                          type="submit"
                          disabled={isSubmittingRegReview || !regReason.trim()}
                          className="inline-flex items-center space-x-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs font-mono transition shadow disabled:opacity-50"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>
                            {isSubmittingRegReview
                              ? 'Recording Regulatory Decision...'
                              : 'Commit Statutory Adjudication Decision'}
                          </span>
                        </button>
                      </div>
                    </form>
                  </div>
                ) : (
                  /* Already Adjudicated Information Card */
                  <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-5 shadow-xl space-y-3 font-mono">
                    <div className="flex items-center space-x-2 border-b border-vault-800 pb-3">
                      <FileCheck2 className="w-4 h-4 text-emerald-400" />
                      <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                        Adjudicated Regulatory Record
                      </h2>
                    </div>

                    <div className="p-4 rounded-lg bg-vault-950 border border-vault-800 space-y-2 text-xs">
                      <div>
                        <strong>Final Decision:</strong>{' '}
                        <span className="font-bold text-white uppercase">{selectedReg.status}</span>
                      </div>
                      <div>
                        <strong>Statutory Reason / Remarks:</strong>{' '}
                        <span className="text-slate-300 font-sans">{selectedReg.review_reason || 'Verified by authorized vigilance directorate.'}</span>
                      </div>
                      {selectedReg.reviewed_at && (
                        <div>
                          <strong>Adjudicated Timestamp:</strong>{' '}
                          <span className="text-slate-400">{new Date(selectedReg.reviewed_at).toLocaleString()}</span>
                        </div>
                      )}
                      <div className="text-[11px] text-emerald-400 pt-1">
                        ✓ Tamper-evident cryptographic block recorded to sovereign SHA-256 audit ledger.
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* WORKBENCH 3: DOCUMENT REVIEW QUEUE (NON-FDR & INTAKE ADJUDICATION) */}
      {activeWorkbenchTab === 'document_review' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Column: Review Queue List */}
          <div className="lg:col-span-5 space-y-3">
            <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-4 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <FileX2 className="w-4 h-4 text-purple-400" />
                  <h2 className="font-semibold text-sm text-slate-100">Document Review Queue</h2>
                </div>
                <button
                  onClick={loadReviewQueue}
                  disabled={isLoadingReview}
                  className="text-slate-400 hover:text-slate-200 transition-colors p-1"
                  title="Refresh Queue"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoadingReview ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {/* Status Filter Tabs */}
              <div className="flex flex-wrap gap-1 mb-3 bg-vault-950 p-1 rounded-lg border border-vault-800 text-xs font-mono">
                {(['pending', 'confirmed_unrelated', 'overridden_as_fdr', 'dismissed', 'all'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => {
                      setReviewFilter(tab);
                      setSelectedReviewId(null);
                    }}
                    className={`px-2.5 py-1 rounded text-[11px] font-medium capitalize transition-colors ${
                      reviewFilter === tab
                        ? 'bg-purple-600 text-white shadow font-semibold'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-vault-800'
                    }`}
                  >
                    {tab.replace('_', ' ')}
                  </button>
                ))}
              </div>

              {/* Search Bar */}
              <div className="relative mb-3">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search by file, institution, or SHA-256..."
                  value={reviewSearch}
                  onChange={(e) => setReviewSearch(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-vault-950 border border-vault-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500 font-mono"
                />
              </div>

              {/* Items List */}
              {isLoadingReview ? (
                <div className="py-12 text-center text-slate-400 text-xs font-mono animate-pulse">
                  Querying staged document review queue...
                </div>
              ) : reviewListError ? (
                <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-mono">
                  {reviewListError}
                </div>
              ) : filteredReviewItems.length === 0 ? (
                <div className="py-12 text-center text-slate-500 text-xs font-mono">
                  No documents found matching current filter criteria.
                </div>
              ) : (
                <div className="space-y-2 max-h-[620px] overflow-y-auto pr-1">
                  {filteredReviewItems.map((item) => {
                    const isSelected = item.id === selectedReviewId;
                    return (
                      <div
                        key={item.id}
                        onClick={() => setSelectedReviewId(item.id)}
                        className={`p-3 rounded-lg border transition-all cursor-pointer font-mono ${
                          isSelected
                            ? 'bg-purple-950/40 border-purple-500/60 shadow-lg'
                            : 'bg-vault-950/70 border-vault-800/80 hover:bg-vault-800/60'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="font-semibold text-slate-200 text-xs truncate flex items-center space-x-1.5">
                              <FileText className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                              <span className="truncate">{item.filename}</span>
                            </div>
                            <div className="text-[11px] text-slate-400 truncate mt-0.5 font-sans">
                              {item.institution_name || `Institution ${item.institution_id.slice(0, 8)}`}
                            </div>
                          </div>

                          <div className="shrink-0 flex flex-col items-end gap-1">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                item.review_status === 'pending'
                                  ? 'bg-amber-950/80 border border-amber-700/60 text-amber-400'
                                  : item.review_status === 'confirmed_unrelated'
                                  ? 'bg-rose-950/80 border border-rose-700/60 text-rose-400'
                                  : item.review_status === 'overridden_as_fdr'
                                  ? 'bg-emerald-950/80 border border-emerald-700/60 text-emerald-400'
                                  : 'bg-slate-800 text-slate-300'
                              }`}
                            >
                              {item.review_status.toUpperCase().replace('_', ' ')}
                            </span>
                            {item.is_strike && (
                              <span className="px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 text-[9px] font-bold">
                                STRIKE RECORDED
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center justify-between text-[10px] text-slate-500 mt-2 pt-2 border-t border-vault-800/60">
                          <span className="text-purple-400 font-semibold truncate max-w-[200px]">
                            {item.detected_document_type || item.classification.replace('_', ' ')}
                          </span>
                          <span>{new Date(item.created_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Review Details & Adjudication Controls */}
          <div className="lg:col-span-7 space-y-4">
            {!selectedReviewItem ? (
              <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-12 text-center text-slate-500 text-xs font-mono">
                Select a document from the review queue to inspect detected content and submit regulatory adjudication.
              </div>
            ) : (
              <>
                {/* Document Information Card */}
                <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-5 shadow-xl space-y-4 font-mono">
                  <div className="flex items-start justify-between border-b border-vault-800 pb-3 gap-2">
                    <div>
                      <h2 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
                        <FileX2 className="w-4 h-4 text-purple-400" />
                        <span>{selectedReviewItem.filename}</span>
                      </h2>
                      <div className="text-xs text-slate-400 font-sans mt-0.5">
                        {selectedReviewItem.institution_name || selectedReviewItem.institution_id}
                      </div>
                    </div>

                    <span
                      className={`px-2.5 py-1 rounded text-xs font-bold ${
                        selectedReviewItem.review_status === 'pending'
                          ? 'bg-amber-950 border border-amber-700/60 text-amber-400'
                          : selectedReviewItem.review_status === 'confirmed_unrelated'
                          ? 'bg-rose-950 border border-rose-700/60 text-rose-400'
                          : selectedReviewItem.review_status === 'overridden_as_fdr'
                          ? 'bg-emerald-950 border border-emerald-700/60 text-emerald-400'
                          : 'bg-slate-800 text-slate-300'
                      }`}
                    >
                      STATUS: {selectedReviewItem.review_status.toUpperCase().replace('_', ' ')}
                    </span>
                  </div>

                  {/* SHA-256 Digest */}
                  <div className="p-2.5 rounded bg-vault-950 border border-vault-800 flex items-center justify-between text-xs">
                    <div className="truncate">
                      <span className="text-slate-500 text-[10px] block">DOCUMENT SHA-256 DIGEST:</span>
                      <span className="text-amber-400 text-[11px] select-all font-mono">
                        {selectedReviewItem.document_sha256}
                      </span>
                    </div>
                    <button
                      onClick={() => navigator.clipboard.writeText(selectedReviewItem.document_sha256)}
                      className="px-2 py-1 rounded bg-vault-900 hover:bg-vault-800 text-slate-300 text-[11px] shrink-0 ml-2"
                      title="Copy SHA-256"
                    >
                      Copy
                    </button>
                  </div>

                  {/* Classification Summary Card */}
                  <div className="p-4 rounded-lg bg-vault-950 border border-vault-800 space-y-2.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 text-[11px] uppercase">Detected Document Profile:</span>
                      <span className="font-bold text-rose-400 text-xs">
                        {selectedReviewItem.detected_document_type || 'Unrelated Document Profile'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-slate-400 text-[11px] uppercase">Algorithmic Confidence:</span>
                      <span className="font-bold text-amber-400 text-xs">
                        {Math.round((selectedReviewItem.confidence || 0.8) * 100)}%
                      </span>
                    </div>

                    <div className="pt-1 text-slate-300 font-sans leading-relaxed border-t border-vault-900">
                      <strong>Content Summary (Automated Estimate):</strong>{' '}
                      {selectedReviewItem.content_summary || 'Document lacks banking Fixed Deposit receipt structure.'}
                    </div>

                    {selectedReviewItem.classification_reasons && selectedReviewItem.classification_reasons.length > 0 && (
                      <div className="pt-2 border-t border-vault-900 space-y-1">
                        <div className="text-[10px] text-slate-400 uppercase font-semibold">Classification Evidence:</div>
                        <ul className="list-disc list-inside space-y-0.5 text-slate-300 text-[11px]">
                          {selectedReviewItem.classification_reasons.map((r, idx) => (
                            <li key={idx}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {selectedReviewItem.extracted_snippets && selectedReviewItem.extracted_snippets.length > 0 && (
                      <div className="pt-2 border-t border-vault-900 space-y-1">
                        <div className="text-[10px] text-slate-400 uppercase font-semibold">Extracted Non-Sensitive Snippets:</div>
                        <div className="flex flex-wrap gap-1.5">
                          {selectedReviewItem.extracted_snippets.map((snip, idx) => (
                            <span key={idx} className="px-2 py-0.5 rounded bg-vault-900 border border-vault-700 text-slate-300 text-[10px]">
                              "{snip}"
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Adjudication Action Form or Adjudicated Details */}
                {selectedReviewItem.review_status === 'pending' ? (
                  <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-5 shadow-xl space-y-4">
                    <div className="flex items-center space-x-2 border-b border-vault-800 pb-3">
                      <Scale className="w-4 h-4 text-purple-400" />
                      <h2 className="text-sm font-bold text-slate-100 font-mono uppercase tracking-wider">
                        Statutory Regulatory Adjudication
                      </h2>
                    </div>

                    {reviewError && (
                      <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-mono">
                        {reviewError}
                      </div>
                    )}

                    {reviewSuccess && (
                      <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
                        {reviewSuccess}
                      </div>
                    )}

                    <form onSubmit={handleAdjudicateReview} className="space-y-4">
                      <div>
                        <label className="block text-xs font-mono font-medium text-slate-300 mb-2">
                          SELECT REGULATORY ADJUDICATION DETERMINATION:
                        </label>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                          <button
                            type="button"
                            onClick={() => setAdjudicationDecision('confirm_unrelated')}
                            className={`p-3 rounded-lg border text-left transition-all ${
                              adjudicationDecision === 'confirm_unrelated'
                                ? 'bg-rose-950/60 border-rose-500 text-rose-200 ring-1 ring-rose-500'
                                : 'bg-vault-950 border-vault-800 text-slate-300 hover:border-slate-600'
                            }`}
                          >
                            <div className="font-bold flex items-center space-x-1.5 text-xs font-mono text-rose-400">
                              <XCircle className="w-4 h-4" />
                              <span>CONFIRM UNRELATED</span>
                            </div>
                            <div className="text-[10px] text-slate-400 mt-1 font-sans">
                              Confirms non-FDR. Increments strike (deduplicated by file hash; 7 strikes trigger temporary upload hold).
                            </div>
                          </button>

                          <button
                            type="button"
                            onClick={() => setAdjudicationDecision('override_as_fdr')}
                            className={`p-3 rounded-lg border text-left transition-all ${
                              adjudicationDecision === 'override_as_fdr'
                                ? 'bg-emerald-950/60 border-emerald-500 text-emerald-200 ring-1 ring-emerald-500'
                                : 'bg-vault-950 border-vault-800 text-slate-300 hover:border-slate-600'
                            }`}
                          >
                            <div className="font-bold flex items-center space-x-1.5 text-xs font-mono text-emerald-400">
                              <CheckCircle2 className="w-4 h-4" />
                              <span>OVERRIDE AS FDR</span>
                            </div>
                            <div className="text-[10px] text-slate-400 mt-1 font-sans">
                              Overrides classification. Permits college to register and mint FDR into vault.
                            </div>
                          </button>

                          <button
                            type="button"
                            onClick={() => setAdjudicationDecision('dismiss')}
                            className={`p-3 rounded-lg border text-left transition-all ${
                              adjudicationDecision === 'dismiss'
                                ? 'bg-slate-800 border-slate-500 text-slate-200 ring-1 ring-slate-500'
                                : 'bg-vault-950 border-vault-800 text-slate-300 hover:border-slate-600'
                            }`}
                          >
                            <div className="font-bold flex items-center space-x-1.5 text-xs font-mono text-slate-300">
                              <Shield className="w-4 h-4" />
                              <span>DISMISS REVIEW</span>
                            </div>
                            <div className="text-[10px] text-slate-400 mt-1 font-sans">
                              Dismisses review without strike penalty (e.g. unreadable scan or test upload).
                            </div>
                          </button>
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs font-mono font-medium text-slate-300 mb-1.5">
                          OFFICER ADJUDICATION GROUNDS &amp; REMARKS (MANDATORY):
                        </label>
                        <textarea
                          rows={3}
                          value={adjudicationReason}
                          onChange={(e) => setAdjudicationReason(e.target.value)}
                          placeholder="State the regulatory grounds for confirming unrelated, overriding, or dismissing this document submission..."
                          className="w-full p-2.5 bg-vault-950 border border-vault-800 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500 font-mono"
                          required
                        />
                      </div>

                      <div className="flex items-center justify-end">
                        <button
                          type="submit"
                          disabled={isAdjudicating || !adjudicationReason.trim()}
                          className="inline-flex items-center space-x-2 px-5 py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs font-mono transition shadow disabled:opacity-50"
                        >
                          <Send className="w-3.5 h-3.5" />
                          <span>
                            {isAdjudicating ? 'Committing Decision...' : 'Commit Regulatory Adjudication Decision'}
                          </span>
                        </button>
                      </div>
                    </form>
                  </div>
                ) : (
                  /* Already Adjudicated Information Card */
                  <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-5 shadow-xl space-y-3 font-mono">
                    <div className="flex items-center space-x-2 border-b border-vault-800 pb-3">
                      <FileCheck2 className="w-4 h-4 text-emerald-400" />
                      <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                        Adjudicated Regulatory Record
                      </h2>
                    </div>

                    <div className="p-4 rounded-lg bg-vault-950 border border-vault-800 space-y-2 text-xs">
                      <div>
                        <strong>Final Determination:</strong>{' '}
                        <span className="font-bold text-white uppercase">{selectedReviewItem.review_status}</span>
                      </div>
                      <div>
                        <strong>Strike Impact:</strong>{' '}
                        <span className={selectedReviewItem.is_strike ? 'text-rose-400 font-bold' : 'text-slate-400'}>
                          {selectedReviewItem.is_strike ? 'Strike Assigned' : 'No Strike Assigned'}
                        </span>
                      </div>
                      <div>
                        <strong>Officer Justification:</strong>{' '}
                        <span className="text-slate-300 font-sans">
                          {selectedReviewItem.review_reason || 'Adjudicated by vigilance directorate.'}
                        </span>
                      </div>
                      {selectedReviewItem.reviewed_by && (
                        <div>
                          <strong>Adjudicated By:</strong>{' '}
                          <span className="text-slate-400">
                            {selectedReviewItem.reviewer_name || selectedReviewItem.reviewed_by}
                          </span>
                        </div>
                      )}
                      {selectedReviewItem.reviewed_at && (
                        <div>
                          <strong>Adjudicated Timestamp:</strong>{' '}
                          <span className="text-slate-400">
                            {new Date(selectedReviewItem.reviewed_at).toLocaleString()}
                          </span>
                        </div>
                      )}
                      <div className="text-[11px] text-emerald-400 pt-1">
                        ✓ Tamper-evident cryptographic audit block committed to sovereign SHA-256 ledger.
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* WORKBENCH 4: INSTITUTION UPLOAD HOLDS & APPEALS (ADMIN ONLY) */}
      {activeWorkbenchTab === 'upload_holds' && user?.role === 'admin' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Column: Held Institutions List */}
          <div className="lg:col-span-5 space-y-3">
            <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-4 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <Ban className="w-4 h-4 text-rose-400" />
                  <h2 className="font-semibold text-sm text-slate-100">Upload Review Holds &amp; Appeals</h2>
                </div>
                <button
                  onClick={loadHeldInstitutions}
                  disabled={isLoadingHeld}
                  className="text-slate-400 hover:text-slate-200 transition-colors p-1"
                  title="Refresh Holds"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isLoadingHeld ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {isLoadingHeld ? (
                <div className="py-12 text-center text-slate-400 text-xs font-mono animate-pulse">
                  Querying upload hold registry...
                </div>
              ) : heldListError ? (
                <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-mono">
                  {heldListError}
                </div>
              ) : heldInstitutions.length === 0 ? (
                <div className="py-12 text-center text-slate-500 text-xs font-mono">
                  No institutions currently on upload review hold.
                </div>
              ) : (
                <div className="space-y-2 max-h-[620px] overflow-y-auto pr-1">
                  {heldInstitutions.map((inst) => {
                    const isSelected = inst.institution_id === selectedHeldInstId;
                    return (
                      <div
                        key={inst.institution_id}
                        onClick={() => setSelectedHeldInstId(inst.institution_id)}
                        className={`p-3 rounded-lg border transition-all cursor-pointer font-mono ${
                          isSelected
                            ? 'bg-rose-950/40 border-rose-500/60 shadow-lg'
                            : 'bg-vault-950/70 border-vault-800/80 hover:bg-vault-800/60'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="font-semibold text-slate-200 text-xs truncate">
                              {inst.institution_name}
                            </div>
                            <div className="text-[11px] text-slate-400 truncate mt-0.5">
                              {inst.institution_id.slice(0, 8)}...
                            </div>
                          </div>

                          <span className="px-2 py-0.5 rounded bg-rose-950 border border-rose-700/60 text-rose-400 text-[10px] font-bold shrink-0">
                            {inst.confirmed_strikes_in_window} / {inst.strike_threshold} STRIKES
                          </span>
                        </div>

                        <div className="mt-2 pt-2 border-t border-vault-800/60 flex items-center justify-between text-[10px]">
                          <span className="text-slate-400">
                            Until: {inst.upload_hold_until ? new Date(inst.upload_hold_until).toLocaleDateString() : 'Indefinite'}
                          </span>
                          {inst.upload_hold_appealed_at ? (
                            <span className="px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 font-bold">
                              APPEAL PENDING
                            </span>
                          ) : (
                            <span className="text-slate-500">No appeal submitted</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Hold Management & Appeal Review */}
          <div className="lg:col-span-7 space-y-4">
            {!selectedHeldInst ? (
              <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-12 text-center text-slate-500 text-xs font-mono">
                Select a held institution from the left to view hold reason, review appeals, or unfreeze/extend hold.
              </div>
            ) : (
              <div className="bg-vault-900/90 border border-vault-800 rounded-xl p-5 shadow-xl space-y-4 font-mono">
                <div className="flex items-start justify-between border-b border-vault-800 pb-3 gap-2">
                  <div>
                    <h2 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
                      <Ban className="w-4 h-4 text-rose-400" />
                      <span>{selectedHeldInst.institution_name}</span>
                    </h2>
                    <div className="text-xs text-slate-400 font-sans mt-0.5">
                      Institution ID: {selectedHeldInst.institution_id}
                    </div>
                  </div>

                  <span className="px-2.5 py-1 rounded bg-rose-950 border border-rose-700/60 text-rose-400 text-xs font-bold">
                    HOLD ACTIVE
                  </span>
                </div>

                {holdActionError && (
                  <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                    {holdActionError}
                  </div>
                )}

                {holdActionSuccess && (
                  <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs">
                    {holdActionSuccess}
                  </div>
                )}

                {/* Hold Details */}
                <div className="p-4 rounded-lg bg-vault-950 border border-vault-800 space-y-2 text-xs">
                  <div>
                    <strong>Hold Justification:</strong>{' '}
                    <span className="text-slate-300 font-sans">{selectedHeldInst.upload_hold_reason || 'N/A'}</span>
                  </div>
                  <div>
                    <strong>Hold Effective Until:</strong>{' '}
                    <span className="text-amber-400">
                      {selectedHeldInst.upload_hold_until ? new Date(selectedHeldInst.upload_hold_until).toLocaleString() : 'N/A'}
                    </span>
                  </div>
                  <div>
                    <strong>Confirmed Unrelated Strikes:</strong>{' '}
                    <span className="text-rose-400 font-bold">{selectedHeldInst.confirmed_strikes_in_window}</span> (threshold: {selectedHeldInst.strike_threshold} in {selectedHeldInst.window_days} days)
                  </div>
                  <div className="text-[11px] text-emerald-400 pt-1">
                    ✓ Read access to existing FDR records remains operational.
                  </div>
                </div>

                {/* Appeal Section (if present) */}
                {selectedHeldInst.upload_hold_appealed_at && (
                  <div className="p-4 rounded-lg bg-amber-950/40 border border-amber-600/60 space-y-2 text-xs">
                    <div className="flex items-center justify-between text-amber-300 font-bold text-xs">
                      <span>FORMAL INSTITUTION APPEAL STATEMENT:</span>
                      <span className="text-[10px] text-amber-400 font-normal">
                        Submitted {new Date(selectedHeldInst.upload_hold_appealed_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="p-3 rounded bg-vault-950 border border-amber-800/40 text-slate-200 font-sans leading-relaxed">
                      {selectedHeldInst.upload_hold_appeal_reason}
                    </div>
                  </div>
                )}

                {/* Admin Actions */}
                <div className="space-y-4 pt-2">
                  {/* Action 1: Lift / Unfreeze Hold */}
                  <div className="p-4 rounded-lg bg-vault-950 border border-vault-800 space-y-3">
                    <div className="flex items-center space-x-2 text-xs font-bold text-emerald-400 uppercase tracking-wider">
                      <ShieldAlert className="w-4 h-4" />
                      <span>Lift Review Hold &amp; Restore FDR Uploads (Administrative Unfreeze)</span>
                    </div>
                    <p className="text-[11px] text-slate-400 font-sans">
                      Clears the upload hold immediately, notifies institution users, and records an unalterable SHA-256 audit block.
                    </p>
                    <div className="space-y-2">
                      <input
                        type="text"
                        placeholder="Justification for lifting hold (e.g., appeal accepted, corrective training completed)..."
                        value={unfreezeReason}
                        onChange={(e) => setUnfreezeReason(e.target.value)}
                        className="w-full p-2 bg-vault-900 border border-vault-700 rounded text-xs text-slate-200 font-mono"
                      />
                      <button
                        type="button"
                        onClick={() => handleAdminUnfreeze(selectedHeldInst.institution_id)}
                        disabled={isManagingHold || !unfreezeReason.trim()}
                        className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition disabled:opacity-50"
                      >
                        {isManagingHold ? 'Processing...' : 'Confirm Unfreeze & Restore Uploads'}
                      </button>
                    </div>
                  </div>

                  {/* Action 2: Extend Hold */}
                  <div className="p-4 rounded-lg bg-vault-950 border border-vault-800 space-y-3">
                    <div className="flex items-center space-x-2 text-xs font-bold text-amber-400 uppercase tracking-wider">
                      <Scale className="w-4 h-4" />
                      <span>Extend Upload Hold Duration</span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-2 items-center">
                      <div className="space-y-1">
                        <label className="text-[10px] text-slate-400">Additional Days:</label>
                        <input
                          type="number"
                          min={1}
                          max={90}
                          value={extendDays}
                          onChange={(e) => setExtendDays(Number(e.target.value))}
                          className="w-full p-2 bg-vault-900 border border-vault-700 rounded text-xs text-slate-200 font-mono"
                        />
                      </div>
                      <div className="md:col-span-3 space-y-1">
                        <label className="text-[10px] text-slate-400">Extension Justification:</label>
                        <input
                          type="text"
                          placeholder="Reason for extension..."
                          value={extendReason}
                          onChange={(e) => setExtendReason(e.target.value)}
                          className="w-full p-2 bg-vault-900 border border-vault-700 rounded text-xs text-slate-200 font-mono"
                        />
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleAdminExtend(selectedHeldInst.institution_id)}
                      disabled={isManagingHold || !extendReason.trim()}
                      className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs transition disabled:opacity-50"
                    >
                      {isManagingHold ? 'Processing...' : `Extend Hold by ${extendDays} Days`}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
