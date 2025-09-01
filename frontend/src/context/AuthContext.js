import React, { createContext, useState, useContext, useEffect, useCallback, useMemo } from 'react';
import { jwtDecode } from 'jwt-decode';
import apiClient from '../api';

const AuthContext = createContext(null);

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    const logout = useCallback(() => {
        setUser(null);
        localStorage.removeItem('userInfo');
        delete apiClient.defaults.headers.common['Authorization'];
    }, []);

    useEffect(() => {
        try {
            const storedUser = localStorage.getItem('userInfo');
            if (storedUser) {
                const userData = JSON.parse(storedUser);
                const decodedToken = jwtDecode(userData.token);
                if (decodedToken.exp * 1000 > Date.now()) {
                    apiClient.defaults.headers.common['Authorization'] = `Bearer ${userData.token}`;
                    setUser(userData);
                } else {
                    logout(); // Token is expired
                }
            }
        } catch (error) {
            console.error("Failed to initialize auth state:", error);
            logout();
        }
        setIsLoading(false);
    }, [logout]);

    const login = useCallback(async (username, password) => {
        try {
            const { data } = await apiClient.post('/api/auth/login', { username, password });
            if (data && data.token) {
                // Pass the raw token to the user object for the EventSource URL
                const userData = { ...data, username, token: data.token }; 
                localStorage.setItem('userInfo', JSON.stringify(userData));
                apiClient.defaults.headers.common['Authorization'] = `Bearer ${userData.token}`;
                setUser(userData);
            }
        } catch (error) {
            throw error;
        }
    }, []);

    const value = useMemo(() => ({
        user,
        isAuthenticated: !!user,
        isAdmin: user?.role === 'admin',
        isLoading,
        login,
        logout,
    }), [user, isLoading, login, logout]);

    return (
        <AuthContext.Provider value={value}>
            {!isLoading && children}
        </AuthContext.Provider>
    );
};

