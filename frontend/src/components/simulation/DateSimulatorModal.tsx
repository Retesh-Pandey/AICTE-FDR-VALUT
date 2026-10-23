import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { api, SimulationStatus } from '@/lib/api';
import { Clock, RotateCcw, AlertTriangle, CheckCircle, X } from 'lucide-react';

interface DateSimulatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSimulateSuccess?: () => void;
}

export const DateSimulatorModal: React.FC<DateSimulatorModalProps> = ({
  isOpen,
  onClose,
  onSimulateSuccess,
}) => {
  const [status, setStatus] = useState<SimulationStatus | null>(null);
  const [customDate, setCustomDate] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [lastResult, setLastResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const data = await api.getSimulatedDate();
      setStatus(data);
    } catch {
      // Ignore background error
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
      setLastResult(null);
      setError(null);

      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') onClose();
      };
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, onClose]);

  const handleSimulate = async (payload: { offset_days?: number; target_date?: string; reset?: boolean }) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.simulateDate(payload);
      setLastResult(res.results);
      await fetchStatus();
      if (onSimulateSuccess) {
        onSimulateSuccess();
      }
    } catch (err: any) {
      setError(err?.error?.message || 'Failed to update simulated date.');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return createPortal(
    <div
      onClick={onClose}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-[#0b0e14] border border-vault-700 w-full max-w-lg rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95"
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-vault-800 flex items-center justify-between bg-vault-900/60">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-100 flex items-center space-x-2">
                <span>Hackathon Maturity &amp; Reminder Simulator</span>
                <span className="px-1.5 py-0.5 rounded bg-amber-950 text-amber-400 border border-amber-800 text-[10px] font-mono">
                  DEMO ENV
                </span>
              </h3>
              <p className="text-[11px] text-slate-400">
                Shift the effective date forward to demonstrate automated maturity checks and reminder alerts in real-time.
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1 rounded hover:bg-vault-800">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Current State Indicator */}
        <div className="p-5 space-y-5">
          <div className="p-3 rounded-lg bg-vault-950 border border-vault-800 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase font-mono text-slate-400">Effective Evaluation Date:</div>
              <div className="text-base font-bold text-amber-400 font-mono mt-0.5">
                {status?.effective_date || 'Loading...'}
              </div>
            </div>
            <div>
              {status?.is_simulated ? (
                <span className="px-2.5 py-1 rounded bg-amber-950 border border-amber-700 text-amber-300 font-mono text-xs font-semibold flex items-center space-x-1">
                  <span>SIMULATED OFFSET ACTIVE</span>
                </span>
              ) : (
                <span className="px-2.5 py-1 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 font-mono text-xs font-semibold flex items-center space-x-1">
                  <CheckCircle className="w-3.5 h-3.5" />
                  <span>REAL SYSTEM DATE</span>
                </span>
              )}
            </div>
          </div>

          {/* Quick Offset Buttons */}
          <div>
            <div className="text-xs font-semibold text-slate-300 mb-2">Fast Forward Scenarios:</div>
            <div className="grid grid-cols-3 gap-2.5">
              <button
                disabled={isLoading}
                onClick={() => handleSimulate({ offset_days: 15 })}
                className="p-2.5 rounded bg-vault-900 hover:bg-vault-800 border border-vault-700 hover:border-amber-500/50 text-left transition disabled:opacity-50"
              >
                <div className="font-bold text-xs text-amber-300 font-mono">+15 Days</div>
                <div className="text-[10px] text-slate-400 mt-0.5 leading-tight">
                  Trigger 15-day renewal warnings
                </div>
              </button>

              <button
                disabled={isLoading}
                onClick={() => handleSimulate({ offset_days: 30 })}
                className="p-2.5 rounded bg-vault-900 hover:bg-vault-800 border border-vault-700 hover:border-amber-500/50 text-left transition disabled:opacity-50"
              >
                <div className="font-bold text-xs text-amber-300 font-mono">+30 Days</div>
                <div className="text-[10px] text-slate-400 mt-0.5 leading-tight">
                  Trigger 30-day reminder notices
                </div>
              </button>

              <button
                disabled={isLoading}
                onClick={() => handleSimulate({ offset_days: 65 })}
                className="p-2.5 rounded bg-vault-900 hover:bg-vault-800 border border-vault-700 hover:border-amber-500/50 text-left transition disabled:opacity-50"
              >
                <div className="font-bold text-xs text-rose-300 font-mono">+65 Days</div>
                <div className="text-[10px] text-slate-400 mt-0.5 leading-tight">
                  Trigger critical expiries &amp; matured state
                </div>
              </button>
            </div>
          </div>

          {/* Custom Date Input */}
          <div className="p-3 rounded bg-vault-900/40 border border-vault-800/80 space-y-2">
            <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
              <span>Set Custom Target Date:</span>
              <span className="text-[10px] text-slate-400 font-mono">YYYY-MM-DD</span>
            </label>
            <div className="flex space-x-2">
              <input
                type="date"
                value={customDate}
                onChange={(e) => setCustomDate(e.target.value)}
                className="flex-1 px-3 py-1.5 rounded bg-vault-950 border border-vault-700 text-xs text-slate-200 font-mono focus:border-amber-500 focus:outline-none"
              />
              <button
                disabled={!customDate || isLoading}
                onClick={() => handleSimulate({ target_date: customDate })}
                className="px-3 py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-slate-950 text-xs font-bold transition disabled:opacity-50"
              >
                Apply
              </button>
            </div>
          </div>

          {/* Results Feedback */}
          {lastResult && (
            <div className="p-3 rounded bg-emerald-950/40 border border-emerald-800/60 text-xs text-emerald-200 space-y-1 font-mono">
              <div className="font-bold text-emerald-300 flex items-center space-x-1.5">
                <CheckCircle className="w-3.5 h-3.5" />
                <span>Maturity Job Evaluated for {lastResult.evaluated_date}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 pt-1 text-[11px]">
                <div>Active Checked: <span className="font-bold text-white">{lastResult.total_active_evaluated}</span></div>
                <div>Alerts Generated: <span className="font-bold text-white">{lastResult.notifications_created}</span></div>
                <div>Marked Renewal Due: <span className="font-bold text-amber-300">{lastResult.marked_renewal_due}</span></div>
                <div>Marked Matured: <span className="font-bold text-rose-300">{lastResult.marked_matured}</span></div>
              </div>
            </div>
          )}

          {error && (
            <div className="p-3 rounded bg-rose-950/40 border border-rose-800 text-xs text-rose-200 flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-vault-800 bg-vault-950 flex items-center justify-between">
          <button
            disabled={isLoading || !status?.is_simulated}
            onClick={() => handleSimulate({ reset: true })}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded bg-vault-900 hover:bg-vault-800 border border-vault-700 text-xs text-slate-300 hover:text-white transition disabled:opacity-40"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset to Real Date</span>
          </button>

          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded bg-vault-800 hover:bg-vault-700 text-xs text-slate-200 transition font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};
