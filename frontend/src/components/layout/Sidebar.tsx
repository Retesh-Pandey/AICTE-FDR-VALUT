import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Shield,
  Layers,
  ScanLine,
  CheckCircle2,
  Clock,
  Lock,
  FileCheck2,
  FileSpreadsheet,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '@/features/auth/AuthContext';
import { useI18n } from '@/lib/i18n';

export const Sidebar: React.FC = () => {
  const { role } = useAuth();
  const { t } = useI18n();

  const navItems = [
    {
      to: '/dashboard',
      label: t('nav.repository'),
      icon: Layers,
      allowedRoles: ['institution', 'officer', 'admin'],
    },
    {
      to: '/intake',
      label: t('nav.intake'),
      icon: ScanLine,
      allowedRoles: ['institution', 'officer', 'admin'],
      highlight: true,
    },
    {
      to: '/verification',
      label: t('nav.verification'),
      icon: CheckCircle2,
      allowedRoles: ['officer', 'admin'],
    },
    {
      to: '/maturity',
      label: t('nav.maturity'),
      icon: Clock,
      badge: '30/15/7d',
      allowedRoles: ['institution', 'officer', 'admin'],
    },
    {
      to: '/release',
      label: t('nav.release'),
      icon: Lock,
      allowedRoles: ['institution', 'officer', 'admin'],
    },
    {
      to: '/reports',
      label: t('nav.reports'),
      icon: FileSpreadsheet,
      allowedRoles: ['institution', 'officer', 'admin'],
    },
    {
      to: '/audit',
      label: t('nav.audit'),
      icon: FileCheck2,
      allowedRoles: ['officer', 'admin'],
    },
  ];

  return (
    <aside className="w-64 bg-vault-950 border-r border-vault-800 flex flex-col justify-between h-screen sticky top-0 shrink-0">
      {/* Top Brand Section */}
      <div>
        <div className="p-5 border-b border-vault-800">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-500/20 to-amber-600/10 border border-amber-500/40 flex items-center justify-center text-vault-amber shadow-lg shadow-amber-500/10">
              <Shield className="w-5 h-5 fill-amber-500/20 text-vault-amber" />
            </div>
            <div>
              <div className="font-bold text-sm tracking-wide text-slate-100 flex items-center space-x-1.5">
                <span>{t('brand.title')}</span>
              </div>
              <div className="text-[10px] font-mono text-vault-amber tracking-wider font-semibold">
                {t('brand.subtitle')}
              </div>
            </div>
          </div>
        </div>

        {/* Node Ledger Sync Telemetry Badge */}
        <div className="px-4 py-3 border-b border-vault-800/80 bg-vault-900/40 flex items-center justify-between text-xs font-mono">
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-vault-emerald shadow-[0_0_8px_#10b981]" />
            <span className="text-slate-300 text-[11px] font-medium">{t('brand.nodeLedger')}</span>
          </div>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950/60 text-vault-emerald border border-emerald-800/60 font-semibold">
            SHA-256 OK
          </span>
        </div>

        {/* Navigation Items */}
        <nav className="p-3 space-y-1.5">
          {navItems.map((item) => {
            const hasAccess = !role || item.allowedRoles.includes(role);
            if (!hasAccess) return null;

            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center justify-between px-3 py-2.5 rounded-md text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-black font-semibold shadow-md shadow-amber-500/20'
                      : 'text-slate-300 hover:text-white hover:bg-vault-900/80 border border-transparent hover:border-vault-800'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <div className="flex items-center space-x-3">
                      <item.icon
                        className={`w-4 h-4 ${
                          isActive ? 'text-black' : item.highlight ? 'text-vault-amber' : 'text-slate-400'
                        }`}
                      />
                      <span>{item.label}</span>
                    </div>

                    {item.badge && (
                      <span
                        className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-bold ${
                          isActive
                            ? 'bg-black/20 text-black'
                            : 'bg-rose-950/60 text-rose-300 border border-rose-800/50'
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Bottom Protocol Parity Box */}
      <div className="p-4 border-t border-vault-800 bg-vault-950/80">
        <div className="p-3 rounded-lg bg-vault-900/70 border border-vault-800 flex items-center justify-between">
          <div className="text-left font-mono">
            <div className="text-[10px] text-slate-400 uppercase tracking-wider">{t('brand.chainParity')}</div>
            <div className="text-xs font-semibold text-slate-200">0x7f4a...e89b</div>
          </div>
          <div className="w-6 h-6 rounded-full bg-emerald-950/70 border border-emerald-600/40 flex items-center justify-center text-vault-emerald">
            <ShieldCheck className="w-3.5 h-3.5" />
          </div>
        </div>
        <div className="mt-2 text-center text-[10px] font-mono text-slate-400 tracking-wider">
          {t('brand.protocol')}
        </div>
      </div>
    </aside>
  );
};
