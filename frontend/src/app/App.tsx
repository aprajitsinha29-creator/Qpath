// Renders root App component wrapping the router in top-level providers.
import { RouterProvider } from 'react-router-dom';
import { Providers } from './providers';
import { router } from './router';

export function App() {
  return (
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  );
}

export default App;
