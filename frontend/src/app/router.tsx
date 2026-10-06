// Renders application route hierarchy mapping URLs to page views.
import { createBrowserRouter } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { MethodPage } from '../pages/MethodPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { PulsePage } from '../pages/PulsePage';
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
