import React from 'react';
import { ShieldCheck, Clock, AlertTriangle, XCircle, CheckCircle2 } from 'lucide-react';
import { InstrumentStatus, VerificationStatus, WorkflowStatus } from '@/lib/api';

export const InstrumentBadge: React.FC<{ status: InstrumentStatus; size?: 'sm' | 'md' }> = ({
  status,
  size = 'md',
}) => {
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';

  switch (status) {
    case 'active':
      return (
        <span
          className={`inline-flex items-center font-mono font-medium rounded border bg-emerald-500/10 text-emerald-400 border-emerald-500/30 ${sizeClasses}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
          ACTIVE
        </span>
      );
    case 'submitted':
      return (
        <span
          className={`inline-flex items-center font-mono font-medium rounded border bg-amber-500/10 text-amber-400 border-amber-500/30 ${sizeClasses}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5" />
          SUBMITTED
        </span>
      );
    case 'renewal_due':
      return (
        <span
          className={`inline-flex items-center font-mono font-medium rounded border bg-orange-500/10 text-orange-400 border-orange-500/30 ${sizeClasses}`}
        >
          <Clock className="w-3 h-3 mr-1 text-orange-400" />
          RENEWAL DUE
        </span>
      );
    case 'matured':
      return (
        <span
          className={`inline-flex items-center font-mono font-medium rounded border bg-purple-500/10 text-purple-400 border-purple-500/30 ${sizeClasses}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-purple-400 mr-1.5" />
          MATURED
        </span>
      );
    case 'renewed':
      return (
        <span
          className={`inline-flex items-center font-mono font-medium rounded border bg-blue-500/10 text-blue-400 border-blue-500/30 ${sizeClasses}`}
        >
          <CheckCircle2 className="w-3 h-3 mr-1 text-blue-400" />
          RENEWED
        </span>
      );
    case 'released':
      return (
        <span
          className={`inline-flex items-center font-mono font-medium rounded border bg-slate-500/10 text-slate-400 border-slate-500/30 ${sizeClasses}`}
        >
          RELEASED
        </span>
      );
    default:
      return (
        <span
          className={`inline-flex items-center font-mono font-medium rounded border bg-slate-800 text-slate-400 border-slate-700 ${sizeClasses}`}
        >
          {status}
        </span>
      );
  }
};

export const VerificationBadge: React.FC<{
  status: VerificationStatus;
  source?: string;
  size?: 'sm' | 'md';
}> = ({ status, source, size = 'md' }) => {
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';

  return (
    <span className="inline-flex items-center space-x-1.5">
      {status === 'verified' && (
        <span
          className={`inline-flex items-center font-mono font-medium rounded border bg-emerald-500/10 text-emerald-400 border-emerald-500/30 ${sizeClasses}`}
        >
          <ShieldCheck className="w-3 h-3 mr-1 text-emerald-400" />
          VERIFIED
        </span>
      )}
      {status === 'pending' && (
        <span
          className={`inline-flex items-center font-mono font-medium rounded border bg-amber-500/10 text-amber-400 border-amber-500/30 ${sizeClasses}`}
        >
          <Clock className="w-3 h-3 mr-1 text-amber-400 animate-spin" />
          PENDING
        </span>
      )}
      {status === 'discrepancy' && (
        <span
          className={`inline-flex items-center font-mono font-semibold rounded border bg-rose-500/10 text-rose-400 border-rose-500/40 shadow-sm shadow-rose-500/10 ${sizeClasses}`}
        >
          <AlertTriangle className="w-3 h-3 mr-1 text-rose-400" />
          DISCREPANCY
        </span>
      )}
      {status === 'rejected' && (
        <span
          className={`inline-flex items-center font-mono font-medium rounded border bg-red-500/10 text-red-400 border-red-500/30 ${sizeClasses}`}
        >
          <XCircle className="w-3 h-3 mr-1 text-red-400" />
          REJECTED
        </span>
      )}

      {source === 'SIMULATED_BANK' && (
        <span className="font-mono text-[9px] px-1 py-0.2 rounded bg-slate-800 border border-slate-700 text-slate-400">
          SIMULATED
        </span>
      )}
    </span>
  );
};

export const WorkflowBadge: React.FC<{ status: WorkflowStatus; size?: 'sm' | 'md' }> = ({
  status,
  size = 'md',
}) => {
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-[11px]';

  if (status === 'none') {
    return <span className="font-mono text-xs text-slate-500">None</span>;
  }

  const label = status.replace('_', ' ').toUpperCase();

  return (
    <span
      className={`inline-flex items-center font-mono font-medium rounded border bg-slate-800/80 text-cyan-400 border-cyan-500/30 ${sizeClasses}`}
    >
      {label}
    </span>
  );
};
