import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// --- Component & Context Imports ---
import InteractiveDataTable from './components/InteractiveDataTable';
import RepeatOrdersTable from './components/RepeatOrdersTable'; // Import the new component
import LoginPage from './components/LoginPage';
import SettingsPage from './components/SettingsPage';
import UserManagementPage from './components/UserManagementPage';
import MainLayout from './components/MainLayout';
import ProtectedRoute from './components/ProtectedRoute';
import { useAuth } from './context/AuthContext';

// --- Helper Components ---
const LoadingSpinner = () => (
    <div className="flex h-screen w-screen items-center justify-center bg-background">
        <div className="w-16 h-16 border-8 border-primary border-t-transparent rounded-full animate-spin"></div>
    </div>
);

/**
 * @description The root component that handles routing.
 */
function App() {
    const { isAuthenticated, isLoading, user } = useAuth();

    if (isLoading) {
        return <LoadingSpinner />;
    }

    return (
        <>
            <ToastContainer theme="colored" position="bottom-right" />
            <Routes>
                <Route
                    path="/login"
                    element={isAuthenticated ? <Navigate to="/" /> : <LoginPage />}
                />
                <Route
                    path="/*"
                    element={
                        <ProtectedRoute>
                            <MainLayout>
                                <Routes>
                                    <Route path="/table" element={<InteractiveDataTable />} />
                                    <Route path="/repeat-orders" element={<RepeatOrdersTable />} />
                                    <Route path="/settings" element={<SettingsPage />} />
                                    {user?.role === 'admin' && (
                                        <Route path="/user-management" element={<UserManagementPage />} />
                                    )}
                                    {/* Default route inside the main layout */}
                                    <Route path="/" element={<Navigate to="/table" replace />} />
                                </Routes>
                            </MainLayout>
                        </ProtectedRoute>
                    }
                />
            </Routes>
        </>
    );
}

export default App;

