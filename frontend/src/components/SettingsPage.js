import React, { useState, useEffect, useRef } from 'react';
import { toast } from 'react-toastify';
import apiClient from '../api';
import { useAuth } from '../context/AuthContext';

// --- Helper Components ---
const Spinner = () => <div className="flex justify-center items-center p-10"><div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div></div>;

const SettingsPage = () => {
    // --- State Management ---
    const { user } = useAuth();
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isConfigured, setIsConfigured] = useState(false);
    const [logoutOutput, setLogoutOutput] = useState('');
    const [importDays, setImportDays] = useState(60);

    const [isImporting, setIsImporting] = useState(false);
    const [importStatus, setImportStatus] = useState('');
    const [importProgress, setImportProgress] = useState({ value: 0, max: 100 });

    const [formData, setFormData] = useState({
        amazon_email: '',
        amazon_password: '',
        amazon_otp_secret_key: '',
    });
    
    const eventSourceRef = useRef(null);

    // --- Data Fetching ---
    useEffect(() => {
        const fetchSettings = async () => {
            setIsLoading(true);
            try {
                const { data } = await apiClient.get('/api/settings');
                setFormData(prev => ({
                    ...prev,
                    amazon_email: data.amazon_email,
                    amazon_otp_secret_key: data.amazon_otp_secret_key,
                }));
                setIsConfigured(data.is_configured);
            } catch (err) {
                toast.error('Failed to load settings.');
            }
            setIsLoading(false);
        };
        fetchSettings();
    }, []);
    
    useEffect(() => {
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
            }
        };
    }, []);

    // --- Event Handlers ---
    const handleFormChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSaveSettings = async (e) => {
        e.preventDefault();
        setIsSaving(true);
        try {
            const { data } = await apiClient.post('/api/settings', formData);
            toast.success(data.message);
            setFormData(prev => ({ ...prev, amazon_password: '' }));
            const settingsRes = await apiClient.get('/api/settings');
            setIsConfigured(settingsRes.data.is_configured);
        } catch (err) {
            toast.error(err.response?.data?.error || 'Failed to save settings.');
        }
        setIsSaving(false);
    };

    const handleRunIngestion = () => {
        if (!user?.token) {
            toast.error("Authentication token not found. Please log in again.");
            return;
        }

        setIsImporting(true);
        setImportStatus('Connecting to server...');
        setImportProgress({ value: 0, max: 100 });

        const baseUrl = process.env.NODE_ENV === 'production'
            ? ''
            : 'http://localhost:5001';
        const url = `${baseUrl}/api/ingestion/run?days=${importDays}&token=${user.token}`;
        const eventSource = new EventSource(url);
        eventSourceRef.current = eventSource;

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const { type, payload } = data;

            if (type === 'status') {
                setImportStatus(payload);
            } else if (type === 'progress') {
                setImportProgress(payload);
            } else if (type === 'error') {
                toast.error(payload);
                setImportStatus(`Error: ${payload}`);
                eventSource.close();
                setIsImporting(false);
            } else if (type === 'done') {
                setIsImporting(false);
                eventSource.close();
            }
        };

        eventSource.onerror = () => {
            toast.error("Connection to server failed. Data import stopped.");
            setIsImporting(false);
            setImportStatus('Connection Error. Please try again.');
            eventSource.close();
        };
    };
    
    const handleForceLogout = async () => {
        setLogoutOutput('Executing command...');
        try {
            const { data } = await apiClient.post('/api/amazon-logout');
            setLogoutOutput(data.output || data.message);
        } catch (err) {
            setLogoutOutput(err.response?.data?.error || 'Failed to execute command.');
        }
    };

    if (isLoading) return <Spinner />;

    return (
        <div className="space-y-8 max-w-3xl mx-auto">
            <div className="bg-surface p-6 rounded-2xl shadow-lg">
                <h2 className="text-3xl font-semibold text-text-primary mb-6">Application Settings</h2>
                <form onSubmit={handleSaveSettings} className="space-y-6">
                    <div>
                        <label htmlFor="amazon_email" className="form-label">Amazon Email</label>
                        <input type="email" name="amazon_email" id="amazon_email" value={formData.amazon_email} onChange={handleFormChange} className="form-input" required />
                    </div>
                    <div>
                        <label htmlFor="amazon_password" className="form-label">Amazon Password</label>
                        <input type="password" name="amazon_password" id="amazon_password" value={formData.amazon_password} onChange={handleFormChange} className="form-input" placeholder={isConfigured ? 'Enter new password to update' : 'Required'} />
                    </div>
                    <div>
                        <label htmlFor="amazon_otp_secret_key" className="form-label">2FA Secret Key (Optional)</label>
                        <input type="text" name="amazon_otp_secret_key" id="amazon_otp_secret_key" value={formData.amazon_otp_secret_key} onChange={handleFormChange} className="form-input" />
                    </div>
                    <div className="flex justify-end">
                        <button type="submit" disabled={isSaving} className="form-button-primary">
                            {isSaving ? 'Saving...' : 'Save Settings'}
                        </button>
                    </div>
                </form>
            </div>
            <div className="bg-surface p-6 rounded-2xl shadow-lg">
                <h3 className="font-semibold text-lg mb-2">Manual Data Import</h3>
                <p className="text-sm text-text-muted mb-4">
                    Import your recent order history. This may take several minutes.
                </p>
                <div className="flex items-center gap-4 mb-4">
                    <input
                        type="number"
                        value={importDays}
                        onChange={(e) => setImportDays(parseInt(e.target.value, 10) || 1)}
                        className="form-input w-24 text-center"
                        min="1"
                        max="365"
                        disabled={isImporting}
                    />
                    <span className="text-text-secondary">days</span>
                    <button 
                        type="button" 
                        onClick={handleRunIngestion} 
                        disabled={isImporting || !isConfigured} 
                        className="form-button-secondary"
                        title={!isConfigured ? 'Please save your settings first' : ''}
                    >
                        {isImporting ? 'Importing...' : 'Run Manual Import'}
                    </button>
                </div>
                {isImporting && (
                    <div className="space-y-2 pt-4 border-t border-border-color">
                        <p className="text-sm font-medium text-text-secondary">{importStatus}</p>
                        <progress 
                            value={importProgress.value} 
                            max={importProgress.max} 
                            className="w-full h-2 rounded-full [&::-webkit-progress-bar]:bg-surface-muted [&::-webkit-progress-value]:bg-primary [&::-moz-progress-bar]:bg-primary"
                        >
                            {importProgress.value}%
                        </progress>
                    </div>
                )}
            </div>
            <div className="bg-surface p-6 rounded-2xl shadow-lg">
                <h3 className="font-semibold text-lg mb-2">Troubleshooting</h3>
                <p className="text-sm text-text-muted mb-4">
                    If you are having trouble loading orders, force a logout of the Amazon session on the server.
                </p>
                <button onClick={handleForceLogout} className="form-button-secondary bg-warning-surface text-warning-text-on-surface hover:bg-warning-surface-hover">
                    Force Amazon Session Logout
                </button>
                {logoutOutput && (
                    <pre className="mt-4 p-4 bg-surface-muted rounded-lg text-xs overflow-x-auto">
                        {logoutOutput}
                    </pre>
                )}
            </div>
        </div>
    );
};

export default SettingsPage;

