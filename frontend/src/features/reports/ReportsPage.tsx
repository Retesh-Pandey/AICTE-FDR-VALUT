import React, { useState, useEffect } from 'react';
import { api, ReportSummaryResponse } from '@/lib/api';
import { InstrumentBadge, VerificationBadge, WorkflowBadge } from '@/components/common/StatusBadges';
import {
  FileSpreadsheet,
  Download,
  Filter,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';

export const ReportsPage: React.FC = () => {
  const [reportType, setReportType] = useState<string>('all');
  const [data, setData] = useState<ReportSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  const fetchReport = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.getReportData(reportType);
      setData(res);
    } catch (err: any) {
      setError(err?.error?.message || 'Failed to generate report dataset.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [reportType]);

  const handleDownload = async (format: 'xlsx' | 'csv' = 'xlsx') => {
    setIsExporting(true);
    setExportNotice(null);
    try {
      await api.downloadReportExcel(reportType, format);
      setExportNotice(`AICTE ${format.toUpperCase()} export '${reportType.toUpperCase()}' generated and downloaded successfully.`);
    } catch (err: any) {
      setError(err?.message || `Failed to download ${format.toUpperCase()} file. Please try again.`);
    } finally {
      setIsExporting(false);
    }
  };

  const filterTabs = [
    { id: 'all', label: 'All Deposits' },
    { id: 'active', label: 'Active Vault Balance' },
    { id: 'expiring', label: 'Expiring (≤ 30 Days)' },
    { id: 'pending', label: 'Pending Verification' },
    { id: 'renewed', label: 'Renewed Instruments' },
    { id: 'released', label: 'Released Deposits' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Title & Actions */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-vault-amber mb-1">
            <FileSpreadsheet className="w-4 h-4" />
            <span>SOVEREIGN REGULATORY REPORTING ENGINE</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">
            Compliance Registers &amp; Excel Exports
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Official AICTE security deposit registries formatted in Excel (.xlsx) and CSV (.csv) with Indian number standards and generation metadata.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchReport}
            disabled={isLoading}
            className="flex items-center space-x-1.5 px-3 py-2 rounded bg-vault-900 hover:bg-vault-850 border border-vault-700 text-xs font-mono text-slate-300 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => handleDownload('csv')}
            disabled={isExporting || isLoading}
            className="flex items-center space-x-1.5 px-3 py-2 rounded bg-vault-900 hover:bg-vault-850 border border-vault-700 text-xs font-mono text-slate-300 transition"
            title="Download formatted CSV file"
          >
            <Download className="w-3.5 h-3.5 text-vault-amber" />
            <span>CSV</span>
          </button>

          <button
            onClick={() => handleDownload('xlsx')}
            disabled={isExporting || isLoading}
            className="flex items-center space-x-2 px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-slate-950 text-xs font-bold font-mono transition shadow-lg shadow-emerald-600/20"
            title="Download styled Excel workbook"
          >
            <Download className="w-4 h-4" />
            <span>{isExporting ? 'GENERATING...' : 'DOWNLOAD EXCEL (.XLSX)'}</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {exportNotice && (
        <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800 text-xs text-emerald-300 font-mono flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{exportNotice}</span>
        </div>
      )}

      {error && (
        <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800 text-xs text-rose-300 font-mono flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Filter Tabs & Telemetry Metrics */}
      <div className="p-4 rounded-xl bg-vault-900 border border-vault-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          {/* Filter Pills */}
          <div className="flex flex-wrap items-center gap-1.5" role="tablist" aria-label="Report Filter Scope">
            <span className="text-xs text-slate-400 font-mono mr-1 flex items-center space-x-1">
              <Filter className="w-3.5 h-3.5 text-vault-amber" />
              <span>Scope:</span>
            </span>
            {filterTabs.map((tab) => (
              <button
                key={tab.id}
                role="tab"
                aria-selected={reportType === tab.id}
                onClick={() => setReportType(tab.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono transition ${
                  reportType === tab.id
                    ? 'bg-vault-amber text-slate-950 font-bold shadow-md shadow-amber-500/20'
                    : 'bg-vault-950 hover:bg-vault-850 text-slate-300 border border-vault-800'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Quick Stats */}
          {data && (
            <div className="flex items-center space-x-4 text-xs font-mono bg-vault-950 px-3.5 py-1.5 rounded-lg border border-vault-800">
              <div className="text-slate-400">
                Count: <span className="font-bold text-slate-100">{data.total_records}</span>
              </div>
              <div className="h-3 w-px bg-vault-800" />
              <div className="text-slate-400">
                Total Principal:{' '}
                <span className="font-bold text-emerald-400">
                  ₹{Number(data.total_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Report Data Preview Table */}
      <div className="rounded-xl bg-vault-900 border border-vault-800 overflow-hidden shadow-xl">
        <div className="p-4 border-b border-vault-800/80 flex items-center justify-between">
          <div className="text-xs font-mono uppercase font-bold text-slate-300">
            Live Preview: {reportType.toUpperCase()} DATASET ({data?.total_records || 0} RECORDS)
          </div>
          <div className="text-[10px] font-mono text-slate-500">
            Actual Application Data · OpenPyXL Styled Engine
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr className="border-b border-vault-800 text-[10px] text-slate-400 uppercase bg-vault-950/60">
                <th className="py-3 px-4">FDR Number</th>
                <th className="py-3 px-4">Institution Name</th>
                <th className="py-3 px-4">Issuing Bank &amp; Branch</th>
                <th className="py-3 px-4 text-right">Principal Amount</th>
                <th className="py-3 px-4">Maturity Date</th>
                <th className="py-3 px-4">Instrument Status</th>
                <th className="py-3 px-4">Verification</th>
                <th className="py-3 px-4">Workflow Stage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-vault-800/60">
              {isLoading && (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-xs text-slate-500 font-mono">
                    Generating report preview from database...
                  </td>
                </tr>
              )}

              {!isLoading && (!data || data.records.length === 0) && (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500 font-mono">
                    No FDR records match the '{reportType.toUpperCase()}' criteria.
                  </td>
                </tr>
              )}

              {!isLoading &&
                data &&
                data.records.map((rec, idx) => (
                  <tr
                    key={idx}
                    onClick={() => {
                      // Navigate if matched fdr
                    }}
                    className="hover:bg-vault-850/50 transition-colors"
                  >
                    <td className="py-3 px-4 font-bold text-vault-amber">
                      {rec.fdr_number}
                    </td>

                    <td className="py-3 px-4">
                      <div className="text-slate-200 font-sans font-semibold text-xs truncate max-w-xs">
                        {rec.institution_name}
                      </div>
                      <div className="text-[10px] text-slate-500">{rec.institution_code}</div>
                    </td>

                    <td className="py-3 px-4">
                      <div className="text-slate-300 font-sans">{rec.bank_name}</div>
                      <div className="text-[10px] text-slate-500">{rec.branch}</div>
                    </td>

                    <td className="py-3 px-4 text-right font-bold text-slate-100">
                      {rec.amount_formatted}
                    </td>

                    <td className="py-3 px-4 text-slate-300 whitespace-nowrap">
                      {rec.maturity_date || 'N/A'}
                    </td>

                    <td className="py-3 px-4">
                      <InstrumentBadge status={rec.instrument_status as any} />
                    </td>

                    <td className="py-3 px-4">
                      <VerificationBadge status={rec.verification_status as any} />
                    </td>

                    <td className="py-3 px-4">
                      <WorkflowBadge status={rec.workflow_status as any} />
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
