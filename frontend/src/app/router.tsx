// Renders application route hierarchy mapping URLs to page views.
import { createBrowserRouter } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { DiagnosticPage } from '../pages/DiagnosticPage';
import { MethodPage } from '../pages/MethodPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { OpportunitiesPage } from '../pages/OpportunitiesPage';
import { PathsPage } from '../pages/PathsPage';
import { PulsePage } from '../pages/PulsePage';
import { ResultsPage } from '../pages/ResultsPage';
import { SubfieldDetailPage } from '../pages/SubfieldDetailPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      {
        index: true,
        element: <PulsePage />,
      },
      {
        path: 'pulse',
        element: <PulsePage />,
      },
      {
        path: 'pulse/:subfieldId',
        element: <SubfieldDetailPage />,
      },
      {
        path: 'diagnostic',
        element: <DiagnosticPage />,
      },
      {
        path: 'diagnostic/results',
        element: <ResultsPage />,
      },
      {
        path: 'paths',
        element: <PathsPage />,
      },
      {
        path: 'opportunities',
        element: <OpportunitiesPage />,
      },
      {
        path: 'method',
        element: <MethodPage />,
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
]);
