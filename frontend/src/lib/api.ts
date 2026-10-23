const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export type UserRole = 'institution' | 'officer' | 'admin';

export type InstrumentStatus =
  | 'submitted'
  | 'active'
  | 'renewal_due'
  | 'matured'
  | 'renewed'
  | 'released';

export type VerificationStatus = 'pending' | 'verified' | 'discrepancy' | 'rejected';

export type WorkflowStatus =
  | 'none'
  | 'renewal_review'
  | 'release_requested'
  | 'under_review'
  | 'conditions_checked'
  | 'approval_pending'
  | 'approved'
  | 'rejected'
  | 'completed';

export interface User {
  id: string;
  email: string;
  full_name?: string;
  role: UserRole;
  institution_id?: string;
  institution?: {
    id: string;
    aicte_id: string;
    name: string;
    region?: string;
  };
}

export interface FDRDocument {
  id: string;
  fdr_id?: string;
  storage_path: string;
  doc_type: string;
  sha256: string;
  ocr_raw_text?: string;
  extracted_json?: any;
  uploaded_by?: string;
  uploaded_at: string;
  signed_url?: string;
}

export interface VerificationLog {
  id: string;
  fdr_id: string;
  source: string;
  submitted_values: any;
  confirmed_values?: any;
  discrepancies?: any[];
  outcome: VerificationStatus;
  resolved_by?: string;
  resolution_note?: string;
  created_at: string;
}

export interface FDRRecord {
  id: string;
  institution_id: string;
  fdr_number: string;
  bank_name: string;
  branch?: string;
  amount: number | string;
  issue_date: string;
  maturity_date: string;
  lien_info?: string;
  previous_fdr_id?: string;
  is_current: boolean;
  instrument_status: InstrumentStatus;
  verification_status: VerificationStatus;
  workflow_status: WorkflowStatus;
  submitted_by?: string;
  created_at: string;
  updated_at: string;
  institution?: {
    id: string;
    aicte_id: string;
    name: string;
    region?: string;
  };
  documents?: FDRDocument[];
  verification_logs?: VerificationLog[];
  release_requests?: any[];
}

export interface FDRListResponse {
  items: FDRRecord[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface DashboardSummary {
  total_fdrs: number;
  active_fdrs: number;
  total_active_amount: string | number;
  expiring_30_days: number;
  pending_verification: number;
  flagged_discrepancies: number;
  matured_fdrs: number;
  recent_records: FDRRecord[];
}

export interface OCRField {
  value: string | null;
  confidence: number;
}

export interface DocumentClassification {
  status:
    | 'likely_fdr'
    | 'possibly_fdr_needs_review'
    | 'likely_unrelated'
    | 'unreadable'
    | 'ocr_unavailable'
    | 'corrupt_or_unsupported';
  confidence: number;
  classification_reasons: string[];
  detected_document_type?: string | null;
  content_summary: string;
  extracted_snippets?: string[];
  is_fdr_candidate: boolean;
  submission_blocked: boolean;
}

export interface DocumentReviewItem {
  id: string;
  institution_id: string;
  institution_name?: string;
  fdr_id?: string | null;
  document_sha256: string;
  filename: string;
  storage_path?: string | null;
  classification: string;
  confidence: number;
  classification_reasons?: string[] | null;
  detected_document_type?: string | null;
  content_summary?: string | null;
  extracted_snippets?: string[] | null;
  review_status: 'pending' | 'confirmed_unrelated' | 'overridden_as_fdr' | 'dismissed';
  is_strike: boolean;
  reviewed_by?: string | null;
  reviewer_name?: string | null;
  reviewed_at?: string | null;
  review_reason?: string | null;
  created_at: string;
}

export interface InstitutionHoldStatus {
  institution_id: string;
  institution_name: string;
  upload_hold_active: boolean;
  upload_hold_until?: string | null;
  upload_hold_reason?: string | null;
  upload_hold_placed_at?: string | null;
  upload_hold_placed_by?: string | null;
  upload_hold_appealed_at?: string | null;
  upload_hold_appeal_reason?: string | null;
  confirmed_strikes_in_window: number;
  strike_threshold: number;
  window_days: number;
  hold_duration_days: number;
}

export interface OCRResult {
  fdr_number: OCRField;
  bank_name: OCRField;
  ifsc: OCRField;
  branch: OCRField;
  amount: OCRField;
  interest_rate: OCRField;
  compounding?: OCRField;
  tenure?: OCRField;
  issue_date: OCRField;
  maturity_date: OCRField;
  institution_name?: OCRField;
  institution_id?: OCRField;
  lien_info: OCRField;
  raw_text: string;
  extraction_status: 'success' | 'partial' | 'needs_review' | 'unreadable' | 'ocr_unavailable' | 'processing_error' | string;
  status_detail?: string | null;
  engine_available?: boolean;
  engine_status?: string;
  classification?: DocumentClassification;
  disclaimer: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: any;
  };
}

let currentToken: string | null = localStorage.getItem('vault_token');

export const setAuthToken = (token: string | null) => {
  currentToken = token;
  if (token) {
    localStorage.setItem('vault_token', token);
  } else {
    localStorage.removeItem('vault_token');
  }
};

export const getAuthToken = () => currentToken;

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});

  if (currentToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${currentToken}`);
  }

  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData: any;
    try {
      errorData = await response.json();
    } catch {
      errorData = { error: { code: 'NETWORK_ERROR', message: response.statusText } };
    }
    throw errorData;
  }

  return response.json();
}


export interface NotificationItem {
  id: string;
  user_id?: string;
  fdr_id?: string;
  type: string;
  milestone?: string;
  message: string;
  read_at?: string;
  created_at: string;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  unread_count: number;
}

export interface ReleaseRequestItem {
  id: string;
  fdr_id: string;
  requested_by: string;
  reason: string;
  stage: WorkflowStatus;
  assigned_officer?: string;
  remarks?: string;
  created_at: string;
  updated_at: string;
  fdr_number?: string;
  bank_name?: string;
  amount?: number | string;
  institution_name?: string;
  fdr_instrument_status?: InstrumentStatus;
}

export interface SimulationStatus {
  effective_date: string;
  simulated_date?: string;
  is_simulated: boolean;
  simulation_enabled: boolean;
}

export interface ChainVerificationResult {
  valid: boolean;
  broken_at: number | null;
  total_blocks: number;
  head_hash?: string | null;
  verified_at?: string | null;
  verification_time_ms?: number | null;
  message?: string | null;
}

export interface AuditLogEntry {
  id: number;
  actor_id?: string | null;
  actor_role?: string | null;
  action: string;
  entity: string;
  entity_id?: string | null;
  old_status?: string | null;
  new_status?: string | null;
  remarks?: string | null;
  payload?: any;
  created_at: string;
  prev_hash?: string | null;
  row_hash: string;
}

export interface PriorityCaseItem {
  fdr_id: string;
  fdr_number: string;
  institution_name: string;
  bank_name: string;
  amount: number | string;
  priority_type: string;
  urgency: 'high' | 'medium' | 'low';
  reason: string;
  days_until_maturity?: number;
  created_at: string;
}

export interface ChartTelemetryResponse {
  status_distribution: Array<{ status: string; name: string; count: number; amount: number; color: string }>;
  maturity_by_month: Array<{ month: string; count: number; amount: number }>;
  amount_by_bank: Array<{ bank_name: string; count: number; amount: number }>;
}

export interface ReportSummaryResponse {
  report_type: string;
  total_records: number;
  total_amount: number;
  records: Array<{
    fdr_number: string;
    institution_name: string;
    institution_code: string;
    bank_name: string;
    branch: string;
    amount: number;
    amount_formatted: string;
    issue_date: string;
    maturity_date: string;
    instrument_status: string;
    verification_status: string;
    workflow_status: string;
    lien_info: string;
    created_at: string;
  }>;
}

export interface SimulatedVerificationComparison {
  field: string;
  submitted?: string | null;
  confirmed?: string | null;
  match: boolean;
  status?: string;
  difference?: string | null;
}

export interface InstitutionPublicBrief {
  id: string;
  aicte_id: string;
  name: string;
  region?: string;
  source?: string;
  is_synthetic: boolean;
  last_synced_at?: string | null;
}

export interface InstitutionDirectoryPage {
  items: InstitutionPublicBrief[];
  total: number;
  page: number;
  limit: number;
  pages: number;
  source_label: string;
  coverage_disclaimer: string;
  last_synced_at?: string | null;
}

export interface InstitutionRegistrationCreate {
  institution_name: string;
  aicte_id?: string;
  contact_person: string;
  official_email: string;
  region?: string;
  address?: string;
}

export interface InstitutionRegistrationResponse {
  id: string;
  institution_name: string;
  aicte_id?: string;
  contact_person: string;
  official_email: string;
  region?: string;
  address?: string;
  status: string;
  review_decision?: string;
  review_reason?: string;
  reviewed_at?: string;
  created_at: string;
  tracking_reference: string;
  notice: string;
}

export interface SimulatedVerificationResponse {
  source: string;
  outcome: 'match' | 'mismatch' | 'not_found';
  mode: string;
  fdr_id: string;
  fdr_number: string;
  bank_name: string;
  matched_fields: string[];
  different_fields: Array<{ field: string; submitted?: string; confirmed?: string; reason?: string }>;
  all_comparisons: SimulatedVerificationComparison[];
  disclaimer: string;
  timestamp: string;
  actor?: string;
  new_verification_status: VerificationStatus;
  verification_log_id?: string;
}

export const api = {
  get: <T>(endpoint: string, options?: RequestInit) => request<T>(endpoint, options),
  post: <T>(endpoint: string, body?: any, options?: RequestInit) =>
    request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),
  put: <T>(endpoint: string, body?: any, options?: RequestInit) =>
    request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),
  delete: <T>(endpoint: string, options?: RequestInit) => request<T>(endpoint, { ...options, method: 'DELETE' }),

  // Auth endpoints
  getMe: () => request<User>('/me'),
  login: (email: string, password: string) =>
    request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ status: string; message: string }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
    }),
  demoLogin: (email: string) =>
    request<AuthResponse>('/auth/demo-login', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  getHealth: () => request<any>('/health'),
  searchInstitutionsPublic: (q: string) =>
    request<InstitutionPublicBrief[]>(`/institutions/public-search?q=${encodeURIComponent(q)}`),
  getInstitutionDirectory: (params: {
    q?: string;
    region?: string;
    page?: number;
    limit?: number;
  } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.q) searchParams.set('q', params.q);
    if (params.region) searchParams.set('region', params.region);
    if (params.page) searchParams.set('page', params.page.toString());
    if (params.limit) searchParams.set('limit', params.limit.toString());
    const qs = searchParams.toString();
    return request<InstitutionDirectoryPage>(`/institutions/directory${qs ? `?${qs}` : ''}`);
  },
  submitInstitutionRegistrationRequest: (data: InstitutionRegistrationCreate) =>
    request<InstitutionRegistrationResponse>('/institutions/register-request', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listRegistrationRequests: (status?: string) => {
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    return request<InstitutionRegistrationResponse[]>(`/institutions/registration-requests${q}`);
  },
  reviewRegistrationRequest: (id: string, decision: 'approved' | 'rejected' | 'duplicate', review_reason: string) =>
    request<InstitutionRegistrationResponse>(`/institutions/registration-requests/${id}/review`, {
      method: 'POST',
      body: JSON.stringify({ decision, review_reason }),
    }),
  syncInstitutionDirectory: (source: string, institutions: any[]) =>
    request<any>('/institutions/sync-directory', {
      method: 'POST',
      body: JSON.stringify({ source, institutions }),
    }),

  // Dashboard Telemetry
  getDashboardSummary: (institutionId?: string) => {
    const q = institutionId ? `?institution_id=${institutionId}` : '';
    return request<DashboardSummary>(`/dashboard/summary${q}`);
  },

  // FDR Management
  listFDRs: (params: {
    status?: string;
    verification_status?: string;
    bank?: string;
    q?: string;
    page?: number;
    limit?: number;
  } = {}) => {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.set('status', params.status);
    if (params.verification_status) searchParams.set('verification_status', params.verification_status);
    if (params.bank) searchParams.set('bank', params.bank);
    if (params.q) searchParams.set('q', params.q);
    if (params.page) searchParams.set('page', params.page.toString());
    if (params.limit) searchParams.set('limit', params.limit.toString());

    const qs = searchParams.toString();
    return request<FDRListResponse>(`/fdrs${qs ? `?${qs}` : ''}`);
  },

  getFDR: (id: string) => request<FDRRecord>(`/fdrs/${id}`),

  submitFDR: (formData: FormData) =>
    request<{ fdr: FDRRecord; document: FDRDocument; validation_flags: any[]; message: string }>('/fdrs', {
      method: 'POST',
      body: formData,
    }),

  ocrExtract: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<OCRResult>('/fdrs/ocr', {
      method: 'POST',
      body: formData,
    });
  },

  verifyFDRWithBank: (id: string) =>
    request<SimulatedVerificationResponse>(`/fdrs/${id}/verify`, {
      method: 'POST',
    }),

  resolveDiscrepancy: (id: string, outcome: VerificationStatus, resolution_note: string) =>
    request<FDRRecord>(`/fdrs/${id}/resolve-discrepancy`, {
      method: 'POST',
      body: JSON.stringify({ outcome, resolution_note }),
    }),

  getFDRAudit: (id: string) => request<AuditLogEntry[]>(`/fdrs/${id}/audit`),

  getAuditLogs: (limit = 100) => request<AuditLogEntry[]>(`/audit/logs?limit=${limit}`),

  verifyAuditChain: () => request<ChainVerificationResult>('/audit/verify-chain'),

  // Hackathon Date Simulator
  getSimulatedDate: () => request<SimulationStatus>('/admin/simulate-date'),
  simulateDate: (payload: { target_date?: string; offset_days?: number; reset?: boolean }) =>
    request<{ status: string; effective_date: string; is_simulated: boolean; results: any }>('/admin/simulate-date', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Notifications
  getNotifications: () => request<NotificationListResponse>('/notifications'),
  markNotificationRead: (id: string) =>
    request<NotificationItem>(`/notifications/${id}/read`, { method: 'POST' }),
  markAllNotificationsRead: () =>
    request<{ status: string; marked_read: number }>('/notifications/read-all', { method: 'POST' }),

  // Release Workflow
  createReleaseRequest: (fdr_id: string, reason: string) =>
    request<ReleaseRequestItem>('/release/requests', {
      method: 'POST',
      body: JSON.stringify({ fdr_id, reason }),
    }),
  listReleaseRequests: (stage?: string) => {
    const q = stage ? `?stage=${stage}` : '';
    return request<ReleaseRequestItem[]>(`/release/requests${q}`);
  },
  getReleaseRequest: (id: string) => request<ReleaseRequestItem>(`/release/requests/${id}`),
  transitionReleaseRequest: (id: string, to_stage: WorkflowStatus, remarks?: string) =>
    request<ReleaseRequestItem>(`/release/requests/${id}/transition`, {
      method: 'POST',
      body: JSON.stringify({ to_stage, remarks }),
    }),

  // Renewal Workflow
  renewFDR: (id: string, formData: FormData) =>
    request<{ record: FDRRecord; document_id: string; validation_flags: any[]; notice: string }>(`/fdrs/${id}/renew`, {
      method: 'POST',
      body: formData,
    }),
  approveRenewal: (id: string, remarks: string) =>
    request<FDRRecord>(`/renewals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ remarks }),
    }),
  rejectRenewal: (id: string, remarks: string) =>
    request<FDRRecord>(`/renewals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ remarks }),
    }),

  // Phase 7: Priority Cases, Charts & Reporting Exports
  getPriorityCases: () => request<PriorityCaseItem[]>('/dashboard/priority-cases'),
  getChartsData: () => request<ChartTelemetryResponse>('/dashboard/charts'),
  getReportData: (type: string = 'all') => request<ReportSummaryResponse>(`/reports/data?type=${type}`),
  downloadReportExcel: async (type: string = 'all', format: 'xlsx' | 'csv' = 'xlsx') => {
    const token = getAuthToken() || localStorage.getItem('vault_token');
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${API_BASE_URL}/reports/ledger-export?type=${type}&format=${format}`, { headers });
    if (!res.ok) {
      let errMsg = `Failed to download ${format.toUpperCase()} ledger`;
      try {
        const errJson = await res.json();
        errMsg = errJson.detail || errJson.message || errMsg;
      } catch {}
      throw new Error(errMsg);
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const ext = format === 'csv' ? 'csv' : 'xlsx';
    a.download = `aicte_fdr_ledger_${type}_${new Date().toISOString().slice(0, 10)}.${ext}`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  // Document Review Queue & Escalation Management
  listReviewQueue: (status?: string, institutionId?: string) => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (institutionId) params.append('institution_id', institutionId);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return request<DocumentReviewItem[]>(`/fdrs/review-queue${qs}`);
  },
  getReviewItem: (id: string) => request<DocumentReviewItem>(`/fdrs/review-queue/${id}`),
  adjudicateReview: (id: string, decision: 'confirm_unrelated' | 'override_as_fdr' | 'dismiss', reason: string) =>
    request<DocumentReviewItem>(`/fdrs/review-queue/${id}/adjudicate`, {
      method: 'POST',
      body: JSON.stringify({ decision, reason }),
    }),
  requestDocumentReview: (payload: {
    filename: string;
    sha256_hash: string;
    classification: any;
    storage_path?: string;
    fdr_id?: string;
  }) =>
    request<DocumentReviewItem>('/fdrs/request-review', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Institution Hold & Appeal
  getInstitutionHoldStatus: (institutionId: string) =>
    request<InstitutionHoldStatus>(`/institutions/${institutionId}/hold-status`),
  appealInstitutionHold: (institutionId: string, appeal_reason: string) =>
    request<{ status: string; message: string }>(`/institutions/${institutionId}/appeal-hold`, {
      method: 'POST',
      body: JSON.stringify({ appeal_reason }),
    }),

  // Admin Hold Management
  listHeldInstitutions: () => request<InstitutionHoldStatus[]>('/admin/institutions/held'),
  adminUnfreezeHold: (institutionId: string, reason: string) =>
    request<{ status: string; message: string }>(`/admin/institutions/${institutionId}/unfreeze-hold`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  adminExtendHold: (institutionId: string, days: number, reason: string) =>
    request<{ status: string; message: string }>(`/admin/institutions/${institutionId}/extend-hold`, {
      method: 'POST',
      body: JSON.stringify({ days, reason }),
    }),

  // OCR Health Diagnostic
  getOCRHealth: () =>
    request<{
      status: string;
      engine_available: boolean;
      engine_status: string;
      engine_diagnostic?: any;
      escalation_policy?: any;
    }>('/health/ocr'),
};

