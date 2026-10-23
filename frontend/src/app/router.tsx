import React from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { MainLayout } from '@/components/layout/MainLayout';
import { LoginPage } from '@/features/auth/LoginPage';
import { OCRIntakeStudio } from '@/features/fdr/OCRIntakeStudio';
import { OfficerVerificationPage } from '@/features/verification/OfficerVerificationPage';
import { DashboardPage } from '@/features/dashboard/DashboardPage';
import { FDRDetailPage } from '@/features/fdr/FDRDetailPage';
import { ReleaseWorkbench } from '@/features/release/ReleaseWorkbench';
import { ReportsPage } from '@/features/reports/ReportsPage';
import { AuditLedgerPage } from '@/features/audit/AuditLedgerPage';
import { useAuth } from '@/features/auth/AuthContext';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-vault-950 flex items-center justify-center font-mono text-xs text-amber-500">
        INITIALIZING SOVEREIGN SESSION...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

const RoleRoute: React.FC<{
  allowedRoles: ('institution' | 'officer' | 'admin')[];
  children: React.ReactNode;
}> = ({ allowedRoles, children }) => {
  const { role, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-vault-950 flex items-center justify-center font-mono text-xs text-amber-500">
        VERIFYING STATUTORY ROLE...
      </div>
    );
  }

  if (role && !allowedRoles.includes(role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <MainLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: 'dashboard',
        element: <DashboardPage />,
      },
      {
        path: 'intake',
        element: <OCRIntakeStudio />,
      },
      {
        path: 'verification',
        element: (
          <RoleRoute allowedRoles={['officer', 'admin']}>
            <OfficerVerificationPage />
          </RoleRoute>
        ),
      },
      {
        path: 'maturity',
        element: <DashboardPage />,
      },
      {
        path: 'release',
        element: <ReleaseWorkbench />,
      },
      {
        path: 'reports',
        element: <ReportsPage />,
      },
      {
        path: 'audit',
        element: (
          <RoleRoute allowedRoles={['officer', 'admin']}>
            <AuditLedgerPage />
          </RoleRoute>
        ),
      },
      {
        path: 'fdrs/:id',
        element: <FDRDetailPage />,
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/dashboard" replace />,
  },
]);
