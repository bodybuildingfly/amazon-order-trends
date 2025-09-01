import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import ThemeToggle from './ThemeToggle';

const LoginPage = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const { login } = useAuth();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);
        
        // --- LOGGING ---
        console.log('[LoginPage] Form submitted. Attempting login for username:', username);

        try {
            await login(username, password);
            // --- LOGGING ---
            console.log('[LoginPage] Login function call completed successfully.');
            // On successful login, the AuthProvider handles state and App.js handles redirect
        } catch (err) {
            // --- LOGGING ---
            console.error('[LoginPage] Login function call failed. Error:', err);
            const errorMessage = err.response?.data?.msg || 'Login failed. Please check your credentials.';
            setError(errorMessage);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="bg-background min-h-screen flex items-center justify-center">
            <div className="bg-surface p-8 rounded-2xl shadow-lg w-full max-w-md mx-4 relative">
                <div className="absolute top-4 right-4">
                    <ThemeToggle />
                </div>
                <h1 className="text-4xl font-bold text-text-primary text-center mb-2">Welcome</h1>
                <p className="text-text-muted text-center mb-8">Please sign in to continue</p>
                
                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label htmlFor="username" className="form-label">Username</label>
                        <input
                            type="text"
                            id="username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                            className="form-input"
                            placeholder="Enter your username"
                        />
                    </div>
                    <div>
                        <label htmlFor="password" className="form-label">Password</label>
                        <input
                            type="password"
                            id="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            className="form-input"
                            placeholder="Enter your password"
                        />
                    </div>

                    {error && (
                        <div className="bg-danger-surface border border-danger text-danger-text px-4 py-3 rounded-lg relative" role="alert">
                            <span className="block sm:inline">{error}</span>
                        </div>
                    )}

                    <div>
                        <button 
                            type="submit" 
                            disabled={isLoading} 
                            className="w-full form-button-primary py-3"
                        >
                            {isLoading ? 'Signing In...' : 'Sign In'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default LoginPage;

