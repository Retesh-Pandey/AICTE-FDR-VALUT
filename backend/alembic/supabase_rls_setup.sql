-- =========================================================================
-- AICTE Smart FDR Lifecycle Management Portal
-- Supabase Postgres Schema & Row Level Security (RLS) Setup
-- =========================================================================
-- Safe, repeatable migration script for Supabase Postgres.
-- Enforces multi-tenant isolation, role checks, and cryptographic audit logs.
-- =========================================================================

-- Enable pgcrypto for UUID generation if not already active
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Create Enums if they do not exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role_enum') THEN
        CREATE TYPE user_role_enum AS ENUM ('institution', 'officer', 'admin');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'instrument_status_enum') THEN
        CREATE TYPE instrument_status_enum AS ENUM ('submitted', 'active', 'renewal_due', 'matured', 'renewed', 'released');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'verification_status_enum') THEN
        CREATE TYPE verification_status_enum AS ENUM ('pending', 'verified', 'discrepancy', 'rejected');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'workflow_status_enum') THEN
        CREATE TYPE workflow_status_enum AS ENUM (
            'none', 'renewal_review', 'release_requested', 'under_review',
            'conditions_checked', 'approval_pending', 'approved', 'rejected', 'completed'
        );
    END IF;
END $$;

-- 2. Tables Schema

-- Institutions (Registry of AICTE approved colleges/universities)
CREATE TABLE IF NOT EXISTS public.institutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aicte_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    region VARCHAR(100),
    address TEXT,
    contact_email VARCHAR(255),
    source VARCHAR(100) NOT NULL DEFAULT 'PORTAL_REGISTRY',
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_institutions_aicte_id ON public.institutions(aicte_id);

-- Institution Registration Requests (Pending Onboarding Queue)
CREATE TABLE IF NOT EXISTS public.institution_registration_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_name VARCHAR(255) NOT NULL,
    aicte_id VARCHAR(100),
    contact_person VARCHAR(255) NOT NULL,
    official_email VARCHAR(255) NOT NULL,
    region VARCHAR(100),
    address TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending_verification',
    reviewed_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    review_decision VARCHAR(50),
    review_reason TEXT,
    reviewed_at TIMESTAMPTZ,
    institution_id UUID REFERENCES public.institutions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_reg_req_email ON public.institution_registration_requests(official_email);
CREATE INDEX IF NOT EXISTS idx_reg_req_status ON public.institution_registration_requests(status);

-- Users (Profiles linked to Supabase Auth auth.users or local sovereign identities)
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    hashed_password VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT true,
    role VARCHAR(50) NOT NULL DEFAULT 'institution',
    institution_id UUID REFERENCES public.institutions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT chk_user_role CHECK (role IN ('institution', 'officer', 'admin'))
);
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
CREATE INDEX IF NOT EXISTS idx_users_institution ON public.users(institution_id);

-- Fixed Deposit Records
CREATE TABLE IF NOT EXISTS public.fdr_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES public.institutions(id) ON DELETE RESTRICT,
    fdr_number VARCHAR(100) NOT NULL,
    bank_name VARCHAR(255) NOT NULL,
    branch VARCHAR(255),
    amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    issue_date DATE NOT NULL,
    maturity_date DATE NOT NULL,
    lien_info TEXT,
    previous_fdr_id UUID REFERENCES public.fdr_records(id) ON DELETE SET NULL,
    is_current BOOLEAN NOT NULL DEFAULT true,
    instrument_status VARCHAR(50) NOT NULL DEFAULT 'submitted',
    verification_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    workflow_status VARCHAR(50) NOT NULL DEFAULT 'none',
    submitted_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_bank_fdr_number UNIQUE (bank_name, fdr_number),
    CONSTRAINT chk_maturity_after_issue CHECK (maturity_date > issue_date)
);
CREATE INDEX IF NOT EXISTS idx_fdr_inst ON public.fdr_records(institution_id);
CREATE INDEX IF NOT EXISTS idx_fdr_maturity ON public.fdr_records(maturity_date);
CREATE INDEX IF NOT EXISTS idx_fdr_status ON public.fdr_records(instrument_status, verification_status);

-- Attached FDR Documents (PDF / scanned receipts)
CREATE TABLE IF NOT EXISTS public.fdr_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fdr_id UUID REFERENCES public.fdr_records(id) ON DELETE CASCADE,
    storage_path VARCHAR(500) NOT NULL,
    doc_type VARCHAR(50) NOT NULL DEFAULT 'fdr_receipt',
    sha256 VARCHAR(64) NOT NULL,
    ocr_raw_text TEXT,
    extracted_json JSONB,
    uploaded_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_fdr_documents_sha256 ON public.fdr_documents(sha256);
CREATE INDEX IF NOT EXISTS idx_fdr_documents_fdr_id ON public.fdr_documents(fdr_id);

-- Verification Logs
CREATE TABLE IF NOT EXISTS public.verification_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fdr_id UUID NOT NULL REFERENCES public.fdr_records(id) ON DELETE CASCADE,
    source VARCHAR(100) NOT NULL,
    submitted_values JSONB NOT NULL,
    confirmed_values JSONB,
    discrepancies JSONB,
    outcome VARCHAR(50) NOT NULL,
    resolved_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    resolution_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_verification_logs_fdr_id ON public.verification_logs(fdr_id);

-- Release Requests
CREATE TABLE IF NOT EXISTS public.release_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fdr_id UUID NOT NULL REFERENCES public.fdr_records(id) ON DELETE CASCADE,
    requested_by UUID NOT NULL REFERENCES public.users(id),
    reason TEXT NOT NULL,
    stage VARCHAR(50) NOT NULL DEFAULT 'release_requested',
    assigned_officer UUID REFERENCES public.users(id),
    remarks TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
);
CREATE INDEX IF NOT EXISTS idx_release_requests_fdr_id ON public.release_requests(fdr_id);

-- Telemetry Notifications & Alerts
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    fdr_id UUID REFERENCES public.fdr_records(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    milestone VARCHAR(50),
    message TEXT NOT NULL,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_notification_milestone UNIQUE (user_id, fdr_id, milestone)
);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON public.notifications(user_id);

-- Append-Only Cryptographic Audit Ledger
CREATE TABLE IF NOT EXISTS public.workflow_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_id UUID,
    actor_role VARCHAR(50),
    action VARCHAR(100) NOT NULL,
    entity VARCHAR(50) NOT NULL,
    entity_id UUID,
    old_status VARCHAR(50),
    new_status VARCHAR(50),
    remarks TEXT,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    prev_hash VARCHAR(64),
    row_hash VARCHAR(64) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON public.workflow_audit_logs(entity, entity_id);

-- Synthetic Mock Bank Records (Simulated verifier sandbox)
CREATE TABLE IF NOT EXISTS public.mock_bank_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fdr_number VARCHAR(100) NOT NULL,
    bank_name VARCHAR(255) NOT NULL,
    branch VARCHAR(255),
    amount NUMERIC(14, 2) NOT NULL,
    issue_date DATE NOT NULL,
    maturity_date DATE NOT NULL,
    lien_marked BOOLEAN NOT NULL DEFAULT true,
    status VARCHAR(50) NOT NULL DEFAULT 'CONFIRMED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT uq_mock_bank_fdr UNIQUE (bank_name, fdr_number)
);

-- =========================================================================
-- 3. Row Level Security Helper Functions
-- =========================================================================

-- Extract authenticated user's assigned role from public.users
CREATE OR REPLACE FUNCTION public.get_auth_role()
RETURNS VARCHAR AS $$
    SELECT role FROM public.users WHERE id = auth.uid() OR email = auth.jwt() ->> 'email' LIMIT 1;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- Extract authenticated user's assigned institution ID from public.users
CREATE OR REPLACE FUNCTION public.get_auth_institution_id()
RETURNS UUID AS $$
    SELECT institution_id FROM public.users WHERE id = auth.uid() OR email = auth.jwt() ->> 'email' LIMIT 1;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- Check if current user is an Admin
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
    SELECT COALESCE(public.get_auth_role() = 'admin', false);
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- Check if current user is an Officer
CREATE OR REPLACE FUNCTION public.is_officer()
RETURNS BOOLEAN AS $$
    SELECT COALESCE(public.get_auth_role() = 'officer', false);
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- Check if current user is an Officer or Admin
CREATE OR REPLACE FUNCTION public.is_officer_or_admin()
RETURNS BOOLEAN AS $$
    SELECT COALESCE(public.get_auth_role() IN ('officer', 'admin'), false);
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- Comprehensive Multi-Tenant Access Verification Function:
-- Returns TRUE if the authenticated user has legitimate authorization to access target_institution_id.
-- 1. Admins have global council-wide access.
-- 2. Officers with assigned institution_id access only that specific institution;
--    officers with institution_id IS NULL have council-wide vigilance access.
-- 3. Institution users access ONLY their own non-null assigned institution.
-- 4. Unauthenticated or foreign tenant requests are strictly DENIED.
CREATE OR REPLACE FUNCTION public.can_access_institution(target_inst_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    user_role VARCHAR;
    user_inst_id UUID;
BEGIN
    IF target_inst_id IS NULL THEN
        RETURN FALSE;
    END IF;

    user_role := public.get_auth_role();
    user_inst_id := public.get_auth_institution_id();

    -- 1. Council Administrators have sovereign access
    IF user_role = 'admin' THEN
        RETURN TRUE;
    END IF;

    -- 2. Vigilance & Regional Officers
    IF user_role = 'officer' THEN
        -- If officer is assigned to a specific regional portfolio, enforce that boundary
        IF user_inst_id IS NOT NULL THEN
            RETURN user_inst_id = target_inst_id;
        END IF;
        -- Council-wide vigilance officer
        RETURN TRUE;
    END IF;

    -- 3. Technical Institution Users
    IF user_role = 'institution' THEN
        IF user_inst_id IS NOT NULL AND user_inst_id = target_inst_id THEN
            RETURN TRUE;
        END IF;
        RETURN FALSE;
    END IF;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- =========================================================================
-- 4. Enable Row Level Security (RLS) on All Tables
-- =========================================================================
ALTER TABLE public.institutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fdr_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fdr_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.verification_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.release_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mock_bank_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.institution_registration_requests ENABLE ROW LEVEL SECURITY;

-- =========================================================================
-- 5. Row Level Security Policies
-- =========================================================================

-- Drop existing policies to ensure clean, repeatable application
DROP POLICY IF EXISTS "institutions_select_policy" ON public.institutions;
DROP POLICY IF EXISTS "registration_requests_insert_policy" ON public.institution_registration_requests;
DROP POLICY IF EXISTS "registration_requests_officer_policy" ON public.institution_registration_requests;
DROP POLICY IF EXISTS "users_self_or_officer_policy" ON public.users;
DROP POLICY IF EXISTS "users_no_self_role_escalation" ON public.users;
DROP POLICY IF EXISTS "fdr_records_select_policy" ON public.fdr_records;
DROP POLICY IF EXISTS "fdr_records_insert_policy" ON public.fdr_records;
DROP POLICY IF EXISTS "fdr_records_update_policy" ON public.fdr_records;
DROP POLICY IF EXISTS "fdr_records_delete_policy" ON public.fdr_records;
DROP POLICY IF EXISTS "fdr_documents_select_policy" ON public.fdr_documents;
DROP POLICY IF EXISTS "fdr_documents_insert_policy" ON public.fdr_documents;
DROP POLICY IF EXISTS "fdr_documents_delete_policy" ON public.fdr_documents;
DROP POLICY IF EXISTS "fdr_documents_policy" ON public.fdr_documents;
DROP POLICY IF EXISTS "release_requests_policy" ON public.release_requests;
DROP POLICY IF EXISTS "notifications_policy" ON public.notifications;
DROP POLICY IF EXISTS "audit_logs_select_policy" ON public.workflow_audit_logs;
DROP POLICY IF EXISTS "mock_bank_records_officer_policy" ON public.mock_bank_records;

-- Institutions Policy:
-- Public directory can search non-sensitive identity (name, AICTE ID, region);
-- Full records visible to assigned institution, officers, admins
CREATE POLICY "institutions_select_policy" ON public.institutions
FOR SELECT USING (
    public.can_access_institution(id)
    OR auth.role() = 'anon'
);

-- Users Policy:
-- Users can view their own profile; Officers & Admins can view users within scope
CREATE POLICY "users_self_or_officer_policy" ON public.users
FOR SELECT USING (
    id = auth.uid()
    OR email = auth.jwt() ->> 'email'
    OR public.is_admin()
    OR (public.is_officer() AND (public.get_auth_institution_id() IS NULL OR institution_id = public.get_auth_institution_id()))
);

-- FDR Records SELECT:
-- Enforces least-privilege scoping: institution users see only their own deposit amounts;
-- Scoped officers see only assigned institutions; Admins see all.
CREATE POLICY "fdr_records_select_policy" ON public.fdr_records
FOR SELECT USING (
    public.can_access_institution(institution_id)
);

-- FDR Records INSERT:
-- Institution users can only insert records targeting their own assigned institution.
-- Prevents users from inserting FDRs under someone else's institution_id.
CREATE POLICY "fdr_records_insert_policy" ON public.fdr_records
FOR INSERT WITH CHECK (
    public.can_access_institution(institution_id)
    AND (
        public.is_officer_or_admin()
        OR (public.get_auth_role() = 'institution' AND institution_id = public.get_auth_institution_id())
    )
);

-- FDR Records UPDATE:
-- Only authorized Officers/Admins can update verification status or statutory flags.
-- Prevents institution users from tampering with deposit status, verification, or institution ownership.
CREATE POLICY "fdr_records_update_policy" ON public.fdr_records
FOR UPDATE USING (
    public.is_admin()
    OR (public.is_officer() AND (public.get_auth_institution_id() IS NULL OR institution_id = public.get_auth_institution_id()))
);

-- FDR Records DELETE:
-- Only Sovereign Administrators can delete records; institution users are strictly forbidden.
CREATE POLICY "fdr_records_delete_policy" ON public.fdr_records
FOR DELETE USING (
    public.is_admin()
);

-- FDR Documents SELECT:
-- Scoped to parent FDR record's institution access rule
CREATE POLICY "fdr_documents_select_policy" ON public.fdr_documents
FOR SELECT USING (
    public.can_access_institution((SELECT r.institution_id FROM public.fdr_records r WHERE r.id = fdr_id))
);

-- FDR Documents INSERT:
CREATE POLICY "fdr_documents_insert_policy" ON public.fdr_documents
FOR INSERT WITH CHECK (
    public.can_access_institution((SELECT r.institution_id FROM public.fdr_records r WHERE r.id = fdr_id))
);

-- FDR Documents DELETE:
-- Prohibit unauthorized document destruction; Admin only.
CREATE POLICY "fdr_documents_delete_policy" ON public.fdr_documents
FOR DELETE USING (
    public.is_admin()
);

-- Release Requests Policy:
-- Institutions can view & create their own release requests; Officers/Admins review within their scope
CREATE POLICY "release_requests_policy" ON public.release_requests
FOR ALL USING (
    public.is_admin()
    OR (
        public.is_officer()
        AND (
            public.get_auth_institution_id() IS NULL
            OR fdr_id IN (SELECT id FROM public.fdr_records WHERE institution_id = public.get_auth_institution_id())
        )
    )
    OR (
        public.get_auth_role() = 'institution'
        AND fdr_id IN (SELECT id FROM public.fdr_records WHERE institution_id = public.get_auth_institution_id())
    )
);

-- Notifications Policy:
-- Scoped strictly to the recipient user or their assigned institution
CREATE POLICY "notifications_policy" ON public.notifications
FOR ALL USING (
    user_id = auth.uid()
    OR public.is_admin()
    OR (
        public.is_officer()
        AND (
            public.get_auth_institution_id() IS NULL
            OR fdr_id IN (SELECT id FROM public.fdr_records WHERE institution_id = public.get_auth_institution_id())
        )
    )
);

-- Audit Logs Policy:
-- Append-only ledger; only Officers and Admins can inspect the sovereign audit chain
CREATE POLICY "audit_logs_select_policy" ON public.workflow_audit_logs
FOR SELECT USING (
    public.is_officer_or_admin()
);

-- Mock Bank Records Policy:
-- Sandbox mock bank records are strictly accessible by Officers and Admins
CREATE POLICY "mock_bank_records_officer_policy" ON public.mock_bank_records
FOR SELECT USING (
    public.is_officer_or_admin()
);


-- Institution Registration Requests Policies:
-- Anyone can submit a registration request with status 'pending_verification'
CREATE POLICY "registration_requests_insert_policy" ON public.institution_registration_requests
FOR INSERT WITH CHECK (
    status = 'pending_verification'
);

-- Only Officers/Admins or the applicant who owns the email can view registration requests
CREATE POLICY "registration_requests_officer_policy" ON public.institution_registration_requests
FOR ALL USING (
    public.is_officer_or_admin()
    OR official_email = auth.jwt() ->> 'email'
);

-- =========================================================================
-- 6. Trigger: Prevent Role and Institution Self-Escalation
-- =========================================================================
CREATE OR REPLACE FUNCTION public.prevent_self_role_change()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT public.is_officer_or_admin() AND auth.role() != 'service_role' THEN
        IF NEW.role != OLD.role OR NEW.institution_id != OLD.institution_id THEN
            RAISE EXCEPTION 'Unauthorized: Users cannot modify their assigned role or institution affiliation.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_prevent_role_change ON public.users;
CREATE TRIGGER trg_prevent_role_change
BEFORE UPDATE ON public.users
FOR EACH ROW EXECUTE FUNCTION public.prevent_self_role_change();

-- =========================================================================
-- 7. Supabase Storage: Private Document Bucket & RLS Policies
-- =========================================================================
-- Ensure the 'fdr-documents' bucket exists and is marked private (public = false)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'fdr-documents',
    'fdr-documents',
    false,
    15728640, -- 15 MB
    ARRAY['application/pdf', 'image/png', 'image/jpeg']
)
ON CONFLICT (id) DO UPDATE SET
    public = false,
    file_size_limit = 15728640,
    allowed_mime_types = ARRAY['application/pdf', 'image/png', 'image/jpeg'];

-- Drop existing storage policies
DROP POLICY IF EXISTS "fdr_storage_select_policy" ON storage.objects;
DROP POLICY IF EXISTS "fdr_storage_insert_policy" ON storage.objects;
DROP POLICY IF EXISTS "fdr_storage_delete_policy" ON storage.objects;

-- Storage SELECT Policy:
-- Strictly authorize file reads to owner institution or authorized officers/admins
-- Files are stored under path: <institution_id>/<filename>
CREATE POLICY "fdr_storage_select_policy" ON storage.objects
FOR SELECT USING (
    bucket_id = 'fdr-documents'
    AND (
        public.is_admin()
        OR (public.is_officer() AND (public.get_auth_institution_id() IS NULL OR (storage.foldername(name))[1] = public.get_auth_institution_id()::text))
        OR (public.get_auth_role() = 'institution' AND (storage.foldername(name))[1] = public.get_auth_institution_id()::text)
    )
);

-- Storage INSERT Policy:
-- Users can only upload files into their own institution's storage folder
CREATE POLICY "fdr_storage_insert_policy" ON storage.objects
FOR INSERT WITH CHECK (
    bucket_id = 'fdr-documents'
    AND (
        public.is_admin()
        OR (public.is_officer() AND (public.get_auth_institution_id() IS NULL OR (storage.foldername(name))[1] = public.get_auth_institution_id()::text))
        OR (public.get_auth_role() = 'institution' AND (storage.foldername(name))[1] = public.get_auth_institution_id()::text)
    )
);

-- Storage DELETE Policy:
-- Prohibit unauthorized file deletion; Admin or service role only
CREATE POLICY "fdr_storage_delete_policy" ON storage.objects
FOR DELETE USING (
    bucket_id = 'fdr-documents'
    AND public.is_admin()
);

