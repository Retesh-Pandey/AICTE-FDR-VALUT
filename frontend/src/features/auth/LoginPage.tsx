import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import {
  api,
  InstitutionPublicBrief,
  InstitutionDirectoryPage,
  InstitutionRegistrationCreate,
  InstitutionRegistrationResponse,
} from '@/lib/api';
import {
  Shield,
  Building,
  UserCheck,
  ShieldAlert,
  ArrowRight,
  Lock,
  Sun,
  Moon,
  Globe,
  Search,
  CheckCircle2,
  X,
  AlertCircle,
  KeyRound,
  ChevronLeft,
  ChevronRight,
  PlusCircle,
  HelpCircle,
  Check,
  Loader2,
  Send,
  Database,
} from 'lucide-react';
import { getSupabaseConfig, checkSupabaseConnection } from '@/lib/supabase';

type RoleChoice = 'institution' | 'officer' | 'admin';

export const LoginPage: React.FC = () => {
  const { login, signUp, loginWithDemo } = useAuth();
  const { t, lang, toggleLang } = useI18n();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  // Authentication Mode: Sign In vs Sign Up (Supabase Auth)
  const [authMode, setAuthMode] = useState<'signin' | 'signup'>('signin');
  const [fullName, setFullName] = useState('');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Supabase connection state
  const supabaseConfig = getSupabaseConfig();
  const [supabaseStatus, setSupabaseStatus] = useState<{
    checking: boolean;
    connected: boolean;
    message: string;
  }>({
    checking: supabaseConfig.configured,
    connected: false,
    message: supabaseConfig.configured ? 'Verifying connection...' : 'Using local/demo mode',
  });

  useEffect(() => {
    if (supabaseConfig.configured) {
      checkSupabaseConnection().then((res) => {
        setSupabaseStatus({
          checking: false,
          connected: res.connected,
          message: res.message,
        });
      });
    }
  }, [supabaseConfig.configured]);

  // Active authentication role (defaults to Technical Institution)
  const [activeRole, setActiveRole] = useState<RoleChoice>('institution');

  // Form credentials
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Institution autocomplete state
  const [instQuery, setInstQuery] = useState('');
  const [instSuggestions, setInstSuggestions] = useState<InstitutionPublicBrief[]>([]);
  const [isSearchingInst, setIsSearchingInst] = useState(false);
  const [instSearchError, setInstSearchError] = useState<string | null>(null);
  const [showInstDropdown, setShowInstDropdown] = useState(false);
  const [selectedInst, setSelectedInst] = useState<InstitutionPublicBrief | null>(null);
  const [instHighlightIndex, setInstHighlightIndex] = useState(-1);

  // Modals state
  const [showBrowseModal, setShowBrowseModal] = useState(false);
  const [showRegisterModal, setShowRegisterModal] = useState(false);

  // Directory browse state
  const [directoryData, setDirectoryData] = useState<InstitutionDirectoryPage | null>(null);
  const [directoryLoading, setDirectoryLoading] = useState(false);
  const [directoryError, setDirectoryError] = useState<string | null>(null);
  const [directoryQuery, setDirectoryQuery] = useState('');
  const [directoryRegion, setDirectoryRegion] = useState('');
  const [directoryPage, setDirectoryPage] = useState(1);

  // Registration Request Form state
  const [regForm, setRegForm] = useState<InstitutionRegistrationCreate>({
    institution_name: '',
    aicte_id: '',
    contact_person: '',
    official_email: '',
    region: 'Northern',
    address: '',
  });
  const [regSubmitting, setRegSubmitting] = useState(false);
  const [regError, setRegError] = useState<string | null>(null);
  const [regSuccess, setRegSuccess] = useState<InstitutionRegistrationResponse | null>(null);

  // Refs for accessibility and focus management
  const authBoardRef = useRef<HTMLDivElement>(null);
  const emailInputRef = useRef<HTMLInputElement>(null);
  const instSearchRef = useRef<HTMLDivElement>(null);
  const instInputRef = useRef<HTMLInputElement>(null);

  // Debounced institution type-ahead search backed by backend/Supabase database
  useEffect(() => {
    if (!instQuery || instQuery.trim().length < 1 || selectedInst?.name === instQuery) {
      setInstSuggestions([]);
      setIsSearchingInst(false);
      setInstSearchError(null);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearchingInst(true);
      setInstSearchError(null);
      try {
        const results = await api.searchInstitutionsPublic(instQuery.trim());
        setInstSuggestions(results);
        setShowInstDropdown(true);
        setInstHighlightIndex(-1);
      } catch (err: any) {
        setInstSuggestions([]);
        setInstSearchError(err?.error?.message || 'Unable to query registered institutions. Check network.');
      } finally {
        setIsSearchingInst(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [instQuery, selectedInst]);

  // Click outside to close institution dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (instSearchRef.current && !instSearchRef.current.contains(e.target as Node)) {
        setShowInstDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch paginated directory when browse modal opens or pagination/filter changes
  const loadDirectory = async (page: number, q: string, region: string) => {
    setDirectoryLoading(true);
    setDirectoryError(null);
    try {
      const data = await api.getInstitutionDirectory({
        page,
        limit: 8,
        q: q.trim() || undefined,
        region: region || undefined,
      });
      setDirectoryData(data);
    } catch (err: any) {
      setDirectoryError(err?.error?.message || 'Failed to load institution directory.');
    } finally {
      setDirectoryLoading(false);
    }
  };

  useEffect(() => {
    if (showBrowseModal) {
      loadDirectory(directoryPage, directoryQuery, directoryRegion);
    }
  }, [showBrowseModal, directoryPage, directoryRegion]);

  const handleDirectorySearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setDirectoryPage(1);
    loadDirectory(1, directoryQuery, directoryRegion);
  };

  const handleSelectInstitution = (inst: InstitutionPublicBrief) => {
    setSelectedInst(inst);
    setInstQuery(inst.name);
    setShowInstDropdown(false);
    setInstHighlightIndex(-1);
    if (showBrowseModal) {
      setShowBrowseModal(false);
    }
    // Set demo email if selecting the demo institution
    if (inst.name.toLowerCase().includes('apex') && !email) {
      setEmail('institution@demo.test');
    }
    // Move focus to email or password
    emailInputRef.current?.focus();
  };

  const handleClearInstitution = () => {
    setSelectedInst(null);
    setInstQuery('');
    setInstSuggestions([]);
    setShowInstDropdown(false);
    instInputRef.current?.focus();
  };

  // Keyboard navigation for suggestions dropdown
  const handleInstKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showInstDropdown || instSuggestions.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setInstHighlightIndex((prev) => (prev < instSuggestions.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setInstHighlightIndex((prev) => (prev > 0 ? prev - 1 : instSuggestions.length - 1));
    } else if (e.key === 'Enter') {
      if (instHighlightIndex >= 0 && instHighlightIndex < instSuggestions.length) {
        e.preventDefault();
        handleSelectInstitution(instSuggestions[instHighlightIndex]);
      }
    } else if (e.key === 'Escape') {
      setShowInstDropdown(false);
      setInstHighlightIndex(-1);
    }
  };

  // Handle portal selection card click: switches active form role and moves focus
  const handleSelectRoleCard = (role: RoleChoice) => {
    setActiveRole(role);
    setError(null);
    if (role === 'officer') {
      setEmail('officer@demo.test');
    } else if (role === 'admin') {
      setEmail('admin@demo.test');
    } else if (selectedInst) {
      setEmail('institution@demo.test');
    } else {
      setEmail('');
    }
    // Smooth scroll and focus on authentication board
    authBoardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setTimeout(() => {
      if (role === 'institution' && !selectedInst) {
        instInputRef.current?.focus();
      } else {
        emailInputRef.current?.focus();
      }
    }, 150);
  };

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please provide both email and password.');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err?.error?.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleSignUpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please provide email and password.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters long for Supabase authentication.');
      return;
    }
    setError(null);
    setSuccessMessage(null);
    setLoading(true);
    try {
      const res = await signUp(email, password, {
        full_name: fullName.trim() || undefined,
        role: activeRole,
      });
      if (res.needsEmailConfirmation) {
        setSuccessMessage('Supabase Account created! Check your email to confirm registration before signing in.');
      } else {
        navigate('/dashboard');
      }
    } catch (err: any) {
      setError(err?.message || err?.error?.message || 'Sign up failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickDemo = async (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword('Demo@12345');
    setError(null);
    setLoading(true);
    try {
      await login(demoEmail, 'Demo@12345');
      navigate('/dashboard');
    } catch {
      try {
        await loginWithDemo(demoEmail);
        navigate('/dashboard');
      } catch (err: any) {
        setError(err?.error?.message || 'Login failed. Please verify backend service.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRegistrationSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegError(null);
    setRegSubmitting(true);
    try {
      const res = await api.submitInstitutionRegistrationRequest(regForm);
      setRegSuccess(res);
    } catch (err: any) {
      setRegError(err?.error?.message || 'Failed to submit registration request. Please check inputs.');
    } finally {
      setRegSubmitting(false);
    }
  };

  const isLight = theme === 'light';

  const roleColumns = [
    {
      id: 'institution' as RoleChoice,
      title: 'Technical Institution',
      subtitle: 'Institutional Custodian',
      badge: 'AICTE Custody Portal',
      description:
        'For approved colleges, polytechnics, and universities to deposit mandatory FDRs, track 30/15/7d maturity deadlines, and file renewal instruments.',
      icon: Building,
      accentColor: isLight
        ? 'border-blue-300 text-blue-600 bg-blue-50'
        : 'border-blue-500/50 text-blue-400 bg-blue-500/10',
      activeRing: isLight
        ? 'ring-2 ring-blue-500/80 bg-blue-50/90 border-blue-400 text-blue-950'
        : 'ring-2 ring-blue-500/60 bg-blue-950/30 border-blue-500/80',
      demoEmail: 'institution@demo.test',
      demoLabel: 'Apex Institute (institution@demo.test)',
    },
    {
      id: 'officer' as RoleChoice,
      title: 'Vigilance Directorate',
      subtitle: 'AICTE Inspection Officer',
      badge: 'Regulatory Oversight',
      description:
        'For regional and headquarters vigilance officers to verify FDR receipts against simulated core-banking records, adjudicate discrepancies, and authorize renewals.',
      icon: UserCheck,
      accentColor: isLight
        ? 'border-amber-300 text-amber-700 bg-amber-50'
        : 'border-amber-500/50 text-vault-amber bg-amber-500/10',
      activeRing: isLight
        ? 'ring-2 ring-amber-500/80 bg-amber-50/90 border-amber-400 text-amber-950'
        : 'ring-2 ring-amber-500/60 bg-amber-950/30 border-amber-500/80',
      demoEmail: 'officer@demo.test',
      demoLabel: 'Vigilance Officer (officer@demo.test)',
    },
    {
      id: 'admin' as RoleChoice,
      title: 'Member Secretary Bureau',
      subtitle: 'Sovereign Administrator',
      badge: 'Central AICTE Governance',
      description:
        'For central council administrators to oversee compliance ledgers, verify tamper-evident SHA-256 audit blocks, manage user access, and configure statutory policies.',
      icon: ShieldAlert,
      accentColor: isLight
        ? 'border-emerald-300 text-emerald-700 bg-emerald-50'
        : 'border-emerald-500/50 text-vault-emerald bg-emerald-500/10',
      activeRing: isLight
        ? 'ring-2 ring-emerald-500/80 bg-emerald-50/90 border-emerald-400 text-emerald-950'
        : 'ring-2 ring-emerald-500/60 bg-emerald-950/30 border-emerald-500/80',
      demoEmail: 'admin@demo.test',
      demoLabel: 'Sovereign Admin (admin@demo.test)',
    },
  ];

  return (
    <div className={`min-h-screen flex flex-col justify-between p-4 md:p-8 relative overflow-hidden transition-colors ${
      isLight ? 'bg-slate-50 text-slate-900' : 'bg-vault-950 text-slate-100'
    }`}>
      {/* Top Header Controls: Language & Theme */}
      <header className="flex items-center justify-between w-full max-w-6xl mx-auto z-30 mb-4">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500/20 to-amber-600/5 border border-amber-500/30 flex items-center justify-center text-vault-amber shadow-sm">
            <Shield className="w-4 h-4 fill-amber-500/20 text-vault-amber" />
          </div>
          <div>
            <div className={`text-xs font-bold font-mono tracking-tight flex items-center space-x-1.5 ${
              isLight ? 'text-slate-900' : 'text-slate-100'
            }`}>
              <span>AICTE FDR VAULT</span>
              <span className={`text-[10px] px-1.5 py-0.2 rounded border font-normal ${
                isLight ? 'bg-amber-100 text-amber-800 border-amber-300' : 'bg-amber-500/10 text-vault-amber border-amber-500/30'
              }`}>
                SIH26265
              </span>
            </div>
            <div className={`text-[10px] font-mono ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
              STATUTORY FIXED DEPOSIT LIFECYCLE MANAGEMENT
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {/* Supabase Cloud Connection Status */}
          <div
            className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-xs font-mono border transition shadow ${
              supabaseStatus.connected
                ? isLight ? 'bg-emerald-50 border-emerald-300 text-emerald-800' : 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300'
                : supabaseStatus.checking
                ? isLight ? 'bg-blue-50 border-blue-300 text-blue-800' : 'bg-blue-950/40 border-blue-500/50 text-blue-300'
                : isLight ? 'bg-white border-slate-200 text-slate-700' : 'bg-vault-900 border-vault-800 text-slate-400'
            }`}
            title={supabaseStatus.message}
          >
            <Database className={`w-3.5 h-3.5 ${supabaseStatus.connected ? (isLight ? 'text-emerald-600' : 'text-emerald-400') : 'text-slate-400'}`} />
            <span className="hidden sm:inline">Supabase:</span>
            <span className="font-semibold">
              {supabaseStatus.connected ? 'Connected' : supabaseStatus.checking ? 'Connecting...' : 'Ready'}
            </span>
            {supabaseStatus.connected && (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse ml-0.5" />
            )}
          </div>

          <button
            type="button"
            onClick={toggleLang}
            className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg border text-xs font-mono transition shadow ${
              isLight ? 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100' : 'bg-vault-900 border-vault-800 text-slate-200 hover:text-white'
            }`}
            title="Toggle Language"
            aria-label="Toggle Language"
          >
            <Globe className={`w-3.5 h-3.5 ${isLight ? 'text-amber-700' : 'text-vault-amber'}`} />
            <span className={lang === 'EN' ? (isLight ? 'text-amber-800 font-bold' : 'text-vault-amber font-bold') : (isLight ? 'text-slate-500' : 'text-slate-400')}>EN</span>
            <span className={isLight ? 'text-slate-400' : 'text-slate-500'}>|</span>
            <span className={lang === 'HI' ? (isLight ? 'text-amber-800 font-bold' : 'text-vault-amber font-bold') : (isLight ? 'text-slate-500' : 'text-slate-400')}>हिंदी</span>
          </button>

          <button
            type="button"
            onClick={toggleTheme}
            className={`p-1.5 rounded-lg border transition shadow ${
              isLight ? 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100' : 'bg-vault-900 border-vault-800 text-slate-200 hover:text-white'
            }`}
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
            aria-label={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 text-vault-amber" />
            ) : (
              <Moon className="w-4 h-4 text-slate-700" />
            )}
          </button>
        </div>
      </header>

      {/* Decorative Grid & Glow Background */}
      <div className={`absolute inset-0 bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none transition-opacity ${
        isLight
          ? 'bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f0_1px,transparent_1px)] opacity-50'
          : 'bg-[linear-gradient(to_right,#111622_1px,transparent_1px),linear-gradient(to_bottom,#111622_1px,transparent_1px)] opacity-30'
      }`} />
      <div className={`absolute top-1/6 left-1/2 -translate-x-1/2 w-[650px] h-96 rounded-full blur-3xl pointer-events-none ${
        isLight ? 'bg-amber-400/10' : 'bg-amber-500/10'
      }`} />

      {/* Main Container */}
      <main className="w-full max-w-6xl mx-auto relative z-10 my-auto py-2">
        {/* Header Branding */}
        <div className="text-center mb-6">
          <h1 className={`text-2xl md:text-3xl font-bold tracking-tight ${isLight ? 'text-slate-900' : 'text-slate-100'}`}>
            {t('brand.title')}
          </h1>
          <p className={`text-xs font-mono tracking-widest mt-1 font-semibold ${isLight ? 'text-amber-800' : 'text-vault-amber'}`}>
            {t('brand.subtitle')} · SECURE STATUTORY ACCESS GATEWAY
          </p>
          <p className={`text-xs mt-2 max-w-2xl mx-auto leading-relaxed ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
            Active sign-in form is displayed first. Choose your jurisdiction below if switching roles. User permissions and institutional tenancies are cryptographically verified and enforced server-side.
          </p>
        </div>

        {/* =========================================================================
            ITEM 1: ACTIVE AUTHENTICATION BOARD AT THE TOP OF THE PAGE
            ========================================================================= */}
        <section
          ref={authBoardRef}
          aria-labelledby="active-auth-heading"
          className={`max-w-xl mx-auto rounded-2xl p-6 md:p-8 shadow-xl backdrop-blur-xl relative mb-10 transition-all border ${
            isLight
              ? 'bg-white border-slate-200/90 shadow-slate-200/60'
              : 'bg-vault-900/95 border-vault-800 shadow-2xl'
          }`}
        >
          {/* Active Role Indicator Ribbon */}
          <div className={`flex items-center justify-between pb-4 mb-5 border-b ${isLight ? 'border-slate-200' : 'border-vault-800'}`}>
            <div className="flex items-center space-x-2.5">
              <KeyRound className={`w-4 h-4 ${isLight ? 'text-amber-700' : 'text-vault-amber'}`} />
              <div>
                <h2 id="active-auth-heading" className={`text-sm font-bold font-mono uppercase tracking-wider flex items-center space-x-2 ${
                  isLight ? 'text-slate-900' : 'text-slate-100'
                }`}>
                  <span>
                    {activeRole === 'institution' && 'Institution Portal Authentication'}
                    {activeRole === 'officer' && 'Vigilance Directorate Sign-In'}
                    {activeRole === 'admin' && 'Sovereign Bureau Administration'}
                  </span>
                </h2>
                <div className={`text-[11px] font-sans mt-0.5 ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
                  {activeRole === 'institution' && 'Authorized custodian access for approved technical institutions.'}
                  {activeRole === 'officer' && 'Statutory vigilance review, bank verification, and renewal adjudication.'}
                  {activeRole === 'admin' && 'Central council governance, SHA-256 audit ledger, and policy configuration.'}
                </div>
              </div>
            </div>

            <span
              className={`text-[10px] font-mono px-2.5 py-1 rounded-full font-bold uppercase tracking-wider shrink-0 border ${
                activeRole === 'institution'
                  ? isLight ? 'bg-blue-50 text-blue-800 border-blue-300' : 'bg-blue-500/20 text-blue-300 border-blue-500/40'
                  : activeRole === 'officer'
                  ? isLight ? 'bg-amber-50 text-amber-800 border-amber-300' : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                  : isLight ? 'bg-emerald-50 text-emerald-800 border-emerald-300' : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
              }`}
            >
              ACTIVE ROLE: {activeRole.toUpperCase()}
            </span>
          </div>

          {/* Authentication Mode Tabs: Sign In vs Sign Up */}
          <div className={`flex rounded-xl p-1 border mb-5 ${isLight ? 'bg-slate-100 border-slate-200' : 'bg-vault-950 border-vault-800'}`}>
            <button
              type="button"
              onClick={() => {
                setAuthMode('signin');
                setError(null);
                setSuccessMessage(null);
              }}
              className={`flex-1 py-2 text-xs font-mono font-semibold rounded-lg transition ${
                authMode === 'signin'
                  ? isLight
                    ? 'bg-white text-amber-800 border border-amber-300 shadow-sm font-bold'
                    : 'bg-amber-500/20 text-vault-amber border border-amber-500/30'
                  : isLight
                  ? 'text-slate-600 hover:text-slate-900'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setAuthMode('signup');
                setError(null);
                setSuccessMessage(null);
              }}
              className={`flex-1 py-2 text-xs font-mono font-semibold rounded-lg transition flex items-center justify-center space-x-1.5 ${
                authMode === 'signup'
                  ? isLight
                    ? 'bg-white text-blue-800 border border-blue-300 shadow-sm font-bold'
                    : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                  : isLight
                  ? 'text-slate-600 hover:text-slate-900'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Database className={`w-3.5 h-3.5 ${isLight ? 'text-blue-600' : 'text-blue-400'}`} />
              <span>Sign Up (Supabase Auth)</span>
            </button>
          </div>

          {successMessage && (
            <div role="status" className={`mb-5 p-3 rounded-lg border text-xs font-mono flex items-start space-x-2 ${
              isLight
                ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                : 'bg-emerald-950/60 border-emerald-800/80 text-emerald-300'
            }`}>
              <CheckCircle2 className={`w-4 h-4 shrink-0 mt-0.5 ${isLight ? 'text-emerald-700' : 'text-emerald-400'}`} />
              <span>{successMessage}</span>
            </div>
          )}

          {error && (
            <div role="alert" className={`mb-5 p-3 rounded-lg border text-xs font-mono flex items-start space-x-2 ${
              isLight
                ? 'bg-rose-50 border-rose-300 text-rose-900'
                : 'bg-rose-950/60 border-rose-800/80 text-rose-300'
            }`}>
              <AlertCircle className={`w-4 h-4 shrink-0 mt-0.5 ${isLight ? 'text-rose-700' : 'text-rose-400'}`} />
              <span>{error}</span>
            </div>
          )}

          {/* Autocomplete Institution Type-Ahead Search (Institution Role Only) */}
          {activeRole === 'institution' && (
            <div className="mb-5" ref={instSearchRef}>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="inst-search-input" className={`text-xs font-semibold flex items-center space-x-1.5 ${
                  isLight ? 'text-slate-700' : 'text-slate-300'
                }`}>
                  <span>Search Registered Technical Institution</span>
                  <span className={`text-[11px] font-normal ${isLight ? 'text-slate-500' : 'text-slate-400'}`}>(Database Type-Ahead)</span>
                </label>

                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => {
                      setShowBrowseModal(true);
                      setDirectoryPage(1);
                    }}
                    className={`text-[11px] font-mono transition flex items-center space-x-1 ${
                      isLight ? 'text-amber-800 hover:text-amber-900 font-semibold' : 'text-vault-amber hover:text-amber-300'
                    }`}
                  >
                    <Search className="w-3 h-3" />
                    <span>Browse All</span>
                  </button>
                  <span className={isLight ? 'text-slate-400 text-xs' : 'text-slate-600 text-xs'}>·</span>
                  <button
                    type="button"
                    onClick={() => {
                      setRegSuccess(null);
                      setRegError(null);
                      setShowRegisterModal(true);
                    }}
                    className={`text-[11px] font-mono transition flex items-center space-x-1 ${
                      isLight ? 'text-blue-700 hover:text-blue-800 font-semibold' : 'text-blue-400 hover:text-blue-300'
                    }`}
                  >
                    <PlusCircle className="w-3 h-3" />
                    <span>Request New</span>
                  </button>
                </div>
              </div>

              {/* Selected Institution Pill */}
              {selectedInst ? (
                <div className={`p-3 rounded-lg border flex items-center justify-between ${
                  isLight
                    ? 'bg-blue-50 border-blue-200 text-blue-950'
                    : 'bg-blue-950/40 border-blue-500/50'
                }`}>
                  <div className="space-y-0.5">
                    <div className={`text-xs font-bold flex items-center space-x-2 ${isLight ? 'text-blue-950' : 'text-slate-100'}`}>
                      <Building className={`w-3.5 h-3.5 shrink-0 ${isLight ? 'text-blue-600' : 'text-blue-400'}`} />
                      <span>{selectedInst.name}</span>
                    </div>
                    <div className={`text-[10px] font-mono flex items-center space-x-3 ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
                      <span>AICTE ID: <strong className={isLight ? 'text-slate-900' : 'text-slate-200'}>{selectedInst.aicte_id}</strong></span>
                      <span>Region: {selectedInst.region || 'Northern'}</span>
                      <span className={isLight ? 'text-emerald-700 font-semibold' : 'text-emerald-400 font-semibold'}>✓ Verified Registered Institution</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleClearInstitution}
                    className={`p-1 rounded transition ${
                      isLight ? 'hover:bg-blue-100 text-slate-500 hover:text-slate-800' : 'hover:bg-vault-800 text-slate-400 hover:text-white'
                    }`}
                    title="Change selected institution"
                    aria-label="Change selected institution"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    {isSearchingInst ? (
                      <Loader2 className={`w-4 h-4 animate-spin ${isLight ? 'text-amber-600' : 'text-amber-500'}`} />
                    ) : (
                      <Search className={`w-4 h-4 ${isLight ? 'text-slate-400' : 'text-slate-500'}`} />
                    )}
                  </div>

                  <input
                    id="inst-search-input"
                    ref={instInputRef}
                    type="text"
                    value={instQuery}
                    onChange={(e) => {
                      setInstQuery(e.target.value);
                      if (selectedInst) setSelectedInst(null);
                    }}
                    onKeyDown={handleInstKeyDown}
                    onFocus={() => {
                      if (instSuggestions.length > 0) setShowInstDropdown(true);
                    }}
                    placeholder="Type institution name or permanent AICTE ID (e.g., 'Apex' or '1-4928190')..."
                    className={`w-full pl-9 pr-8 py-2.5 rounded-lg border text-xs focus:outline-none transition font-mono ${
                      isLight
                        ? 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500'
                        : 'bg-vault-950 border-vault-700 text-slate-200 focus:border-blue-500'
                    }`}
                    aria-autocomplete="list"
                    aria-expanded={showInstDropdown}
                    aria-haspopup="listbox"
                  />

                  {instQuery && (
                    <button
                      type="button"
                      onClick={handleClearInstitution}
                      className={`absolute inset-y-0 right-0 pr-3 flex items-center ${
                        isLight ? 'text-slate-400 hover:text-slate-700' : 'text-slate-400 hover:text-white'
                      }`}
                      aria-label="Clear institution search query"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              )}

              {/* Type-Ahead Dropdown Suggestions */}
              {showInstDropdown && !selectedInst && (
                <div
                  role="listbox"
                  aria-label="Institution search suggestions"
                  className={`absolute left-6 right-6 md:left-8 md:right-8 z-50 mt-1 rounded-xl border shadow-2xl overflow-hidden max-h-64 overflow-y-auto ${
                    isLight
                      ? 'bg-white border-slate-200 shadow-slate-300/60'
                      : 'bg-[#0b0e14] border-vault-700'
                  }`}
                >
                  {isSearchingInst ? (
                    <div className={`p-3 text-center text-xs font-mono flex items-center justify-center space-x-2 ${
                      isLight ? 'text-slate-600' : 'text-slate-400'
                    }`}>
                      <Loader2 className={`w-3.5 h-3.5 animate-spin ${isLight ? 'text-amber-700' : 'text-vault-amber'}`} />
                      <span>Querying registered technical institutions...</span>
                    </div>
                  ) : instSearchError ? (
                    <div className={`p-3 text-center text-xs font-mono ${isLight ? 'text-rose-600' : 'text-rose-400'}`}>
                      {instSearchError}
                    </div>
                  ) : instSuggestions.length > 0 ? (
                    <ul className={`divide-y ${isLight ? 'divide-slate-100' : 'divide-vault-800'}`}>
                      {instSuggestions.map((inst, index) => {
                        const isHighlighted = index === instHighlightIndex;
                        return (
                          <li
                            key={inst.id}
                            role="option"
                            aria-selected={isHighlighted}
                            onClick={() => handleSelectInstitution(inst)}
                            onMouseEnter={() => setInstHighlightIndex(index)}
                            className={`p-3 cursor-pointer text-xs transition flex items-center justify-between ${
                              isHighlighted
                                ? isLight ? 'bg-blue-50 text-blue-950 font-medium' : 'bg-vault-800 text-white'
                                : isLight ? 'text-slate-800 hover:bg-slate-50' : 'text-slate-300 hover:bg-vault-850'
                            }`}
                          >
                            <div className="space-y-0.5">
                              <div className={`font-semibold flex items-center space-x-2 ${isLight ? 'text-slate-900' : 'text-slate-100'}`}>
                                <span>{inst.name}</span>
                                {inst.is_synthetic && (
                                  <span className={`text-[9px] px-1.5 py-0.2 rounded border font-mono ${
                                    isLight ? 'bg-amber-100 text-amber-800 border-amber-300' : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                                  }`}>
                                    [DEMO SEED]
                                  </span>
                                )}
                              </div>
                              <div className={`text-[10px] font-mono ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
                                AICTE ID: <span className={isLight ? 'text-slate-900 font-semibold' : 'text-slate-200'}>{inst.aicte_id}</span> · Region: {inst.region || 'Northern'} · Source: {inst.source || 'PORTAL_REGISTRY'}
                              </div>
                            </div>
                            <CheckCircle2 className={`w-4 h-4 shrink-0 ml-2 ${isLight ? 'text-blue-600' : 'text-blue-400'}`} />
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <div className="p-4 text-center text-xs font-mono space-y-2">
                      <div className={`font-semibold ${isLight ? 'text-slate-900' : 'text-slate-300'}`}>No registered institution found</div>
                      <div className={`text-[11px] ${isLight ? 'text-slate-600' : 'text-slate-500'}`}>
                        No catalog matches for &ldquo;{instQuery}&rdquo;.
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setShowInstDropdown(false);
                          setRegForm((prev) => ({ ...prev, institution_name: instQuery }));
                          setRegSuccess(null);
                          setRegError(null);
                          setShowRegisterModal(true);
                        }}
                        className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono transition ${
                          isLight
                            ? 'bg-blue-50 border-blue-300 text-blue-700 hover:bg-blue-100'
                            : 'bg-blue-600/30 border-blue-500/60 text-blue-300 hover:text-white'
                        }`}
                      >
                        <PlusCircle className="w-3.5 h-3.5" />
                        <span>Request Registration for &ldquo;{instQuery}&rdquo;</span>
                      </button>
                    </div>
                  )}

                  {/* Dropdown footer coverage disclaimer */}
                  <div className={`p-2 border-t text-[10px] font-mono flex items-center justify-between ${
                    isLight ? 'bg-slate-50 border-slate-200 text-slate-600' : 'bg-vault-950 border-vault-800 text-slate-500'
                  }`}>
                    <span>Registry Source: Registered Institutions in this Portal</span>
                    <button
                      type="button"
                      onClick={() => {
                        setShowInstDropdown(false);
                        setShowBrowseModal(true);
                      }}
                      className={isLight ? 'text-amber-800 hover:underline font-semibold' : 'text-vault-amber hover:underline'}
                    >
                      Browse full directory →
                    </button>
                  </div>
                </div>
              )}

              {/* Informational security note on tenant assignment */}
              <div className={`mt-1.5 text-[10px] leading-tight ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
                ℹ️ <em>Type-ahead searches registered colleges. User role &amp; institution tenancy are strictly validated against verified database identities.</em>
              </div>
            </div>
          )}

          {/* Secure Email & Password Form */}
          <form onSubmit={authMode === 'signup' ? handleSignUpSubmit : handlePasswordLogin} className="space-y-4">
            {authMode === 'signup' && (
              <div>
                <label htmlFor="auth-fullname-input" className={`block text-xs font-semibold mb-1 ${isLight ? 'text-slate-700' : 'text-slate-300'}`}>
                  Full Name / Authorized Signatory
                </label>
                <input
                  id="auth-fullname-input"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g., Dr. Rajesh Kumar"
                  className={`w-full px-3.5 py-2.5 rounded-lg border text-xs focus:outline-none transition font-mono ${
                    isLight
                      ? 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500'
                      : 'bg-vault-950 border-vault-700 text-slate-200 focus:border-blue-500'
                  }`}
                />
              </div>
            )}

            <div>
              <label htmlFor="auth-email-input" className={`block text-xs font-semibold mb-1 ${isLight ? 'text-slate-700' : 'text-slate-300'}`}>
                {t('auth.email')} <span className="text-rose-500">*</span>
              </label>
              <input
                id="auth-email-input"
                ref={emailInputRef}
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={
                  activeRole === 'institution'
                    ? 'institution@demo.test'
                    : activeRole === 'officer'
                    ? 'officer@demo.test'
                    : 'admin@demo.test'
                }
                className={`w-full px-3.5 py-2.5 rounded-lg border text-xs focus:outline-none transition font-mono ${
                  isLight
                    ? 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-amber-500 focus:ring-1 focus:ring-amber-500'
                    : 'bg-vault-950 border-vault-700 text-slate-200 focus:border-amber-500'
                }`}
              />
            </div>

            <div>
              <label htmlFor="auth-password-input" className={`block text-xs font-semibold mb-1 ${isLight ? 'text-slate-700' : 'text-slate-300'}`}>
                {t('auth.password')} <span className="text-rose-500">*</span>
              </label>
              <input
                id="auth-password-input"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className={`w-full px-3.5 py-2.5 rounded-lg border text-xs focus:outline-none transition font-mono ${
                  isLight
                    ? 'bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-amber-500 focus:ring-1 focus:ring-amber-500'
                    : 'bg-vault-950 border-vault-700 text-slate-200 focus:border-amber-500'
                }`}
              />
              {authMode === 'signup' && (
                <p className={`mt-1 text-[10px] font-mono ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
                  Minimum 6 characters. Will create a user identity in Supabase Auth.
                </p>
              )}
            </div>

            <button
              type="submit"
              disabled={loading}
              className={`w-full py-2.5 px-4 rounded-lg font-bold text-xs tracking-wider uppercase transition shadow-lg flex items-center justify-center space-x-2 disabled:opacity-50 ${
                authMode === 'signup'
                  ? 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-blue-500/20'
                  : 'bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 shadow-amber-500/20'
              }`}
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>{authMode === 'signup' ? 'Creating Supabase Account...' : 'Authenticating...'}</span>
                </>
              ) : (
                <>
                  <Lock className="w-3.5 h-3.5" />
                  <span>{authMode === 'signup' ? 'Create Supabase Account' : t('auth.signInButton')}</span>
                </>
              )}
            </button>
          </form>

          {/* Contextual Helper per mode */}
          {authMode === 'signin' ? (
            <div className={`mt-5 pt-4 border-t ${isLight ? 'border-slate-200' : 'border-vault-800/80'}`}>
              <div className={`text-[10px] font-mono uppercase tracking-wider mb-2 text-center ${
                isLight ? 'text-slate-600 font-semibold' : 'text-slate-400'
              }`}>
                ⚡ Fictional Demo Credentials (Password: <code className={`px-1.5 py-0.5 rounded font-bold ${
                  isLight ? 'bg-amber-100 text-amber-900 border border-amber-300/60' : 'bg-vault-950 text-slate-300'
                }`}>Demo@12345</code>)
              </div>

              <button
                type="button"
                onClick={() => {
                  const target =
                    activeRole === 'institution'
                      ? 'institution@demo.test'
                      : activeRole === 'officer'
                      ? 'officer@demo.test'
                      : 'admin@demo.test';
                  handleQuickDemo(target);
                }}
                disabled={loading}
                className={`w-full p-2.5 rounded-lg border text-xs font-mono transition flex items-center justify-center space-x-2 font-medium ${
                  isLight
                    ? 'bg-amber-50/70 border-amber-300 hover:bg-amber-100 hover:border-amber-400 text-amber-900 shadow-sm'
                    : 'bg-vault-950 border-vault-800 hover:border-amber-500/50 text-slate-300 hover:text-white'
                }`}
              >
                <span>Auto-Fill &amp; Authenticate as {roleColumns.find((c) => c.id === activeRole)?.subtitle}</span>
                <ArrowRight className={`w-3.5 h-3.5 ${isLight ? 'text-amber-700' : 'text-vault-amber'}`} />
              </button>
            </div>
          ) : (
            <div className={`mt-4 p-3 rounded-lg border text-[11px] font-mono ${
              isLight
                ? 'bg-blue-50 border-blue-200 text-blue-900'
                : 'bg-vault-950 border border-vault-800 text-slate-400'
            }`}>
              🛡️ <strong>Supabase Auth Identity:</strong> New accounts register directly into your Supabase project with role <strong>{activeRole.toUpperCase()}</strong>.
            </div>
          )}
        </section>

        {/* =========================================================================
            ITEM 2: THREE PORTAL SELECTION CARDS BELOW THE AUTHENTICATION BOARD
            ORDER: 1. Institution, 2. Officer, 3. Admin
            ========================================================================= */}
        <section aria-labelledby="portal-jurisdictions-heading" className="mb-8">
          <div className="text-center mb-4">
            <h2 id="portal-jurisdictions-heading" className={`text-xs font-mono uppercase tracking-widest font-bold ${
              isLight ? 'text-slate-700' : 'text-slate-400'
            }`}>
              Select Authorized Portal Jurisdiction
            </h2>
            <p className={`text-[11px] mt-0.5 ${isLight ? 'text-slate-600' : 'text-slate-500'}`}>
              Selecting a portal below switches the active authentication form above and moves focus to it.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 lg:gap-6">
            {roleColumns.map((col, index) => {
              const isSelected = activeRole === col.id;
              const Icon = col.icon;
              return (
                <div
                  key={col.id}
                  onClick={() => handleSelectRoleCard(col.id)}
                  className={`p-5 rounded-xl border cursor-pointer transition-all relative flex flex-col justify-between ${
                    isSelected
                      ? `${col.activeRing} shadow-xl ${isLight ? 'shadow-slate-300/50' : 'shadow-black/40'}`
                      : isLight
                      ? 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50 shadow-sm'
                      : 'bg-vault-900/80 border-vault-800 hover:border-vault-700 hover:bg-vault-900/90'
                  }`}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSelectRoleCard(col.id);
                    }
                  }}
                  aria-pressed={isSelected}
                  aria-label={`Select ${col.title} portal (Order ${index + 1}: ${col.id})`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center border ${col.accentColor}`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase tracking-wider ${
                          isSelected
                            ? isLight
                              ? 'bg-amber-100 text-amber-900 border border-amber-300 font-bold'
                              : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                            : isLight
                            ? 'bg-slate-100 text-slate-700 border border-slate-200'
                            : 'bg-vault-950 text-slate-400 border border-vault-800'
                        }`}
                      >
                        {isSelected ? '● ACTIVE WORKBENCH' : col.badge}
                      </span>
                    </div>

                    <div className={`text-[10px] font-mono uppercase tracking-wider mb-1 ${
                      isLight ? 'text-slate-500 font-semibold' : 'text-slate-500'
                    }`}>
                      PORTAL {index + 1} OF 3
                    </div>
                    <h3 className={`text-base font-bold ${isLight ? 'text-slate-900' : 'text-slate-100'}`}>{col.title}</h3>
                    <div className={`text-xs font-mono mb-2 font-medium ${
                      isLight ? 'text-amber-800 font-semibold' : 'text-vault-amber'
                    }`}>{col.subtitle}</div>
                    <p className={`text-xs leading-relaxed font-sans ${
                      isLight ? 'text-slate-600' : 'text-slate-400'
                    }`}>{col.description}</p>
                  </div>

                  <div className={`mt-4 pt-3 border-t flex items-center justify-between text-xs font-mono ${
                    isLight ? 'border-slate-200' : 'border-vault-800/80'
                  }`}>
                    <span className={isSelected ? (isLight ? 'text-amber-800 font-bold' : 'text-amber-400 font-bold') : (isLight ? 'text-slate-500 font-medium' : 'text-slate-500')}>
                      {isSelected ? 'Current Active Form' : 'Click to select role'}
                    </span>
                    <ArrowRight
                      className={`w-4 h-4 transition-transform ${
                        isSelected ? (isLight ? 'text-amber-800 translate-x-1' : 'text-amber-400 translate-x-1') : (isLight ? 'text-slate-400' : 'text-slate-600')
                      }`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Footer info */}
        <footer className="text-center mt-6 text-[11px] font-mono text-slate-500">
          Statutory Compliance Portal · AICTE Regulation 2024-FDR-98 · Certified Sovereign Identity Architecture
        </footer>
      </main>

      {/* =========================================================================
          MODAL 1: BROWSE ALL REGISTERED INSTITUTIONS (PAGINATED DIRECTORY)
          ========================================================================= */}
      {showBrowseModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="browse-directory-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
        >
          <div className={`border rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden ${
            isLight ? 'bg-white border-slate-300 shadow-slate-300/60' : 'bg-[#0b0e14] border-vault-700'
          }`}>
            {/* Modal Header */}
            <div className={`p-5 border-b flex items-center justify-between ${
              isLight ? 'bg-slate-50 border-slate-200' : 'bg-vault-900/60 border-vault-800'
            }`}>
              <div className="flex items-center space-x-2.5">
                <Building className={`w-5 h-5 ${isLight ? 'text-amber-600' : 'text-vault-amber'}`} />
                <div>
                  <h3 id="browse-directory-title" className={`text-sm font-bold font-mono uppercase tracking-wider ${
                    isLight ? 'text-slate-900' : 'text-slate-100'
                  }`}>
                    AICTE Technical Institutions Directory
                  </h3>
                  <p className={`text-[11px] ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
                    Browse registered colleges and technical institutions in this portal.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowBrowseModal(false)}
                className={`p-1.5 rounded-lg transition ${
                  isLight
                    ? 'text-slate-500 hover:text-slate-800 hover:bg-slate-200'
                    : 'text-slate-400 hover:text-white hover:bg-vault-800'
                }`}
                aria-label="Close browse modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Coverage Disclaimer Badge */}
            <div className={`px-5 py-3 border-b text-xs font-mono flex items-start space-x-2 ${
              isLight
                ? 'bg-amber-50 border-amber-200 text-amber-900'
                : 'bg-amber-500/10 border-amber-500/20 text-amber-300'
            }`}>
              <HelpCircle className={`w-4 h-4 shrink-0 mt-0.5 ${isLight ? 'text-amber-700' : 'text-amber-400'}`} />
              <div>
                <strong>Coverage Disclosure:</strong> Showing registered institutions in this portal. National AICTE master directory synchronization is pending official API integration. If your institution is approved but unlisted, please submit a registration request.
              </div>
            </div>

            {/* Filter & Search Bar */}
            <div className={`p-4 border-b ${
              isLight ? 'bg-slate-50/80 border-slate-200' : 'bg-vault-900/40 border-vault-800'
            }`}>
              <form onSubmit={handleDirectorySearchSubmit} className="flex flex-col sm:flex-row gap-2.5">
                <div className="relative flex-1">
                  <Search className={`w-4 h-4 absolute left-3 top-3 pointer-events-none ${
                    isLight ? 'text-slate-400' : 'text-slate-500'
                  }`} />
                  <input
                    type="text"
                    value={directoryQuery}
                    onChange={(e) => setDirectoryQuery(e.target.value)}
                    placeholder="Search by college name or permanent AICTE ID..."
                    className={`w-full pl-9 pr-3 py-2 rounded-lg text-xs font-mono focus:outline-none transition ${
                      isLight
                        ? 'bg-white border border-slate-300 text-slate-900 placeholder-slate-400 focus:border-amber-500 focus:ring-1 focus:ring-amber-500'
                        : 'bg-vault-950 border border-vault-700 text-slate-200 focus:border-amber-500'
                    }`}
                  />
                </div>

                <select
                  value={directoryRegion}
                  onChange={(e) => {
                    setDirectoryRegion(e.target.value);
                    setDirectoryPage(1);
                  }}
                  className={`px-3 py-2 rounded-lg text-xs font-mono focus:outline-none transition ${
                    isLight
                      ? 'bg-white border border-slate-300 text-slate-800 focus:border-amber-500 focus:ring-1 focus:ring-amber-500'
                      : 'bg-vault-950 border border-vault-700 text-slate-200 focus:border-amber-500'
                  }`}
                >
                  <option value="">All AICTE Regions</option>
                  <option value="Northern">Northern Region</option>
                  <option value="North-Western">North-Western Region</option>
                  <option value="South-Western">South-Western Region</option>
                  <option value="Southern">Southern Region</option>
                  <option value="Western">Western Region</option>
                  <option value="Central">Central Region</option>
                  <option value="Eastern">Eastern Region</option>
                </select>

                <button
                  type="submit"
                  className={`px-4 py-2 rounded-lg font-bold text-xs font-mono transition ${
                    isLight
                      ? 'bg-amber-500 hover:bg-amber-600 text-slate-950 shadow-sm'
                      : 'bg-amber-500 hover:bg-amber-400 text-slate-950'
                  }`}
                >
                  Search
                </button>
              </form>
            </div>

            {/* Table / Results Body */}
            <div className={`flex-1 overflow-y-auto p-5 ${isLight ? 'bg-slate-50/40' : ''}`}>
              {directoryLoading ? (
                <div className={`py-16 text-center text-xs font-mono flex flex-col items-center justify-center space-y-2 ${
                  isLight ? 'text-slate-600' : 'text-slate-400'
                }`}>
                  <Loader2 className={`w-6 h-6 animate-spin ${isLight ? 'text-amber-600' : 'text-vault-amber'}`} />
                  <span>Loading institution directory...</span>
                </div>
              ) : directoryError ? (
                <div className={`p-4 rounded-lg border text-xs font-mono text-center ${
                  isLight
                    ? 'bg-rose-50 border-rose-200 text-rose-800'
                    : 'bg-rose-950/60 border border-rose-800 text-rose-300'
                }`}>
                  {directoryError}
                </div>
              ) : directoryData && directoryData.items.length > 0 ? (
                <div className="space-y-3">
                  <div className={`text-[11px] font-mono flex items-center justify-between mb-2 ${
                    isLight ? 'text-slate-600 font-medium' : 'text-slate-400'
                  }`}>
                    <span>Total Registered Institutions: <strong className={isLight ? 'text-slate-900' : 'text-slate-200'}>{directoryData.total}</strong></span>
                    <span>Page {directoryData.page} of {directoryData.pages}</span>
                  </div>

                  <div className={`divide-y rounded-xl border overflow-hidden ${
                    isLight
                      ? 'divide-slate-200 border-slate-200 bg-white shadow-sm'
                      : 'divide-vault-800 border-vault-800 bg-vault-900/60'
                  }`}>
                    {directoryData.items.map((inst) => (
                      <div
                        key={inst.id}
                        className={`p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition ${
                          isLight ? 'hover:bg-amber-50/40' : 'hover:bg-vault-850/60'
                        }`}
                      >
                        <div className="space-y-1">
                          <div className={`font-semibold text-xs flex items-center space-x-2 ${
                            isLight ? 'text-slate-900' : 'text-slate-100'
                          }`}>
                            <span>{inst.name}</span>
                            {inst.is_synthetic && (
                              <span className={`text-[9px] px-1.5 py-0.2 rounded font-mono font-bold ${
                                isLight
                                  ? 'bg-amber-100 border border-amber-300 text-amber-800'
                                  : 'bg-amber-500/10 border border-amber-500/30 text-amber-400'
                              }`}>
                                [DEMO SEED]
                              </span>
                            )}
                          </div>
                          <div className={`text-[10px] font-mono flex flex-wrap gap-x-4 gap-y-1 ${
                            isLight ? 'text-slate-600' : 'text-slate-400'
                          }`}>
                            <span>AICTE ID: <strong className={isLight ? 'text-slate-900' : 'text-slate-200'}>{inst.aicte_id}</strong></span>
                            <span>Region: {inst.region || 'Northern'}</span>
                            <span>Source: {inst.source || 'PORTAL_REGISTRY'}</span>
                            {inst.last_synced_at && (
                              <span>Synced: {new Date(inst.last_synced_at).toLocaleDateString()}</span>
                            )}
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={() => handleSelectInstitution(inst)}
                          className={`self-start sm:self-center px-3 py-1.5 rounded-lg border text-xs font-mono transition flex items-center space-x-1 font-semibold ${
                            isLight
                              ? 'bg-blue-50 border-blue-300 hover:bg-blue-600 hover:text-white text-blue-700 shadow-sm'
                              : 'bg-blue-600/30 border-blue-500/50 hover:bg-blue-600 hover:text-white text-blue-300'
                          }`}
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Select For Sign-In</span>
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className={`py-12 text-center text-xs font-mono space-y-3 ${
                  isLight ? 'text-slate-600' : 'text-slate-400'
                }`}>
                  <div className={`font-semibold text-sm ${isLight ? 'text-slate-800' : 'text-slate-300'}`}>No institutions match your search filter.</div>
                  <p className={`max-w-md mx-auto ${isLight ? 'text-slate-600' : 'text-slate-500'}`}>
                    If your college is approved by AICTE but does not appear in this portal directory, you can file an onboarding request.
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      setShowBrowseModal(false);
                      setRegSuccess(null);
                      setRegError(null);
                      setShowRegisterModal(true);
                    }}
                    className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-bold transition shadow"
                  >
                    <PlusCircle className="w-4 h-4" />
                    <span>Request New Institution Registration</span>
                  </button>
                </div>
              )}
            </div>

            {/* Modal Footer with Pagination Controls */}
            <div className={`p-4 border-t flex items-center justify-between ${
              isLight ? 'bg-slate-50 border-slate-200' : 'bg-vault-900/60 border-vault-800'
            }`}>
              <div className={`text-[11px] font-mono ${isLight ? 'text-slate-600 font-medium' : 'text-slate-500'}`}>
                AICTE SIH26265 Registry Index
              </div>

              {directoryData && directoryData.pages > 1 && (
                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    disabled={directoryPage <= 1 || directoryLoading}
                    onClick={() => setDirectoryPage((p) => Math.max(1, p - 1))}
                    className={`px-2.5 py-1 rounded-md border text-xs disabled:opacity-30 disabled:pointer-events-none transition ${
                      isLight
                        ? 'bg-white border-slate-300 text-slate-700 hover:bg-slate-100 shadow-sm'
                        : 'bg-vault-950 border-vault-700 text-slate-300 hover:text-white'
                    }`}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className={`text-xs font-mono px-2 ${isLight ? 'text-slate-800 font-semibold' : 'text-slate-300'}`}>
                    {directoryPage} / {directoryData.pages}
                  </span>
                  <button
                    type="button"
                    disabled={directoryPage >= directoryData.pages || directoryLoading}
                    onClick={() => setDirectoryPage((p) => Math.min(directoryData.pages, p + 1))}
                    className={`px-2.5 py-1 rounded-md border text-xs disabled:opacity-30 disabled:pointer-events-none transition ${
                      isLight
                        ? 'bg-white border-slate-300 text-slate-700 hover:bg-slate-100 shadow-sm'
                        : 'bg-vault-950 border-vault-700 text-slate-300 hover:text-white'
                    }`}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 2: NEW INSTITUTION ONBOARDING / REGISTRATION REQUEST
          ========================================================================= */}
      {showRegisterModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="register-request-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
        >
          <div className={`border rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden ${
            isLight ? 'bg-white border-slate-300 shadow-slate-300/60' : 'bg-[#0b0e14] border-vault-700'
          }`}>
            {/* Modal Header */}
            <div className={`p-5 border-b flex items-center justify-between ${
              isLight ? 'bg-slate-50 border-slate-200' : 'bg-vault-900/60 border-vault-800'
            }`}>
              <div className="flex items-center space-x-2.5">
                <PlusCircle className={`w-5 h-5 ${isLight ? 'text-blue-600' : 'text-blue-400'}`} />
                <div>
                  <h3 id="register-request-title" className={`text-sm font-bold font-mono uppercase tracking-wider ${
                    isLight ? 'text-slate-900' : 'text-slate-100'
                  }`}>
                    New Institution Registration Request
                  </h3>
                  <p className={`text-[11px] ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
                    Apply to register an uncataloged AICTE approved college or university.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowRegisterModal(false)}
                className={`p-1.5 rounded-lg transition ${
                  isLight
                    ? 'text-slate-500 hover:text-slate-800 hover:bg-slate-200'
                    : 'text-slate-400 hover:text-white hover:bg-vault-800'
                }`}
                aria-label="Close registration modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className={`flex-1 overflow-y-auto p-6 ${isLight ? 'bg-slate-50/30' : ''}`}>
              {regSuccess ? (
                <div className="space-y-4">
                  <div className={`p-4 rounded-xl border space-y-2 ${
                    isLight
                      ? 'bg-emerald-50 border-emerald-300 text-emerald-900'
                      : 'bg-emerald-950/40 border border-emerald-500/50 text-emerald-300'
                  }`}>
                    <div className="flex items-center space-x-2 font-bold text-sm">
                      <CheckCircle2 className={`w-5 h-5 ${isLight ? 'text-emerald-700' : 'text-emerald-400'}`} />
                      <span>Registration Request Filed Successfully</span>
                    </div>
                    <div className="text-xs font-mono">
                      Tracking Reference: <strong className={`px-2 py-0.5 rounded border ${
                        isLight
                          ? 'bg-white text-emerald-900 border-emerald-300'
                          : 'text-white bg-vault-950 border-emerald-500/40'
                      }`}>{regSuccess.tracking_reference}</strong>
                    </div>
                    <div className={`text-xs leading-relaxed font-sans mt-2 ${
                      isLight ? 'text-emerald-950' : 'text-slate-300'
                    }`}>
                      {regSuccess.notice}
                    </div>
                  </div>

                  <div className={`p-4 rounded-xl border text-xs font-mono space-y-1 ${
                    isLight
                      ? 'bg-white border-slate-200 text-slate-700 shadow-sm'
                      : 'bg-vault-900 border border-vault-800 text-slate-400'
                  }`}>
                    <div><strong>Institution Name:</strong> {regSuccess.institution_name}</div>
                    <div><strong>AICTE Permanent ID:</strong> {regSuccess.aicte_id || 'Pending Document Review'}</div>
                    <div><strong>Official Email:</strong> {regSuccess.official_email}</div>
                    <div><strong>Contact Person:</strong> {regSuccess.contact_person}</div>
                    <div><strong>Status:</strong> <span className={`font-bold ${isLight ? 'text-amber-700' : 'text-amber-400'}`}>{regSuccess.status}</span></div>
                  </div>

                  <div className={`p-3 rounded-lg border text-xs font-mono ${
                    isLight
                      ? 'bg-amber-50 border-amber-300 text-amber-950'
                      : 'bg-amber-500/10 border border-amber-500/30 text-amber-300'
                  }`}>
                    🛡️ <strong>Statutory Isolation Policy:</strong> Applicants cannot log in or access FDR instruments until an authorized AICTE Vigilance Officer verifies accreditation documents and approves the institution record.
                  </div>

                  <div className="flex justify-end pt-2">
                    <button
                      type="button"
                      onClick={() => setShowRegisterModal(false)}
                      className={`px-4 py-2 rounded-lg font-bold text-xs font-mono transition ${
                        isLight
                          ? 'bg-amber-500 hover:bg-amber-600 text-slate-950 shadow-sm'
                          : 'bg-amber-500 hover:bg-amber-400 text-slate-950'
                      }`}
                    >
                      Return to Sign-In
                    </button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleRegistrationSubmit} className="space-y-4">
                  {regError && (
                    <div className={`p-3 rounded-lg border text-xs font-mono flex items-start space-x-2 ${
                      isLight
                        ? 'bg-rose-50 border-rose-200 text-rose-800'
                        : 'bg-rose-950/60 border border-rose-800 text-rose-300'
                    }`}>
                      <AlertCircle className={`w-4 h-4 shrink-0 mt-0.5 ${isLight ? 'text-rose-600' : 'text-rose-400'}`} />
                      <span>{regError}</span>
                    </div>
                  )}

                  <div className={`p-3 rounded-lg border text-xs font-mono ${
                    isLight
                      ? 'bg-blue-50/80 border-blue-200 text-blue-900'
                      : 'bg-vault-950 border border-vault-800 text-slate-400'
                  }`}>
                    ℹ️ <em>Requests are verified against authorized AICTE records by an Inspection Officer. Filing a request does NOT grant immediate login access.</em>
                  </div>

                  <div>
                    <label className={`block text-xs font-semibold mb-1 ${
                      isLight ? 'text-slate-800' : 'text-slate-300'
                    }`}>
                      Institution Name <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      minLength={3}
                      value={regForm.institution_name}
                      onChange={(e) => setRegForm({ ...regForm, institution_name: e.target.value })}
                      placeholder="e.g., Delhi Institute of Engineering and Technology"
                      className={`w-full px-3 py-2 rounded-lg text-xs font-mono focus:outline-none transition ${
                        isLight
                          ? 'bg-white border border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-600 focus:ring-1 focus:ring-blue-600'
                          : 'bg-vault-950 border border-vault-700 text-slate-200 focus:border-blue-500'
                      }`}
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className={`block text-xs font-semibold mb-1 ${
                        isLight ? 'text-slate-800' : 'text-slate-300'
                      }`}>
                        AICTE Permanent ID (if known)
                      </label>
                      <input
                        type="text"
                        value={regForm.aicte_id || ''}
                        onChange={(e) => setRegForm({ ...regForm, aicte_id: e.target.value })}
                        placeholder="e.g., 1-4928190 or AICTE-REG-..."
                        className={`w-full px-3 py-2 rounded-lg text-xs font-mono focus:outline-none transition ${
                          isLight
                            ? 'bg-white border border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-600 focus:ring-1 focus:ring-blue-600'
                            : 'bg-vault-950 border border-vault-700 text-slate-200 focus:border-blue-500'
                        }`}
                      />
                    </div>

                    <div>
                      <label className={`block text-xs font-semibold mb-1 ${
                        isLight ? 'text-slate-800' : 'text-slate-300'
                      }`}>
                        AICTE Region <span className="text-rose-500">*</span>
                      </label>
                      <select
                        required
                        value={regForm.region || 'Northern'}
                        onChange={(e) => setRegForm({ ...regForm, region: e.target.value })}
                        className={`w-full px-3 py-2 rounded-lg text-xs font-mono focus:outline-none transition ${
                          isLight
                            ? 'bg-white border border-slate-300 text-slate-800 focus:border-blue-600 focus:ring-1 focus:ring-blue-600'
                            : 'bg-vault-950 border border-vault-700 text-slate-200 focus:border-blue-500'
                        }`}
                      >
                        <option value="Northern">Northern</option>
                        <option value="North-Western">North-Western</option>
                        <option value="South-Western">South-Western</option>
                        <option value="Southern">Southern</option>
                        <option value="Western">Western</option>
                        <option value="Central">Central</option>
                        <option value="Eastern">Eastern</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className={`block text-xs font-semibold mb-1 ${
                        isLight ? 'text-slate-800' : 'text-slate-300'
                      }`}>
                        Contact Person &amp; Designation <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={regForm.contact_person}
                        onChange={(e) => setRegForm({ ...regForm, contact_person: e.target.value })}
                        placeholder="e.g., Dr. Rajesh Kumar, Principal"
                        className={`w-full px-3 py-2 rounded-lg text-xs font-mono focus:outline-none transition ${
                          isLight
                            ? 'bg-white border border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-600 focus:ring-1 focus:ring-blue-600'
                            : 'bg-vault-950 border border-vault-700 text-slate-200 focus:border-blue-500'
                        }`}
                      />
                    </div>

                    <div>
                      <label className={`block text-xs font-semibold mb-1 ${
                        isLight ? 'text-slate-800' : 'text-slate-300'
                      }`}>
                        Official Contact Email <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="email"
                        required
                        value={regForm.official_email}
                        onChange={(e) => setRegForm({ ...regForm, official_email: e.target.value })}
                        placeholder="e.g., registrar@college.edu.in"
                        className={`w-full px-3 py-2 rounded-lg text-xs font-mono focus:outline-none transition ${
                          isLight
                            ? 'bg-white border border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-600 focus:ring-1 focus:ring-blue-600'
                            : 'bg-vault-950 border border-vault-700 text-slate-200 focus:border-blue-500'
                        }`}
                      />
                    </div>
                  </div>

                  <div>
                    <label className={`block text-xs font-semibold mb-1 ${
                      isLight ? 'text-slate-800' : 'text-slate-300'
                    }`}>
                      Campus Address &amp; State
                    </label>
                    <textarea
                      rows={2}
                      value={regForm.address || ''}
                      onChange={(e) => setRegForm({ ...regForm, address: e.target.value })}
                      placeholder="e.g., Knowledge Park Phase II, Greater Noida, Uttar Pradesh - 201306"
                      className={`w-full px-3 py-2 rounded-lg text-xs font-mono focus:outline-none transition ${
                        isLight
                          ? 'bg-white border border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-600 focus:ring-1 focus:ring-blue-600'
                          : 'bg-vault-950 border border-vault-700 text-slate-200 focus:border-blue-500'
                      }`}
                    />
                  </div>

                  <div className={`flex items-center justify-end space-x-3 pt-3 border-t ${
                    isLight ? 'border-slate-200' : 'border-vault-800'
                  }`}>
                    <button
                      type="button"
                      onClick={() => setShowRegisterModal(false)}
                      className={`px-4 py-2 rounded-lg border text-xs font-mono transition ${
                        isLight
                          ? 'bg-white border-slate-300 text-slate-700 hover:bg-slate-100 shadow-sm'
                          : 'bg-vault-900 border border-vault-700 text-slate-300 hover:text-white'
                      }`}
                    >
                      Cancel
                    </button>

                    <button
                      type="submit"
                      disabled={regSubmitting}
                      className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs font-mono transition flex items-center space-x-1.5 shadow disabled:opacity-50"
                    >
                      {regSubmitting ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Submitting Request...</span>
                        </>
                      ) : (
                        <>
                          <Send className="w-3.5 h-3.5" />
                          <span>Submit Registration Request</span>
                        </>
                      )}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
