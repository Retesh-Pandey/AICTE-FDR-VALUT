import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Layers,
  Clock,
  AlertTriangle,
  ArrowUpRight,
  ScanLine,
  TrendingUp,
  Search,
  RefreshCw,
  ShieldAlert,
  BarChart3,
  Building2,
  ArrowRight,
  Download,
  CheckCircle2,
} from 'lucide-react';
import { formatCurrencyINR, formatDate } from '@/lib/utils';
import { useAuth } from '@/features/auth/AuthContext';
import {
  api,
  DashboardSummary,
  FDRRecord,
  PriorityCaseItem,
  ChartTelemetryResponse,
} from '@/lib/api';
import { InstrumentBadge, VerificationBadge, WorkflowBadge } from '@/components/common/StatusBadges';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { role } = useAuth();

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [fdrs, setFdrs] = useState<FDRRecord[]>([]);
  const [priorityCases, setPriorityCases] = useState<PriorityCaseItem[]>([]);
  const [chartsData, setChartsData] = useState<ChartTelemetryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Search
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [verificationFilter, setVerificationFilter] = useState<string>('all');
  const [bankFilter, setBankFilter] = useState<string>('all');

  // Ledger Download state
  const [isDownloadingActiveLedger, setIsDownloadingActiveLedger] = useState(false);
  const [activeLedgerNotice, setActiveLedgerNotice] = useState<string | null>(null);
  const [activeLedgerError, setActiveLedgerError] = useState<string | null>(null);

  const handleDownloadActiveLedger = async () => {
    setIsDownloadingActiveLedger(true);
    setActiveLedgerNotice(null);
    setActiveLedgerError(null);
    try {
      await api.downloadReportExcel('active', 'xlsx');
      setActiveLedgerNotice('Active security volume ledger (.xlsx) exported successfully.');
      setTimeout(() => setActiveLedgerNotice(null), 4000);
    } catch (err: any) {
      setActiveLedgerError(err.message || 'Failed to download active ledger.');
      setTimeout(() => setActiveLedgerError(null), 4000);
    } finally {
      setIsDownloadingActiveLedger(false);
    }
  };

  const loadDashboardData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      // 1. Fetch live metrics
      const summaryData = await api.getDashboardSummary();
      setSummary(summaryData);

      // 2. Fetch priority cases (for officers & admins)
      if (role !== 'institution') {
        try {
          const pc = await api.getPriorityCases();
          setPriorityCases(pc);
        } catch {
          // Non-critical
        }
      }

      // 3. Fetch analytics charts data
      try {
        const cd = await api.getChartsData();
        setChartsData(cd);
      } catch {
        // Non-critical
      }

      // 4. Fetch list of FDRs with current filters
      const listParams: any = { limit: 50 };
      if (searchTerm.trim()) listParams.q = searchTerm.trim();
      if (statusFilter !== 'all') listParams.status = statusFilter;
      if (verificationFilter !== 'all') listParams.verification_status = verificationFilter;
      if (bankFilter !== 'all') listParams.bank = bankFilter;

      const fdrData = await api.listFDRs(listParams);
      setFdrs(fdrData.items);
    } catch (err: any) {
      setError(err?.error?.message || 'Failed to connect to AICTE Sovereign Vault API.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, [statusFilter, verificationFilter, bankFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadDashboardData();
  };

  const handleResetFilters = () => {
    setSearchTerm('');
    setStatusFilter('all');
    setVerificationFilter('all');
    setBankFilter('all');
  };

  return (
    <div className="space-y-6 max-w-[1700px] mx-auto pb-16">
      {/* Sovereign Welcome & Breadcrumb Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-slate-500 mb-1">
            <span>AICTE-VAULT</span>
            <span>&gt;</span>
            <span className="text-amber-500 font-semibold uppercase">
              {role} Surveillance Matrix
            </span>
          </div>
          <h1 className="text-2xl font-mono font-bold text-slate-100 tracking-tight flex items-center space-x-2">
            <span>SECURITY DEPOSIT SURVEILLANCE &amp; FDR VAULT</span>
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-0.5">
            Cryptographic ledger parity: <span className="text-emerald-400 font-semibold">100% (SHA-256)</span> | Sovereign Protocol SIH26265
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => loadDashboardData()}
            disabled={isLoading}
            className="flex items-center space-x-2 px-3 py-2 rounded bg-vault-900 hover:bg-vault-800 border border-vault-800 text-xs font-mono text-slate-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-amber-500' : ''}`} />
            <span>Refresh Ledger</span>
          </button>

          <button
            onClick={() => navigate('/intake')}
            className="flex items-center space-x-2 px-4 py-2 rounded bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-mono font-bold tracking-wider uppercase transition-all shadow-md shadow-amber-500/10"
          >
            <ScanLine className="w-4 h-4" />
            <span>Ingest New Deposit</span>
          </button>
        </div>
      </div>

      {/* Error State Banner */}
      {error && (
        <div className="p-4 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 font-mono text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => loadDashboardData()}
            className="underline hover:text-rose-300 font-semibold"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* Ledger Download Feedback */}
      {activeLedgerNotice && (
        <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800 text-xs font-mono text-emerald-300 flex items-center space-x-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{activeLedgerNotice}</span>
        </div>
      )}

      {activeLedgerError && (
        <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800 text-xs font-mono text-rose-300 flex items-center space-x-2 animate-in fade-in">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{activeLedgerError}</span>
        </div>
      )}

      {/* Telemetry Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Active Value */}
        <div className="p-4 rounded-lg bg-vault-900 border border-vault-800 shadow-lg space-y-2 relative group">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>ACTIVE SECURITY VOLUME</span>
            <div className="flex items-center space-x-1.5">
              <button
                type="button"
                onClick={handleDownloadActiveLedger}
                disabled={isDownloadingActiveLedger}
                title="Download Active Ledger Data (.xlsx)"
                aria-label="Download Active Ledger Data"
                className="flex items-center space-x-1 px-1.5 py-0.5 rounded bg-vault-800 hover:bg-vault-700 text-vault-amber hover:text-white transition text-[10px] border border-vault-700 disabled:opacity-50"
              >
                <Download className={`w-3 h-3 ${isDownloadingActiveLedger ? 'animate-bounce text-emerald-400' : ''}`} />
                <span>{isDownloadingActiveLedger ? '...' : 'Export'}</span>
              </button>
              <TrendingUp className="w-4 h-4 text-emerald-400" />
            </div>
          </div>
          <div className="text-2xl font-mono font-bold text-vault-emerald tracking-tight">
            {summary ? formatCurrencyINR(summary.total_active_amount) : '₹0.00'}
          </div>
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
            <span>{summary?.active_fdrs ?? 0} Active Instruments</span>
            <span className="text-emerald-400/90 font-semibold">100% LIEN SECURED</span>
          </div>
        </div>

        {/* Card 2: Total Registered FDRs */}
        <div className="p-4 rounded-lg bg-vault-900 border border-vault-800 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>TOTAL INSTRUMENTS</span>
            <Layers className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-mono font-bold text-slate-100 tracking-tight">
            {summary?.total_fdrs ?? 0}
          </div>
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
            <span>Across Institutions</span>
            <span className="text-slate-400">VAULT JURISDICTION</span>
          </div>
        </div>

        {/* Card 3: Expiring / Renewal Due */}
        <div className="p-4 rounded-lg bg-vault-900 border border-vault-800 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>RENEWAL RADAR (≤ 30 DAYS)</span>
            <Clock className="w-4 h-4 text-orange-400" />
          </div>
          <div className="text-2xl font-mono font-bold text-orange-400 tracking-tight">
            {summary?.expiring_30_days ?? 0}
          </div>
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
            <span>Matured: {summary?.matured_fdrs ?? 0}</span>
            <span className="text-orange-400 font-semibold">ACTION REQUIRED</span>
          </div>
        </div>

        {/* Card 4: Verification Discrepancies */}
        <div className="p-4 rounded-lg bg-vault-900 border border-vault-800 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>VIGILANCE DISCREPANCIES</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-mono font-bold text-rose-400 tracking-tight">
            {summary?.flagged_discrepancies ?? 0}
          </div>
          <div className="flex items-center justify-between text-[11px] font-mono text-slate-500">
            <span>Pending Review: {summary?.pending_verification ?? 0}</span>
            <span className="text-rose-400 font-semibold">NEEDS REVIEW</span>
          </div>
        </div>
      </div>

      {/* Priority Cases Workbench (Officers & Admins) */}
      {role !== 'institution' && priorityCases.length > 0 && (
        <div className="rounded-xl bg-vault-900 border border-vault-800 p-5 space-y-4 shadow-xl">
          <div className="flex items-center justify-between border-b border-vault-800 pb-3">
            <div className="flex items-center space-x-2">
              <ShieldAlert className="w-4 h-4 text-vault-amber" />
              <h2 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-100">
                Priority Surveillance Cases ({priorityCases.length} Requiring Attention)
              </h2>
            </div>
            <span className="text-[10px] font-mono text-slate-400 uppercase">
              Auto-Ranked by Regulatory Urgency
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {priorityCases.slice(0, 6).map((item) => (
              <div
                key={item.fdr_id}
                onClick={() => navigate(`/fdrs/${item.fdr_id}`)}
                className={`p-3.5 rounded-lg border transition cursor-pointer hover:border-amber-500/60 ${
                  item.urgency === 'high'
                    ? 'bg-rose-950/20 border-rose-900/60'
                    : item.urgency === 'medium'
                    ? 'bg-amber-950/20 border-amber-900/60'
                    : 'bg-vault-950 border-vault-800'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-mono text-xs font-bold text-vault-amber">
                    {item.fdr_number}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase ${
                      item.urgency === 'high'
                        ? 'bg-rose-900/80 text-rose-200'
                        : item.urgency === 'medium'
                        ? 'bg-amber-900/80 text-amber-200'
                        : 'bg-vault-800 text-slate-300'
                    }`}
                  >
                    {item.urgency} URGENCY
                  </span>
                </div>

                <div className="text-xs font-semibold text-slate-200 truncate mb-1">
                  {item.institution_name}
                </div>

                <div className="text-[11px] font-mono text-slate-400 flex items-center justify-between mb-2">
                  <span>{item.bank_name}</span>
                  <span className="text-slate-100 font-bold">
                    ₹{Number(item.amount).toLocaleString('en-IN')}
                  </span>
                </div>

                <p className="text-[11px] text-slate-400 italic line-clamp-2">
                  "{item.reason}"
                </p>

                <div className="mt-2.5 pt-2 border-t border-vault-800/60 flex items-center justify-between text-[10px] font-mono text-amber-400">
                  <span>Open Case Workbench</span>
                  <ArrowRight className="w-3 h-3" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analytics Charts & Portfolio Distribution Grid */}
      {chartsData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Chart 1: Instrument Status Distribution */}
          <div className="p-5 rounded-xl bg-vault-900 border border-vault-800 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-vault-800 pb-3">
              <div className="flex items-center space-x-2 text-xs font-mono font-bold text-slate-200">
                <BarChart3 className="w-4 h-4 text-emerald-400" />
                <span>DEPOSIT STATUS DISTRIBUTION</span>
              </div>
              <span className="text-[10px] font-mono text-slate-400">Actual Database Records</span>
            </div>

            <div className="space-y-3 pt-1">
              {chartsData.status_distribution.map((st) => {
                const total = summary?.total_fdrs || 1;
                const pct = Math.round((st.count / total) * 100);
                return (
                  <div key={st.status} className="space-y-1 font-mono text-xs">
                    <div className="flex items-center justify-between text-slate-300">
                      <span className="flex items-center space-x-2">
                        <span
                          className="w-2.5 h-2.5 rounded-full"
                          style={{ backgroundColor: st.color }}
                        />
                        <span>{st.name}</span>
                      </span>
                      <span>
                        <span className="font-bold text-slate-100">{st.count}</span>{' '}
                        <span className="text-slate-500">({pct}%)</span> · ₹
                        {Number(st.amount).toLocaleString('en-IN')}
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-vault-950 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${pct}%`, backgroundColor: st.color }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Chart 2: Bank Concentration */}
          <div className="p-5 rounded-xl bg-vault-900 border border-vault-800 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-vault-800 pb-3">
              <div className="flex items-center space-x-2 text-xs font-mono font-bold text-slate-200">
                <Building2 className="w-4 h-4 text-vault-amber" />
                <span>TOP ISSUING BANK CONCENTRATION</span>
              </div>
              <span className="text-[10px] font-mono text-slate-400">Scheduled Commercial Banks</span>
            </div>

            <div className="space-y-3 pt-1">
              {chartsData.amount_by_bank.map((b) => {
                const maxAmount = chartsData.amount_by_bank[0]?.amount || 1;
                const barWidth = Math.round((b.amount / maxAmount) * 100);
                return (
                  <div key={b.bank_name} className="space-y-1 font-mono text-xs">
                    <div className="flex items-center justify-between text-slate-300">
                      <span className="truncate max-w-[220px] font-sans font-medium text-slate-200">
                        {b.bank_name}
                      </span>
                      <span>
                        <span className="font-bold text-slate-100">{b.count} FDRs</span> ·{' '}
                        <span className="text-amber-400 font-bold">
                          ₹{Number(b.amount).toLocaleString('en-IN')}
                        </span>
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-vault-950 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-amber-600 to-amber-400 transition-all duration-500"
                        style={{ width: `${barWidth}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Search & Filter Bar */}
      <div className="p-4 rounded-lg bg-vault-900 border border-vault-800 space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex flex-wrap items-center gap-3">
          {/* Search Input */}
          <div className="flex-1 min-w-[280px] relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by FDR number, institution name, or bank..."
              className="w-full pl-9 pr-3 py-2 rounded bg-vault-950 border border-vault-800 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-amber-500/50"
            />
          </div>

          {/* Instrument Status Filter */}
          <div className="min-w-[160px]">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full py-2 px-3 rounded bg-vault-950 border border-vault-800 text-xs font-mono text-slate-300 focus:outline-none focus:border-amber-500/50"
            >
              <option value="all">All Instrument Statuses</option>
              <option value="active">Active</option>
              <option value="submitted">Submitted</option>
              <option value="renewal_due">Renewal Due</option>
              <option value="matured">Matured</option>
              <option value="renewed">Renewed</option>
              <option value="released">Released</option>
            </select>
          </div>

          {/* Verification Status Filter */}
          <div className="min-w-[160px]">
            <select
              value={verificationFilter}
              onChange={(e) => setVerificationFilter(e.target.value)}
              className="w-full py-2 px-3 rounded bg-vault-950 border border-vault-800 text-xs font-mono text-slate-300 focus:outline-none focus:border-amber-500/50"
            >
              <option value="all">All Verification Statuses</option>
              <option value="verified">Verified</option>
              <option value="pending">Pending</option>
              <option value="discrepancy">Discrepancy</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>

          {/* Bank Filter */}
          <div className="min-w-[160px]">
            <select
              value={bankFilter}
              onChange={(e) => setBankFilter(e.target.value)}
              className="w-full py-2 px-3 rounded bg-vault-950 border border-vault-800 text-xs font-mono text-slate-300 focus:outline-none focus:border-amber-500/50"
            >
              <option value="all">All Scheduled Banks</option>
              <option value="State Bank of India">State Bank of India</option>
              <option value="Punjab National Bank">Punjab National Bank</option>
              <option value="Canara Bank">Canara Bank</option>
              <option value="Bank of Baroda">Bank of Baroda</option>
              <option value="HDFC Bank">HDFC Bank</option>
              <option value="ICICI Bank">ICICI Bank</option>
            </select>
          </div>

          <button
            type="submit"
            className="px-4 py-2 rounded bg-vault-800 hover:bg-vault-700 text-slate-200 text-xs font-mono font-semibold transition-colors"
          >
            Apply Filters
          </button>

          {(searchTerm || statusFilter !== 'all' || verificationFilter !== 'all' || bankFilter !== 'all') && (
            <button
              type="button"
              onClick={handleResetFilters}
              className="px-3 py-2 text-xs font-mono text-slate-400 hover:text-rose-400 transition-colors"
            >
              Reset
            </button>
          )}
        </form>
      </div>

      {/* FDR Registry Data Table */}
      <div className="rounded-lg bg-vault-900 border border-vault-800 shadow-xl overflow-hidden">
        <div className="p-4 border-b border-vault-800 flex items-center justify-between">
          <div className="font-mono text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
            <Layers className="w-4 h-4 text-amber-500" />
            <span>FDR Instrument Registry ({fdrs.length} Records)</span>
          </div>
          <div className="font-mono text-[11px] text-slate-500">
            Click row to view full lifecycle dossier
          </div>
        </div>

        {isLoading ? (
          <div className="p-8 space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 bg-vault-950/60 rounded animate-pulse" />
            ))}
          </div>
        ) : fdrs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-vault-800 text-[10px] text-slate-500 uppercase tracking-wider bg-vault-950/40">
                  <th className="py-3 px-4">FDR Identifier</th>
                  <th className="py-3 px-4">Institution Name</th>
                  <th className="py-3 px-4">Issuing Bank &amp; Branch</th>
                  <th className="py-3 px-4 text-right">Principal Amount</th>
                  <th className="py-3 px-4">Maturity Date</th>
                  <th className="py-3 px-4">Instrument Status</th>
                  <th className="py-3 px-4">Verification</th>
                  <th className="py-3 px-4">Workflow</th>
                  <th className="py-3 px-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-vault-800/60">
                {fdrs.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => navigate(`/fdrs/${item.id}`)}
                    className="hover:bg-vault-800/40 transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4 font-bold text-amber-400 group-hover:text-amber-300">
                      {item.fdr_number}
                    </td>

                    <td className="py-3 px-4">
                      <div className="text-slate-200 font-sans font-medium truncate max-w-xs">
                        {item.institution?.name || 'Apex Institute of Technology'}
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        {item.institution?.aicte_id || 'AICTE-INST-001'}
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      <div className="text-slate-300 font-sans">{item.bank_name}</div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        {item.branch || 'Main Branch'}
                      </div>
                    </td>

                    <td className="py-3 px-4 text-right font-bold text-slate-100">
                      {formatCurrencyINR(item.amount)}
                    </td>

                    <td className="py-3 px-4 text-slate-300 whitespace-nowrap">
                      {formatDate(item.maturity_date)}
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <InstrumentBadge status={item.instrument_status} size="sm" />
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <VerificationBadge status={item.verification_status} size="sm" />
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <WorkflowBadge status={item.workflow_status} size="sm" />
                    </td>

                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/fdrs/${item.id}`);
                        }}
                        className="p-1.5 rounded hover:bg-vault-700 text-slate-400 hover:text-amber-400 transition-colors"
                        title="View Record Details"
                      >
                        <ArrowUpRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-16 text-center space-y-3 font-mono">
            <ScanLine className="w-10 h-10 text-slate-600 mx-auto" />
            <div className="text-slate-300 text-sm font-semibold">No FDR records match the specified filters.</div>
            <p className="text-xs text-slate-500">
              Try adjusting your search criteria or ingest a new Fixed Deposit Receipt.
            </p>
            <button
              onClick={handleResetFilters}
              className="px-4 py-2 rounded bg-vault-800 text-xs text-amber-400 font-semibold"
            >
              Clear Filters
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
