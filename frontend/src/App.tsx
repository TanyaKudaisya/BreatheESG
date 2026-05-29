import { Routes, Route, Navigate } from 'react-router-dom';
import { Box } from '@mui/material';
import { useCurrentUser } from './hooks/useAuth';

// Lazy-loaded page placeholders — full implementations come in later tasks
import LoginPage from './components/auth/LoginPage';
import DashboardLayout from './components/layout/DashboardLayout';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { data: user, isLoading } = useCurrentUser();

  if (isLoading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="100vh"
      >
        Loading…
      </Box>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
