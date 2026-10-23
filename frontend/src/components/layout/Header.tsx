import React, { useState, useEffect } from 'react';
import { useAuth } from '@/features/auth/AuthContext';
import { useI18n } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { api } from '@/lib/api';
import { DateSimulatorModal } from '@/components/simulation/DateSimulatorModal';
import { NotificationDrawer } from '@/components/notifications/NotificationDrawer';
import {
  Bell,
  Download,
  ShieldAlert,
  Calendar,
  Globe,
  ChevronDown,
  UserCheck,
  Building,
  LogOut,
  Sun,
  Moon,
  Database,
} from 'lucide-react';
import { getSupabaseConfig, checkSupabaseConnection } from '@/lib/supabase';

export const Header: React.FC = () => {
  const { user, role, logout, loginWithDemo } = useAuth();
  const { language, toggleLanguage, t } = useI18n();
  const { theme, toggleTheme } = useTheme();
  const [isRoleDropdownOpen, setIsRoleDropdownOpen] = useState(false);
  const [isSimModalOpen, setIsSimModalOpen] = useState(false);
  const [isNotifDrawerOpen, setIsNotifDrawerOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [effectiveDateStr, setEffectiveDateStr] = useState<string>('Live');
  const [isSimActive, setIsSimActive] = useState<boolean>(false);
  const [isExportingLedger, setIsExportingLedger] = useState(false);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  // Supabase connection state
  const supabaseConfig = getSupabaseConfig();
  const [supabaseConnected, setSupabaseConnected] = useState<boolean>(false);

  useEffect(() => {
    if (supabaseConfig.configured) {
      checkSupabaseConnection().then((res) => setSupabaseConnected(res.connected));
    }
  }, [supabaseConfig.configured]);

  const handleExportLedger = async () => {
    setIsExportingLedger(true);
    setExportNotice(null);
    try {
      await api.downloadReportExcel('all', 'xlsx');
      setExportNotice('AICTE FDR Ledger exported successfully.');
      setTimeout(() => setExportNotice(null), 3500);
    } catch (err: any) {
      alert(err.message || 'Failed to download ledger');
    } finally {
      setIsExportingLedger(false);
    }
  };

  const syncStatus = async () => {
    try {
      const [simData, notifData] = await Promise.all([
        api.getSimulatedDate(),
        api.getNotifications(),
      ]);
      setEffectiveDateStr(simData.effective_date);
      setIsSimActive(simData.is_simulated);
      setUnreadCount(notifData.unread_count);
    } catch {
      // Ignore background error
    }
  };

  useEffect(() => {
    syncStatus();
    const interval = setInterval(syncStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const roleLabels = {
    institution: 'Apex Institute / Custodian',
    officer: 'Vigilance Directorate / New Delhi HQ',
    admin: 'Member Secretary Bureau / Sovereign Admin',
  };

  const handleRoleSwitch = async (email: string) => {
    setIsRoleDropdownOpen(false);
    await loginWithDemo(email);
    syncStatus();
  };

  return (
    <header className="h-14 border-b border-vault-800 bg-vault-950/90 backdrop-blur-md px-6 flex items-center justify-between z-20 sticky top-0">
      {/* Left Badges */}
      <div className="flex items-center space-x-3 text-xs">
        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-vault-900 border border-vault-800 text-slate-300">
          <ShieldAlert className="w-3.5 h-3.5 text-vault-amber" />
          <span className="font-medium tracking-wide">{t('brand.custody')}</span>
        </div>

        <div className="hidden lg:flex items-center space-x-2 px-2.5 py-1 rounded bg-vault-900/60 border border-vault-800 text-slate-400 font-mono text-[11px]">
          <span className="text-slate-500">ADAPTER:</span>
          <span className="text-vault-emerald font-semibold">{t('brand.adapter')}</span>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center space-x-3">
        {exportNotice && (
          <span className="hidden xl:inline text-xs font-mono text-emerald-400 bg-emerald-950/50 border border-emerald-800 px-2 py-1 rounded">
            {exportNotice}
          </span>
        )}

        {/* Dark / Light Mode Toggle */}
        <button
          onClick={toggleTheme}
          className="flex items-center space-x-1 px-2.5 py-1.5 rounded bg-vault-900 border border-vault-800 text-slate-300 hover:text-white transition text-xs font-mono"
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
          aria-label="Toggle dark/light theme"
          aria-pressed={theme === 'light'}
        >
          {theme === 'dark' ? (
            <>
              <Sun className="w-3.5 h-3.5 text-amber-400" />
              <span className="hidden sm:inline text-[11px] text-slate-300">Light</span>
            </>
          ) : (
            <>
              <Moon className="w-3.5 h-3.5 text-indigo-400" />
              <span className="hidden sm:inline text-[11px] text-slate-700">Dark</span>
            </>
          )}
        </button>

        {/* Supabase Connection Indicator */}
        <div
          className={`hidden md:flex items-center space-x-1 px-2.5 py-1.5 rounded border text-xs font-mono transition ${
            supabaseConnected
              ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300'
              : 'bg-vault-900 border-vault-800 text-slate-400'
          }`}
          title={supabaseConnected ? 'Supabase cloud database & auth connected' : 'Connecting to Supabase...'}
        >
          <Database className={`w-3.5 h-3.5 ${supabaseConnected ? 'text-emerald-400' : 'text-slate-400'}`} />
          <span className="text-[11px]">Supabase</span>
          {supabaseConnected && (
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse ml-0.5" />
          )}
        </div>

        {/* Language Toggle (EN | हिंदी) */}
        <button
          onClick={toggleLanguage}
          className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded bg-vault-900 border border-vault-800 text-slate-300 hover:text-white transition text-xs font-mono"
          title="Toggle Language / भाषा बदलें"
          aria-label="Toggle Language"
          aria-pressed={language === 'HI'}
        >
          <Globe className="w-3.5 h-3.5 text-vault-amber" />
          <span className={language === 'EN' ? 'text-vault-amber font-bold' : 'text-slate-400'}>EN</span>
          <span className="text-slate-600">|</span>
          <span className={language === 'HI' ? 'text-vault-amber font-bold' : 'text-slate-400'}>हिंदी</span>
        </button>

        {/* Interactive Simulated Date Badge (Admin/Demo only) */}
        <button
          onClick={() => setIsSimModalOpen(true)}
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded border transition font-mono text-xs ${
            isSimActive
              ? 'bg-amber-950/80 border-amber-600 text-amber-300 hover:bg-amber-900 animate-pulse'
              : 'bg-vault-900 border-vault-800 text-slate-300 hover:text-white hover:border-vault-700'
          }`}
          title="Click to open Maturity & Date Simulator (Simulated Evaluation)"
        >
          <Calendar className="w-3.5 h-3.5 text-vault-amber" />
          <span className="text-slate-400">{isSimActive ? t('brand.sim') : t('brand.eval')}</span>
          <span className="font-semibold text-vault-amber">{effectiveDateStr}</span>
        </button>

        {/* Notification Bell */}
        <button
          onClick={() => setIsNotifDrawerOpen(true)}
          className="relative p-1.5 rounded bg-vault-900 border border-vault-800 text-slate-300 hover:text-white transition"
          title="Open Alerts & Maturity Notices"
          aria-label="Open Alerts & Maturity Notices"
        >
          <Bell className="w-4 h-4 text-slate-300" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 px-1 min-w-[16px] h-4 rounded-full bg-rose-600 text-white font-mono text-[10px] flex items-center justify-center font-bold">
              {unreadCount}
            </span>
          )}
        </button>

        {/* Date Simulator Modal */}
        <DateSimulatorModal
          isOpen={isSimModalOpen}
          onClose={() => setIsSimModalOpen(false)}
          onSimulateSuccess={syncStatus}
        />

        {/* Notifications Drawer */}
        <NotificationDrawer
          isOpen={isNotifDrawerOpen}
          onClose={() => setIsNotifDrawerOpen(false)}
          onUnreadCountChange={setUnreadCount}
        />

        {/* Export Ledger Button */}
        <button
          onClick={handleExportLedger}
          disabled={isExportingLedger}
          title="Download Complete Sovereign FDR Ledger (.xlsx)"
          className="hidden md:flex items-center space-x-1.5 px-2.5 py-1.5 rounded bg-vault-900 hover:bg-vault-850 border border-vault-800 text-slate-300 hover:text-white transition text-xs disabled:opacity-50 font-mono"
        >
          <Download className={`w-3.5 h-3.5 text-vault-amber ${isExportingLedger ? 'animate-bounce' : ''}`} />
          <span>{isExportingLedger ? 'EXPORTING...' : t('brand.exportLedger')}</span>
        </button>

        {/* Role Switcher & User Profile */}
        <div className="relative">
          <button
            onClick={() => setIsRoleDropdownOpen(!isRoleDropdownOpen)}
            className="flex items-center space-x-2 px-3 py-1.5 rounded bg-vault-900 hover:bg-vault-850 border border-vault-700 transition"
          >
            <div className="w-2 h-2 rounded-full bg-vault-emerald animate-pulse" />
            <div className="text-left text-xs">
              <div className="font-semibold text-slate-200">
                {role ? roleLabels[role] : 'AICTE Authority'}
              </div>
              <div className="text-[10px] text-slate-400 font-mono">
                {user?.email || 'officer@demo.test'}
              </div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {/* Quick Demo Switcher Modal */}
          {isRoleDropdownOpen && (
            <div className="absolute right-0 mt-2 w-72 bg-vault-900 border border-vault-700 rounded-lg shadow-2xl p-2 z-50">
              <div className="px-3 py-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wider border-b border-vault-800 mb-1">
                SIH Hackathon Role Switcher
              </div>

              <button
                onClick={() => handleRoleSwitch('institution@demo.test')}
                className="w-full text-left px-3 py-2 rounded hover:bg-vault-800 flex items-center space-x-2.5 transition text-xs"
              >
                <Building className="w-4 h-4 text-blue-400" />
                <div>
                  <div className="font-medium text-slate-200">Institution Custodian</div>
                  <div className="text-[10px] text-slate-400">institution@demo.test</div>
                </div>
              </button>

              <button
                onClick={() => handleRoleSwitch('officer@demo.test')}
                className="w-full text-left px-3 py-2 rounded hover:bg-vault-800 flex items-center space-x-2.5 transition text-xs"
              >
                <UserCheck className="w-4 h-4 text-vault-amber" />
                <div>
                  <div className="font-medium text-slate-200">Vigilance Officer</div>
                  <div className="text-[10px] text-slate-400">officer@demo.test</div>
                </div>
              </button>

              <button
                onClick={() => handleRoleSwitch('admin@demo.test')}
                className="w-full text-left px-3 py-2 rounded hover:bg-vault-800 flex items-center space-x-2.5 transition text-xs"
              >
                <ShieldAlert className="w-4 h-4 text-emerald-400" />
                <div>
                  <div className="font-medium text-slate-200">Sovereign Administrator</div>
                  <div className="text-[10px] text-slate-400">admin@demo.test</div>
                </div>
              </button>

              <div className="border-t border-vault-800 mt-1 pt-1">
                <button
                  onClick={logout}
                  className="w-full text-left px-3 py-1.5 rounded hover:bg-rose-950/40 text-rose-400 flex items-center space-x-2 transition text-xs"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>{t('brand.logout')}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
