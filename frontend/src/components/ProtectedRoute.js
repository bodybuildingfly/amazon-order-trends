import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/**
 * @description A component that acts as a gatekeeper for routes.
 * If the user is authenticated, it renders the child components.
 * Otherwise, it redirects them to the login page.
 */
const ProtectedRoute = ({ children }) => {
    const { isAuthenticated } = useAuth();

    if (!isAuthenticated) {
        // Redirect them to the /login page, but save the current location they were
        // trying to go to. This allows us to send them along to that page after they login.
        return <Navigate to="/login" replace />;
    }

    return children;
};

export default ProtectedRoute;

