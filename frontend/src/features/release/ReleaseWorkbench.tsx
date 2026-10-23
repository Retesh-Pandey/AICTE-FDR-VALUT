import React, { useState, useEffect } from 'react';
import { api, ReleaseRequestItem, WorkflowStatus } from '@/lib/api';
import { useAuth } from '@/features/auth/AuthContext';
import { InstrumentBadge, WorkflowBadge } from '@/components/common/StatusBadges';
import {
  FileCheck2,
  ShieldCheck,
  CheckCircle2,
  Filter,
  RefreshCw,
  XCircle,
  AlertTriangle,
} from 'lucide-react';

export const ReleaseWorkbench: React.FC = () => {
  const { role } = useAuth();
  const [requests, setRequests] = useState<ReleaseRequestItem[]>([]);
  const [selectedRequest, setSelectedRequest] = useState<ReleaseRequestItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [stageFilter, setStageFilter] = useState<string>('all');
  const [remarks, setRemarks] = useState('');
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [transitionError, setTransitionError] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);

  const fetchRequests = async () => {
    setIsLoading(true);
    try {
      const data = await api.listReleaseRequests(stageFilter === 'all' ? undefined : stageFilter);
      setRequests(data);
      if (selectedRequest) {
        const updated = data.find((r) => r.id === selectedRequest.id);
        if (updated) setSelectedRequest(updated);
      } else if (data.length > 0) {
        setSelectedRequest(data[0]);
      }
    } catch {
      // Ignore background error
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, [stageFilter]);

  const handleTransition = async (to_stage: WorkflowStatus) => {
    if (!selectedRequest) return;
    setIsTransitioning(true);
    setTransitionError(null);
    setSuccessNotice(null);

    try {
      const updated = await api.transitionReleaseRequest(selectedRequest.id, to_stage, remarks);
      setSelectedRequest(updated);
      setRemarks('');
      setSuccessNotice(`Request transitioned to stage '${to_stage.toUpperCase()}' successfully.`);
      await fetchRequests();
    } catch (err: any) {
      setTransitionError(err?.error?.message || 'Transition failed. Please check permissions.');
    } finally {
      setIsTransitioning(false);
    }
  };

  const stagesList: WorkflowStatus[] = [
    'release_requested',
    'under_review',
    'conditions_checked',
    'approval_pending',
    'approved',
    'completed',
  ];

  const getStageIndex = (stage: WorkflowStatus) => {
    if (stage === 'rejected') return -1;
    return stagesList.indexOf(stage);
  };

  return (
    <div className="space-y-6">
      {/* Page Title & Sovereign Invariant Notice */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-mono text-vault-amber mb-1">
            <ShieldCheck className="w-4 h-4" />
            <span>SOVEREIGN RELEASE &amp; ENCASHMENT GOVERNANCE</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">
            FDR Release Management &amp; Stepper
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Role-enforced administrative release workflow. Maturity alone never releases an FDR.
          </p>
        </div>

        <button
          onClick={fetchRequests}
          className="flex items-center space-x-2 px-3 py-1.5 rounded bg-vault-900 hover:bg-vault-850 border border-vault-700 text-xs text-slate-300 hover:text-white transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Queue</span>
        </button>
      </div>

      {/* Main Grid: Requests List & Interactive Stepper Workbench */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Release Requests Table / List */}
        <div className="lg:col-span-5 space-y-4">
          {/* Filter Bar */}
          <div className="p-3 rounded-lg bg-vault-900 border border-vault-800 flex items-center justify-between text-xs">
            <div className="flex items-center space-x-2 text-slate-400">
              <Filter className="w-3.5 h-3.5 text-vault-amber" />
              <span>Filter Stage:</span>
            </div>
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              className="px-2.5 py-1 rounded bg-vault-950 border border-vault-700 text-xs text-slate-200 font-mono focus:border-amber-500 focus:outline-none"
            >
              <option value="all">All Stages</option>
              <option value="release_requested">Release Requested</option>
              <option value="under_review">Under Review</option>
              <option value="conditions_checked">Conditions Checked</option>
              <option value="approval_pending">Approval Pending</option>
              <option value="approved">Approved</option>
              <option value="completed">Completed</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>

          {/* List Card */}
          <div className="p-2 rounded-lg bg-vault-900/60 border border-vault-800 divide-y divide-vault-800/80 max-h-[600px] overflow-y-auto">
            {isLoading && (
              <div className="py-12 text-center text-xs text-slate-400 font-mono">
                Loading release requests...
              </div>
            )}

            {!isLoading && requests.length === 0 && (
              <div className="py-12 text-center text-slate-400 space-y-2">
                <FileCheck2 className="w-8 h-8 mx-auto text-slate-600" />
                <div className="text-xs font-semibold text-slate-300">No Release Requests Found</div>
                <div className="text-[11px] text-slate-400">
                  There are no release requests matching the current filter.
                </div>
              </div>
            )}

            {!isLoading &&
              requests.map((req) => {
                const isSelected = selectedRequest?.id === req.id;
                return (
                  <div
                    key={req.id}
                    onClick={() => setSelectedRequest(req)}
                    className={`p-3.5 rounded-lg transition cursor-pointer mb-1 ${
                      isSelected
                        ? 'bg-vault-800/90 border border-amber-500/50'
                        : 'hover:bg-vault-850 border border-transparent'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-xs text-amber-400 font-mono">
                        {req.fdr_number || 'FDR-INSTRUMENT'}
                      </span>
                      <WorkflowBadge status={req.stage} />
                    </div>

                    <div className="text-xs text-slate-300 font-medium truncate mb-1">
                      {req.institution_name || 'Apex Institute of Technology'}
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                      <span>{req.bank_name || 'State Bank of India'}</span>
                      <span className="text-slate-200 font-bold">
                        ₹{Number(req.amount || 0).toLocaleString('en-IN')}
                      </span>
                    </div>

                    <div className="mt-2 text-[10px] text-slate-400 line-clamp-1 italic">
                      "{req.reason}"
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* Right: Stage Stepper & Role Transition Workbench */}
        <div className="lg:col-span-7">
          {selectedRequest ? (
            <div className="p-6 rounded-xl bg-vault-900 border border-vault-800 shadow-2xl space-y-6">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-vault-800 pb-4 gap-2">
                <div>
                  <div className="text-[10px] font-mono text-slate-400 uppercase">
                    Release Request ID: {selectedRequest.id}
                  </div>
                  <h2 className="text-lg font-bold text-slate-100 mt-0.5">
                    {selectedRequest.fdr_number} · ₹
                    {Number(selectedRequest.amount || 0).toLocaleString('en-IN')}
                  </h2>
                  <div className="text-xs text-slate-300">{selectedRequest.institution_name}</div>
                </div>

                <div className="flex items-center space-x-2">
                  {selectedRequest.fdr_instrument_status && (
                    <InstrumentBadge status={selectedRequest.fdr_instrument_status} />
                  )}
                  <WorkflowBadge status={selectedRequest.stage} />
                </div>
              </div>

              {/* Six-Stage Stepper Component */}
              <div className="space-y-2">
                <div className="text-xs font-semibold text-slate-300">Lifecycle Stage Stepper:</div>
                <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 pt-2">
                  {stagesList.map((st, idx) => {
                    const currentIdx = getStageIndex(selectedRequest.stage);
                    const isPassed = currentIdx >= idx;
                    const isCurrent = selectedRequest.stage === st;
                    const isRejected = selectedRequest.stage === 'rejected';

                    const labels: Record<string, string> = {
                      release_requested: '1. Requested',
                      under_review: '2. Under Review',
                      conditions_checked: '3. Conditions',
                      approval_pending: '4. Pending Exec',
                      approved: '5. Approved',
                      completed: '6. Released',
                    };

                    return (
                      <div
                        key={st}
                        className={`p-2.5 rounded-lg border text-center transition ${
                          isRejected
                            ? 'bg-rose-950/20 border-rose-900 text-slate-500'
                            : isCurrent
                            ? 'bg-amber-950/60 border-amber-500 text-amber-300 font-bold'
                            : isPassed
                            ? 'bg-emerald-950/30 border-emerald-800 text-emerald-400'
                            : 'bg-vault-950 border-vault-800 text-slate-400'
                        }`}
                      >
                        <div className="text-[11px] font-mono leading-tight">{labels[st]}</div>
                        <div className="text-[9px] mt-1 font-mono uppercase">
                          {isCurrent ? 'ACTIVE' : isPassed ? 'PASSED' : 'PENDING'}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {selectedRequest.stage === 'rejected' && (
                  <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800 flex items-center space-x-2 text-rose-300 text-xs">
                    <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>This release request was formally rejected. FDR remains in vault custody.</span>
                  </div>
                )}
              </div>

              {/* Justification Box */}
              <div className="p-3.5 rounded-lg bg-vault-950 border border-vault-800 space-y-1.5">
                <div className="text-[10px] font-mono uppercase text-slate-400">Institutional Justification:</div>
                <p className="text-xs text-slate-200 leading-relaxed font-sans font-medium">
                  "{selectedRequest.reason}"
                </p>
                {selectedRequest.remarks && (
                  <div className="pt-2 border-t border-vault-800/80 text-[11px] text-amber-300/90 font-mono">
                    <span className="font-bold">Officer Remarks:</span> {selectedRequest.remarks}
                  </div>
                )}
              </div>

              {/* Role-Gated Transition Action Controls */}
              <div className="p-4 rounded-lg bg-vault-950/80 border border-vault-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="text-xs font-semibold text-slate-200">
                    Execute Stage Transition ({role?.toUpperCase() || 'USER'})
                  </div>
                  <span className="text-[10px] font-mono text-slate-400">
                    Mandatory Audit Logging Enforced
                  </span>
                </div>

                {/* Remarks Input */}
                <div>
                  <textarea
                    rows={2}
                    value={remarks}
                    onChange={(e) => setRemarks(e.target.value)}
                    placeholder="Enter mandatory transition justification / remarks..."
                    className="w-full px-3 py-2 rounded bg-vault-900 border border-vault-700 text-xs text-slate-200 font-sans focus:border-amber-500 focus:outline-none"
                  />
                </div>

                {transitionError && (
                  <div className="p-2.5 rounded bg-rose-950/40 border border-rose-800 text-xs text-rose-200 flex items-center space-x-2">
                    <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>{transitionError}</span>
                  </div>
                )}

                {successNotice && (
                  <div className="p-2.5 rounded bg-emerald-950/40 border border-emerald-800 text-xs text-emerald-200 flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>{successNotice}</span>
                  </div>
                )}

                {/* Transition Action Buttons */}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  {/* Officer Actions */}
                  {role === 'officer' && (
                    <>
                      {selectedRequest.stage === 'release_requested' && (
                        <button
                          disabled={isTransitioning}
                          onClick={() => handleTransition('under_review')}
                          className="px-3.5 py-2 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition disabled:opacity-50"
                        >
                          Begin Officer Review (under_review)
                        </button>
                      )}

                      {selectedRequest.stage === 'under_review' && (
                        <>
                          <button
                            disabled={isTransitioning || !remarks.trim()}
                            onClick={() => handleTransition('conditions_checked')}
                            className="px-3.5 py-2 rounded bg-amber-600 hover:bg-amber-500 text-slate-950 text-xs font-bold transition disabled:opacity-50"
                          >
                            Mark Conditions Checked
                          </button>
                          <button
                            disabled={isTransitioning || !remarks.trim()}
                            onClick={() => handleTransition('rejected')}
                            className="px-3.5 py-2 rounded bg-rose-900 hover:bg-rose-800 text-white text-xs font-semibold transition disabled:opacity-50"
                          >
                            Reject Request
                          </button>
                        </>
                      )}

                      {selectedRequest.stage === 'conditions_checked' && (
                        <>
                          <button
                            disabled={isTransitioning}
                            onClick={() => handleTransition('approval_pending')}
                            className="px-3.5 py-2 rounded bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition disabled:opacity-50"
                          >
                            Forward to Admin for Executive Approval
                          </button>
                          <button
                            disabled={isTransitioning || !remarks.trim()}
                            onClick={() => handleTransition('rejected')}
                            className="px-3.5 py-2 rounded bg-rose-900 hover:bg-rose-800 text-white text-xs font-semibold transition disabled:opacity-50"
                          >
                            Reject Request
                          </button>
                        </>
                      )}
                    </>
                  )}

                  {/* Admin Actions */}
                  {role === 'admin' && (
                    <>
                      {selectedRequest.stage === 'approval_pending' && (
                        <>
                          <button
                            disabled={isTransitioning || !remarks.trim()}
                            onClick={() => handleTransition('approved')}
                            className="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-slate-950 text-xs font-extrabold transition disabled:opacity-50"
                          >
                            Executive Approve (approved)
                          </button>
                          <button
                            disabled={isTransitioning || !remarks.trim()}
                            onClick={() => handleTransition('rejected')}
                            className="px-3.5 py-2 rounded bg-rose-900 hover:bg-rose-800 text-white text-xs font-semibold transition disabled:opacity-50"
                          >
                            Reject Request
                          </button>
                        </>
                      )}

                      {selectedRequest.stage === 'approved' && (
                        <button
                          disabled={isTransitioning}
                          onClick={() => handleTransition('completed')}
                          className="px-5 py-2.5 rounded bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-extrabold transition shadow-lg shadow-emerald-500/20 disabled:opacity-50 flex items-center space-x-2"
                        >
                          <ShieldCheck className="w-4 h-4" />
                          <span>Complete Release &amp; Discharge Deposit Lien</span>
                        </button>
                      )}
                    </>
                  )}

                  {/* Institution Message */}
                  {role === 'institution' && (
                    <div className="text-[11px] text-slate-400 font-mono">
                      Your release request has been submitted to AICTE New Delhi. Progress will update across the stepper above.
                    </div>
                  )}

                  {selectedRequest.stage === 'completed' && (
                    <div className="text-xs text-emerald-400 font-mono font-bold flex items-center space-x-1.5">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>Security deposit has been officially discharged and marked RELEASED.</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full min-h-[300px] flex items-center justify-center p-8 rounded-xl bg-vault-900 border border-vault-800 text-slate-400 text-center">
              Select a release request from the queue to view its lifecycle stepper.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
