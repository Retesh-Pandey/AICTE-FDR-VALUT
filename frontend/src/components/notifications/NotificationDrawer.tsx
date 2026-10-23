import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { api, NotificationItem } from '@/lib/api';
import { Bell, CheckCheck, ExternalLink, X, AlertTriangle, RefreshCw } from 'lucide-react';

interface NotificationDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onUnreadCountChange?: (count: number) => void;
}

export const NotificationDrawer: React.FC<NotificationDrawerProps> = ({
  isOpen,
  onClose,
  onUnreadCountChange,
}) => {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<'all' | 'unread'>('all');

  const fetchNotifications = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getNotifications();
      setNotifications(data.items);
      setUnreadCount(data.unread_count);
      if (onUnreadCountChange) {
        onUnreadCountChange(data.unread_count);
      }
    } catch (err: any) {
      setError(err?.error?.message || 'Failed to load lifecycle telemetry alerts.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchNotifications();
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const handleMarkAsRead = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n))
      );
      setUnreadCount((c) => {
        const next = Math.max(0, c - 1);
        if (onUnreadCountChange) onUnreadCountChange(next);
        return next;
      });
    } catch {
      // Ignore network error on single mark
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markAllNotificationsRead();
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, read_at: new Date().toISOString() }))
      );
      setUnreadCount(0);
      if (onUnreadCountChange) {
        onUnreadCountChange(0);
      }
    } catch {
      // Ignore error
    }
  };

  const getBadgeForType = (type: string) => {
    switch (type) {
      case 'maturity_30':
        return (
          <span className="px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 text-[10px] font-mono">
            30-DAY NOTICE
          </span>
        );
      case 'maturity_15':
        return (
          <span className="px-1.5 py-0.5 rounded bg-orange-950 text-orange-300 border border-orange-800 text-[10px] font-mono">
            RENEWAL DUE (15D)
          </span>
        );
      case 'maturity_7':
        return (
          <span className="px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 text-[10px] font-mono font-bold animate-pulse">
            CRITICAL EXPIRY (7D)
          </span>
        );
      case 'matured':
        return (
          <span className="px-1.5 py-0.5 rounded bg-red-950 text-red-200 border border-red-800 text-[10px] font-mono font-bold">
            MATURED DEPOSIT
          </span>
        );
      case 'workflow':
        return (
          <span className="px-1.5 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800 text-[10px] font-mono">
            WORKFLOW
          </span>
        );
      default:
        return (
          <span className="px-1.5 py-0.5 rounded bg-vault-900 text-slate-400 border border-vault-800 text-[10px] font-mono">
            SYSTEM
          </span>
        );
    }
  };

  if (!isOpen) return null;

  const displayedNotifications =
    filterMode === 'unread'
      ? notifications.filter((n) => !n.read_at)
      : notifications;

  return createPortal(
    <div
      onClick={onClose}
      className="fixed inset-0 z-[100] flex justify-end bg-black/60 backdrop-blur-sm transition-opacity"
      role="dialog"
      aria-modal="true"
      aria-label="Lifecycle Telemetry Alerts"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-[#0b0e14] border-l border-vault-800 w-full sm:max-w-md max-w-full h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-200 overflow-hidden"
      >
        {/* Drawer Header */}
        <div className="p-4 border-b border-vault-800 flex items-center justify-between bg-vault-900/80 shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded bg-vault-800 border border-vault-700 text-amber-400">
              <Bell className="w-4 h-4" />
            </div>
            <div>
              <div className="font-bold text-sm text-slate-100 flex items-center space-x-2">
                <span>Lifecycle Telemetry Alerts</span>
                {unreadCount > 0 && (
                  <span className="px-2 py-0.2 rounded-full bg-rose-600 text-white text-[10px] font-mono font-bold">
                    {unreadCount} NEW
                  </span>
                )}
              </div>
              <div className="text-[11px] text-slate-400">
                Institutional maturity notifications &amp; workflow updates
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-vault-800 transition"
            aria-label="Close Alerts Drawer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Action & Filter Bar */}
        <div className="px-4 py-2 border-b border-vault-800/80 bg-vault-950/60 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center space-x-1" role="tablist" aria-label="Alert Filters">
            <button
              role="tab"
              aria-selected={filterMode === 'all'}
              onClick={() => setFilterMode('all')}
              className={`px-2 py-1 rounded text-[11px] font-mono transition ${
                filterMode === 'all'
                  ? 'bg-vault-800 text-vault-amber font-semibold border border-vault-700'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All ({notifications.length})
            </button>
            <button
              role="tab"
              aria-selected={filterMode === 'unread'}
              onClick={() => setFilterMode('unread')}
              className={`px-2 py-1 rounded text-[11px] font-mono transition ${
                filterMode === 'unread'
                  ? 'bg-vault-800 text-vault-amber font-semibold border border-vault-700'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Unread ({unreadCount})
            </button>
          </div>

          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="text-amber-400 hover:text-amber-300 font-semibold flex items-center space-x-1 text-[11px]"
            >
              <CheckCheck className="w-3.5 h-3.5" />
              <span>Mark all as read</span>
            </button>
          )}
        </div>

        {/* Notifications List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
          {isLoading && (
            <div className="py-16 text-center text-xs text-slate-400 font-mono space-y-2">
              <RefreshCw className="w-6 h-6 mx-auto animate-spin text-amber-500" />
              <div>Retrieving telemetry alerts...</div>
            </div>
          )}

          {error && !isLoading && (
            <div className="py-12 px-4 text-center space-y-3">
              <AlertTriangle className="w-8 h-8 mx-auto text-rose-500" />
              <div className="text-xs text-rose-300 font-mono">{error}</div>
              <button
                onClick={fetchNotifications}
                className="px-3 py-1.5 rounded bg-vault-800 hover:bg-vault-750 border border-vault-700 text-xs font-mono text-slate-200 transition"
              >
                Retry Loading
              </button>
            </div>
          )}

          {!isLoading && !error && displayedNotifications.length === 0 && (
            <div className="py-16 text-center text-slate-400 space-y-2">
              <CheckCheck className="w-8 h-8 mx-auto text-slate-600" />
              <div className="text-xs font-semibold text-slate-300">
                {filterMode === 'unread' ? 'No Unread Alerts' : 'All Clear'}
              </div>
              <div className="text-[11px] text-slate-400">
                {filterMode === 'unread'
                  ? 'All notifications have been reviewed and marked as read.'
                  : 'No active alerts or maturity notices pending.'}
              </div>
            </div>
          )}

          {!isLoading &&
            !error &&
            displayedNotifications.map((item) => {
              const isUnread = !item.read_at;
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    if (item.fdr_id) {
                      navigate(`/fdrs/${item.fdr_id}`);
                      onClose();
                    }
                  }}
                  className={`p-3 rounded-lg border transition cursor-pointer relative ${
                    isUnread
                      ? 'bg-vault-900/90 border-amber-500/40 hover:border-amber-500 shadow-sm'
                      : 'bg-vault-950/70 border-vault-800 hover:border-vault-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center space-x-2">
                      {getBadgeForType(item.type)}
                      <span className="text-[10px] text-slate-400 font-mono">
                        {new Date(item.created_at).toLocaleDateString('en-IN', {
                          day: '2-digit',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>

                    <span
                      className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                        isUnread
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {isUnread ? 'UNREAD' : 'READ'}
                    </span>
                  </div>

                  <p className="text-xs text-slate-200 leading-relaxed font-sans break-words">
                    {item.message}
                  </p>

                  <div className="flex items-center justify-between mt-2.5 pt-2 border-t border-vault-800/60 text-[10px] text-slate-400 font-mono">
                    {item.fdr_id ? (
                      <span className="text-amber-400 flex items-center space-x-1 hover:underline">
                        <span>FDR Ref: {item.fdr_id.slice(0, 8)}...</span>
                        <ExternalLink className="w-3 h-3" />
                      </span>
                    ) : (
                      <span className="text-slate-500">System Notification</span>
                    )}

                    {isUnread && (
                      <button
                        onClick={(e) => handleMarkAsRead(item.id, e)}
                        className="text-amber-400/90 hover:text-amber-300 underline font-sans text-[11px]"
                      >
                        Mark as read
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
        </div>
      </div>
    </div>,
    document.body
  );
};
