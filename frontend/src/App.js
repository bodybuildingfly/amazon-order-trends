import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// --- Component & Context Imports ---
import Dashboard from './components/Dashboard';
import InteractiveDataTable from './components/InteractiveDataTable';
import RepeatOrdersTable from './components/RepeatOrdersTable';
import LoginPage from './components/LoginPage';
import UserSettingsPage from './components/UserSettingsPage';
import AdminSettingsPage from './components/AdminSettingsPage';
import UserManagementPage from './components/UserManagementPage';
import PriceTrackingPage from './components/PriceTrackingPage';
import MainLayout from './components/MainLayout';
import ProtectedRoute from './components/ProtectedRoute';
import { useAuth } from './context/AuthContext';
import LoadingSpinner from './components/common/LoadingSpinner';

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

                {/* Protected Routes */}
                <Route
                    element={
                        <ProtectedRoute>
                            <MainLayout />
                        </ProtectedRoute>
                    }
                >
                    <Route path="/" element={<Navigate to="/dashboard" replace />} />
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/table" element={<InteractiveDataTable />} />
                    <Route path="/repeat-orders" element={<RepeatOrdersTable />} />
                    <Route path="/price-tracking" element={<PriceTrackingPage />} />
                    <Route path="/settings" element={<UserSettingsPage />} />
                    {user?.role === 'admin' && (
                        <>
                            <Route path="/user-management" element={<UserManagementPage />} />
                            <Route path="/admin-settings" element={<AdminSettingsPage />} />
                        </>
                    )}
                </Route>
            </Routes>
        </>
    );
}

export default App;

