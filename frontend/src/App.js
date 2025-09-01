import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// --- Component & Context Imports ---
import InteractiveDataTable from './components/InteractiveDataTable';
import LoginPage from './components/LoginPage';
import PriceTrendGraph from './components/PriceTrendGraph';
import SettingsPage from './components/SettingsPage';
import MainLayout from './components/MainLayout'; // Import the new layout component
import ProtectedRoute from './components/ProtectedRoute'; // Import the new protected route
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
    const { isAuthenticated, isLoading } = useAuth();
    
    // --- LOGGING ---
    console.log('[App.js] Rendering:', { isAuthenticated, isLoading });

    if (isLoading) {
        console.log('[App.js] Showing loading spinner because isLoading is true.');
        return <LoadingSpinner />;
    }

    return (
        <>
            <ToastContainer theme="colored" position="bottom-right" />
            <Routes>
                {/* If authenticated and trying to access /login, redirect to the main app */}
                <Route
                    path="/login"
                    element={isAuthenticated ? <Navigate to="/" /> : <LoginPage />}
                />

                {/* All other routes are protected */}
                <Route
                    path="/*"
                    element={
                        <ProtectedRoute>
                            <MainLayout>
                                <Routes>
                                    <Route path="/trends" element={<PriceTrendGraph />} />
                                    <Route path="/table" element={<InteractiveDataTable />} />
                                    <Route path="/settings" element={<SettingsPage />} />
                                    {/* Default route inside the main layout */}
                                    <Route path="/" element={<Navigate to="/trends" replace />} />
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

