import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { DashboardPage } from '@/pages/DashboardPage';
import { IssuersPage } from '@/pages/IssuersPage';
import { CredentialIssuancePage } from '@/pages/CredentialIssuancePage';
import { CredentialDetailsPage } from '@/pages/CredentialDetailsPage';
import { VerificationPage } from '@/pages/VerificationPage';
import { SelectiveDisclosurePage } from '@/pages/SelectiveDisclosurePage';
import { StoredDocumentsPage } from '@/pages/StoredDocumentsPage';
import { HolderWalletPage } from '@/pages/HolderWalletPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <DashboardPage />,
      },
      {
        path: 'wallet',
        element: <HolderWalletPage />,
      },
      {
        path: 'holder',
        element: <HolderWalletPage />,
      },
      {
        path: 'issuers',
        element: <IssuersPage />,
      },
      {
        path: 'credentials',
        element: <CredentialDetailsPage />,
      },
      {
        path: 'credentials/issue',
        element: <CredentialIssuancePage />,
      },
      {
        path: 'verify',
        element: <VerificationPage />,
      },
      {
        path: 'presentations',
        element: <SelectiveDisclosurePage />,
      },
      {
        path: 'documents',
        element: <StoredDocumentsPage />,
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
]);
