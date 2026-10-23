import React, { useState, useEffect, useCallback } from 'react';
import { api, ChainVerificationResult, AuditLogEntry } from '@/lib/api';
import { useAuth } from '@/features/auth/AuthContext';
import { formatDate } from '@/lib/utils';
import {
  FileCheck2,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Search,
  Lock,
  CheckCircle2,
  Shield,
  Layers,
  Clock,
  Copy,
  Check,
  AlertOctagon,
  Info,
} from 'lucide-react';

export const AuditLedgerPage: React.FC = () => {
  const { role } = useAuth();
  const isAdmin = role === 'admin';

  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [isLoadingLogs, setIsLoadingLogs] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');

  // Verification state
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<ChainVerificationResult | null>(null);
  const [verifyError, setVerifyError] = useState<{
    code?: string;
    message: string;
    details?: any;
  } | null>(null);
  const [isPreviousResult, setIsPreviousResult] = useState(false);
  const [copiedHeadHash, setCopiedHeadHash] = useState(false);

  const fetchAuditData = useCallback(async () => {
    setIsLoadingLogs(true);
    try {
      try {
        const fetchedLogs = await api.getAuditLogs(100);
        setLogs(fetchedLogs);
      } catch {
        // Fallback to FDR audit trails if direct logs query fails
        const fdrsData = await api.listFDRs({ limit: 10 });
        let combinedLogs: AuditLogEntry[] = [];
        for (const fdr of fdrsData.items.slice(0, 5)) {
          try {
            const l = await api.getFDRAudit(fdr.id);
            combinedLogs = [...combinedLogs, ...l];
          } catch {
            // ignore individual FDR audit lookup failure
          }
        }
        const uniqueMap = new Map<number, AuditLogEntry>();
        combinedLogs.forEach((item) => uniqueMap.set(item.id, item));
        const sorted = Array.from(uniqueMap.values()).sort((a, b) => b.id - a.id);
        setLogs(sorted);
      }
    } catch (err: any) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setIsLoadingLogs(false);
    }
  }, []);

  useEffect(() => {
    fetchAuditData();
  }, [fetchAuditData]);

  const handleManualVerify = async () => {
    if (!isAdmin) {
      setVerifyError({
        code: 'FORBIDDEN_ROLE',
        message: `Admin access required: Only Sovereign Administrators can execute cryptographic chain integrity verification. Current role: "${role || 'unauthenticated'}".`,
      });
      return;
    }

    setIsVerifying(true);
    setVerifyError(null);

    try {
      const result = await api.verifyAuditChain();
      setVerifyResult(result);
      setVerifyError(null);
      setIsPreviousResult(false);

      // Refresh displayed ledger information from the server after verification
      await fetchAuditData();
    } catch (err: any) {
      let message = 'Verification request failed due to an unexpected network or server error.';
      let code = 'VERIFICATION_ERROR';

      if (err?.error?.message) {
        message = err.error.message;
        code = err.error.code || 'API_ERROR';
      } else if (err?.message) {
        message = err.message;
      }

      if (err?.status === 401 || err?.error?.code === 'NOT_AUTHENTICATED' || err?.error?.code === 'INVALID_TOKEN') {
        message = 'Your session has expired or authentication token is missing. Please sign in again as an Administrator.';
        code = 'UNAUTHORIZED';
      } else if (err?.status === 403 || err?.error?.code === 'FORBIDDEN_ROLE') {
        message = 'Admin access required: Only Sovereign Administrators have authorization to verify cryptographic chain integrity.';
        code = 'FORBIDDEN';
      }

      setVerifyError({
        code,
        message,
        details: err?.error?.details || (err?.statusText ? `${err.status} ${err.statusText}` : undefined),
      });

      // Keep previous result visible only if clearly marked as previous/stale
      if (verifyResult) {
        setIsPreviousResult(true);
      }
    } finally {
      setIsVerifying(false);
    }
  };

  const copyHeadHash = (hash: string) => {
    if (!hash) return;
    navigator.clipboard.writeText(hash);
    setCopiedHeadHash(true);
    setTimeout(() => setCopiedHeadHash(false), 2000);
  };

  const filteredLogs = logs.filter((log) => {
    const matchesSearch =
      !searchQuery ||
      log.action?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.remarks?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.row_hash?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesRole = roleFilter === 'all' || log.actor_role === roleFilter;

    return matchesSearch && matchesRole;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-vault-amber mb-1">
            <Lock className="w-4 h-4" />
            <span>CRYPTOGRAPHIC LEDGER &amp; SHA-256 TAMPER-EVIDENT AUDIT</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">
            Hash Audit Ledger &amp; Parity Verification
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Every administrative mutation, discrepancy resolution, and workflow progression is sealed into an append-only hash chain with tamper detection.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-2">
          {!isAdmin && (
            <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-mono">
              <Lock className="w-3.5 h-3.5 shrink-0" />
              <span>Admin access required</span>
            </div>
          )}

          <button
            id="btn-verify-audit-integrity"
            onClick={handleManualVerify}
            disabled={isVerifying || !isAdmin}
            title={!isAdmin ? 'Admin access required to verify audit chain integrity' : 'Verify SHA-256 hash-chain integrity'}
            className={`flex items-center space-x-2 px-4 py-2.5 rounded-lg font-mono font-bold text-xs transition shadow-lg ${
              !isAdmin
                ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed'
                : 'bg-vault-amber hover:bg-amber-400 text-slate-950 shadow-amber-500/20 active:scale-95'
            } disabled:opacity-50`}
          >
            <ShieldCheck className={`w-4 h-4 ${isVerifying ? 'animate-spin' : ''}`} />
            <span>{isVerifying ? 'CALCULATING HASH INTEGRITY...' : 'VERIFY AUDIT INTEGRITY'}</span>
          </button>
        </div>
      </div>

      {/* Verification Error Alert */}
      {verifyError && (
        <div className="p-4 rounded-xl border border-rose-800/80 bg-rose-950/70 text-rose-200 font-mono flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-lg shadow-rose-950/40 animate-in fade-in duration-200">
          <div className="flex items-start space-x-3">
            <AlertOctagon className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-rose-300">
                Verification Failed: {verifyError.code || 'REQUEST_FAILED'}
              </div>
              <div className="text-xs text-rose-200 mt-1 font-sans">
                {verifyError.message}
              </div>
              {verifyError.details && (
                <div className="text-[11px] text-rose-400 mt-1 font-mono">
                  Details: {typeof verifyError.details === 'object' ? JSON.stringify(verifyError.details) : String(verifyError.details)}
                </div>
              )}
            </div>
          </div>
          {isAdmin && (
            <button
              onClick={handleManualVerify}
              disabled={isVerifying}
              className="px-3 py-1.5 rounded-lg bg-rose-900/60 hover:bg-rose-800 text-rose-100 text-xs font-mono font-semibold transition border border-rose-700 self-start md:self-auto shrink-0"
            >
              Retry Verification
            </button>
          )}
        </div>
      )}

      {/* Sovereign Verification Result Card */}
      {verifyResult && (
        <div
          className={`p-4 rounded-xl border flex flex-col gap-3 font-mono shadow-xl transition-all ${
            verifyResult.valid
              ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300'
              : 'bg-rose-950/70 border-rose-800 text-rose-300'
          }`}
        >
          {/* Header row */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex items-start md:items-center space-x-3">
              {verifyResult.valid ? (
                <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0 mt-0.5 md:mt-0" />
              ) : (
                <AlertTriangle className="w-6 h-6 text-rose-400 shrink-0 mt-0.5 md:mt-0" />
              )}
              <div>
                <div className="flex items-center space-x-2">
                  <div className="text-sm font-bold uppercase tracking-wide">
                    {verifyResult.valid
                      ? 'SHA-256 CHAIN PARITY VERIFIED — ZERO ANOMALIES DETECTED'
                      : `INTEGRITY COMPROMISED — CORRUPTED BLOCK DETECTED AT #${verifyResult.broken_at}`}
                  </div>
                  {isPreviousResult && (
                    <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold uppercase">
                      Previous Check
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-300 mt-1 font-sans">
                  {verifyResult.message || (
                    verifyResult.valid
                      ? `All ${verifyResult.total_blocks} chained audit blocks validated mathematically against cryptographic predecessor hashes and row digests.`
                      : `An unauthorized modification or hash mismatch was detected at block #${verifyResult.broken_at}. Review is required.`
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2 self-start md:self-auto">
              <div className="text-[11px] px-3 py-1.5 rounded bg-black/40 border border-current font-bold">
                {verifyResult.valid ? 'STATUS: VALID' : 'STATUS: TAMPERED'}
              </div>
            </div>
          </div>

          {/* Telemetry info sub-bar */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 pt-2 border-t border-current/20 text-xs">
            <div className="flex items-center space-x-1.5 text-slate-400">
              <Layers className="w-3.5 h-3.5 text-current shrink-0" />
              <span>Blocks Checked:</span>
              <span className="font-bold text-slate-100">{verifyResult.total_blocks}</span>
            </div>

            {verifyResult.broken_at !== null && (
              <div className="flex items-center space-x-1.5 text-rose-300 font-bold">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                <span>Broken Block:</span>
                <span className="underline">#{verifyResult.broken_at}</span>
              </div>
            )}

            {verifyResult.verification_time_ms !== undefined && verifyResult.verification_time_ms !== null && (
              <div className="flex items-center space-x-1.5 text-slate-400">
                <Clock className="w-3.5 h-3.5 text-current shrink-0" />
                <span>Computation:</span>
                <span className="font-bold text-slate-100">{verifyResult.verification_time_ms} ms</span>
              </div>
            )}

            {verifyResult.verified_at && (
              <div className="flex items-center space-x-1.5 text-slate-400">
                <Clock className="w-3.5 h-3.5 text-current shrink-0" />
                <span>Timestamp:</span>
                <span className="font-bold text-slate-100">{formatDate(verifyResult.verified_at)}</span>
              </div>
            )}

            {verifyResult.head_hash && (
              <div className="sm:col-span-2 md:col-span-4 flex items-center space-x-2 pt-1 text-[11px] text-slate-400">
                <span className="shrink-0 font-bold text-slate-300">Head Block Hash:</span>
                <span className="font-mono text-amber-400 truncate select-all">{verifyResult.head_hash}</span>
                <button
                  onClick={() => copyHeadHash(verifyResult.head_hash!)}
                  className="p-1 rounded bg-black/40 hover:bg-black/60 text-slate-300 hover:text-white transition shrink-0"
                  title="Copy SHA-256 Head Hash"
                >
                  {copiedHeadHash ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Standby Banner if not yet verified */}
      {!verifyResult && !verifyError && !isVerifying && (
        <div className="p-4 rounded-xl border border-vault-800 bg-vault-900/60 font-mono text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-slate-400">
          <div className="flex items-center space-x-3">
            <Info className="w-5 h-5 text-vault-amber shrink-0" />
            <div>
              <span className="font-bold text-slate-200">Cryptographic Hash-Chain Verification Standby.</span>
              <p className="text-[11px] text-slate-400 mt-0.5 font-sans">
                Click &ldquo;VERIFY AUDIT INTEGRITY&rdquo; to recompute SHA-256 row hashes and predecessor links across the audit ledger.
              </p>
            </div>
          </div>
          <div className="text-[10px] text-slate-500 uppercase px-2 py-1 rounded bg-vault-950 border border-vault-800 shrink-0">
            Awaiting Calculation
          </div>
        </div>
      )}

      {/* Telemetry Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-vault-900 border border-vault-800">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-2">
            <span>Total Ledger Blocks</span>
            <Layers className="w-4 h-4 text-vault-amber" />
          </div>
          <div className="text-2xl font-bold font-mono text-slate-100">
            {verifyResult?.total_blocks ?? logs.length}
          </div>
          <div className="text-[10px] font-mono text-slate-500 mt-1">Cryptographic Blocks</div>
        </div>

        <div className="p-4 rounded-xl bg-vault-900 border border-vault-800">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-2">
            <span>Hash Algorithm</span>
            <Lock className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold font-mono text-emerald-400">SHA-256</div>
          <div className="text-[10px] font-mono text-slate-500 mt-1">Chained Predecessor Links</div>
        </div>

        <div className="p-4 rounded-xl bg-vault-900 border border-vault-800">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-2">
            <span>Mutation Enforcement</span>
            <Shield className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-xl font-bold font-mono text-purple-400">APPEND-ONLY</div>
          <div className="text-[10px] font-mono text-slate-500 mt-1">Tamper-evident hash chain</div>
        </div>

        <div className="p-4 rounded-xl bg-vault-900 border border-vault-800">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-2">
            <span>Transactional Consistency</span>
            <FileCheck2 className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-xl font-bold font-mono text-cyan-400">ACID PARITY</div>
          <div className="text-[10px] font-mono text-slate-500 mt-1">Atomic with State Changes</div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 rounded-xl bg-vault-900 border border-vault-800 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs font-mono">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search audit actions, remarks, or SHA-256 hashes..."
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-vault-950 border border-vault-700 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500"
          />
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-slate-400">Filter Actor:</span>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="px-3 py-2 rounded-lg bg-vault-950 border border-vault-700 text-slate-200 focus:outline-none focus:border-amber-500"
          >
            <option value="all">All Roles</option>
            <option value="admin">Administrator</option>
            <option value="officer">AICTE Officer</option>
            <option value="institution">Institution</option>
          </select>

          <button
            onClick={fetchAuditData}
            disabled={isLoadingLogs}
            title="Refresh Ledger"
            className="p-2 rounded-lg bg-vault-950 border border-vault-700 text-slate-300 hover:text-white transition"
          >
            <RefreshCw className={`w-4 h-4 ${isLoadingLogs ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Audit Blocks Table */}
      <div className="rounded-xl bg-vault-900 border border-vault-800 overflow-hidden shadow-xl">
        <div className="p-4 border-b border-vault-800/80 flex items-center justify-between font-mono text-xs">
          <div className="font-bold text-slate-200 uppercase">
            Audit Ledger Trail ({filteredLogs.length} Blocks Shown)
          </div>
          <div className="text-[10px] text-vault-emerald">
            SEQUENTIAL CRYPTOGRAPHIC LEDGER
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-vault-800 text-[10px] text-slate-400 uppercase bg-vault-950/60">
                <th className="py-3 px-4">Block #</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Actor Role</th>
                <th className="py-3 px-4">Transition</th>
                <th className="py-3 px-4">Remarks / Rationale</th>
                <th className="py-3 px-4">SHA-256 Digest</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-vault-800/60">
              {isLoadingLogs && (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-xs text-slate-500 font-mono">
                    Querying cryptographic ledger...
                  </td>
                </tr>
              )}

              {!isLoadingLogs && filteredLogs.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-xs text-slate-500 font-mono">
                    No audit records match the current search filter.
                  </td>
                </tr>
              )}

              {!isLoadingLogs &&
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-vault-850/50 transition-colors">
                    <td className="py-3 px-4 font-bold text-vault-amber">
                      #{log.id}
                    </td>

                    <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                      {formatDate(log.created_at)}
                    </td>

                    <td className="py-3 px-4 font-semibold text-slate-200">
                      {log.action}
                    </td>

                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-vault-950 border border-vault-700 text-cyan-400 text-[10px] uppercase font-bold">
                        {log.actor_role || 'system'}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-slate-300">
                      {log.old_status || log.new_status ? (
                        <div className="flex items-center space-x-1.5 text-[11px]">
                          <span className="text-slate-500">{log.old_status || 'start'}</span>
                          <span className="text-amber-500">&rarr;</span>
                          <span className="text-emerald-400 font-bold">{log.new_status}</span>
                        </div>
                      ) : (
                        <span className="text-slate-500">-</span>
                      )}
                    </td>

                    <td className="py-3 px-4 text-slate-300 max-w-xs truncate">
                      {log.remarks || '-'}
                    </td>

                    <td className="py-3 px-4 text-[10px] text-slate-400">
                      <div className="flex items-center space-x-1 font-mono">
                        <span className="text-amber-500/80">{log.row_hash?.slice(0, 14)}...</span>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
