import React, { useState, useEffect, useRef, useCallback } from 'react';
import { toast } from 'react-toastify';
import apiClient from '../api';

const Spinner = () => <div className="flex justify-center items-center p-10"><div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div></div>;

// Custom hook to get the previous value of a prop or state.
function usePrevious(value) {
    const ref = useRef();
    useEffect(() => {
        ref.current = value;
    });
    return ref.current;
}

const UserSettingsPage = () => {
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isConfigured, setIsConfigured] = useState(false);
    const [logoutOutput, setLogoutOutput] = useState('');
    const [importDays, setImportDays] = useState(60);
    
    // State for the import job
    const [jobDetails, setJobDetails] = useState(null);
    const [isImporting, setIsImporting] = useState(false);
    const [isPolling, setIsPolling] = useState(false);
    
    const prevJobStatus = usePrevious(jobDetails?.status);
    const pollingIntervalRef = useRef(null);

    const [formData, setFormData] = useState({
        amazon_email: '',
        amazon_password: '',
        amazon_otp_secret_key: '',
        enable_scheduled_ingestion: false,
    });

    const pollImportStatus = useCallback(async () => {
        try {
            const { data: job } = await apiClient.get('/api/ingestion/manual/status');
            // Only update job details if a job object is returned.
            // This prevents the UI from disappearing if the API returns null
            // (e.g., after a server restart where the in-memory job is lost).
            if (job) {
                setJobDetails(job);
                if (job.status === 'completed' || job.status === 'failed') {
                    setIsPolling(false); // Stop polling
                }
            }
        } catch (error) {
            toast.error('Could not get import status. Stopping polling.');
            setIsPolling(false); // Stop polling on error
        }
    }, []);

    // Effect to manage the polling interval based on the isPolling state
    useEffect(() => {
        if (isPolling) {
            // Clear any existing interval before starting a new one.
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
            }
            pollingIntervalRef.current = setInterval(pollImportStatus, 3000);
        } else {
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
            }
        }
        // Cleanup function to clear interval on component unmount
        return () => {
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
            }
        };
    }, [isPolling, pollImportStatus]);

    // Effect for handling job status changes and notifications
    useEffect(() => {
        setIsImporting(jobDetails?.status === 'running');

        if (jobDetails && jobDetails.status !== prevJobStatus) {
            if (jobDetails.status === 'completed') {
                toast.success('Manual import finished successfully.');
            } else if (jobDetails.status === 'failed') {
                const errorMsg = jobDetails.error || 'An unknown error occurred.';
                toast.error(`Import failed: ${errorMsg}`);
            }
        }
    }, [jobDetails, prevJobStatus]);

    // Effect for fetching initial data
    useEffect(() => {
        const fetchInitialData = async () => {
            setIsLoading(true);
            try {
                const settingsRes = await apiClient.get('/api/settings');
                setFormData(prev => ({
                    ...prev,
                    amazon_email: settingsRes.data.amazon_email,
                    amazon_otp_secret_key: settingsRes.data.amazon_otp_secret_key,
                    enable_scheduled_ingestion: settingsRes.data.enable_scheduled_ingestion || false,
                }));
                setIsConfigured(settingsRes.data.is_configured);

                const { data: initialJob } = await apiClient.get('/api/ingestion/manual/status');
                setJobDetails(initialJob);
                if (initialJob?.status === 'running') {
                    setIsPolling(true);
                }
            } catch (err) {
                toast.error('Failed to load initial page data.');
            }
            setIsLoading(false);
        };
        fetchInitialData();
    }, []); // Runs only on mount

    const handleFormChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
    };

    // Derived state for the UI
    const importProgress = jobDetails?.progress || { value: 0, max: 100 };
    const importLog = jobDetails?.log || [];
    let importStatus = '';
    if (jobDetails) {
        if (jobDetails.status === 'running') {
            importStatus = importLog[importLog.length - 1] || 'Import in progress...';
        } else if (jobDetails.status === 'completed') {
            importStatus = 'Import completed successfully.';
        } else if (jobDetails.status === 'failed') {
            importStatus = `Error: ${jobDetails.error || 'Unknown error'}`;
        }
    }
    
    const handleSaveSettings = async (e) => {
        e.preventDefault();
        setIsSaving(true);
        try {
            const { data } = await apiClient.post('/api/settings/user', formData);
            toast.success(data.message);
            setFormData(prev => ({ ...prev, amazon_password: '' }));
            const settingsRes = await apiClient.get('/api/settings');
            setIsConfigured(settingsRes.data.is_configured);
        } catch (err) {
            toast.error(err.response?.data?.error || 'Failed to save settings.');
        }
        setIsSaving(false);
    };

    const handleRunIngestion = async () => {
        // Optimistically update UI and start polling
        setJobDetails({
            status: 'running',
            log: ['Requesting server to start import...'],
            progress: { value: 0, max: 100 }
        });
        setIsPolling(true);

        try {
            await apiClient.post('/api/ingestion/run', { days: importDays });
        } catch (err) {
            const errorMsg = err.response?.data?.error || 'Failed to start import.';
            toast.error(errorMsg);
            setJobDetails({ status: 'failed', error: errorMsg, log: [errorMsg] });
            setIsPolling(false);
        }
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
                <h2 className="text-3xl font-semibold text-text-primary mb-6">User Settings</h2>
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
                    <div className="pt-2">
                        <label className="flex items-center space-x-3 cursor-pointer">
                            <input
                                type="checkbox"
                                name="enable_scheduled_ingestion"
                                checked={formData.enable_scheduled_ingestion}
                                onChange={handleFormChange}
                                className="form-checkbox"
                            />
                            <span className="text-text-secondary">
                                Enable ongoing data retrieval
                                <p className="text-xs text-text-muted">
                                    When selected, your Amazon orders will be automatically pulled every morning at 1am.
                                </p>
                            </span>
                        </label>
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
                {(isImporting || jobDetails?.status === 'completed' || jobDetails?.status === 'failed') && (
                    <div className="space-y-2 pt-4 border-t border-border-color">
                        <p className="text-sm font-medium text-text-secondary">{importStatus}</p>
                        <progress 
                            value={importProgress.value} 
                            max={importProgress.max} 
                            className="w-full h-2 rounded-full [&::-webkit-progress-bar]:bg-surface-muted [&::-webkit-progress-value]:bg-primary [&::-moz-progress-bar]:bg-primary"
                        >
                            {importProgress.value}%
                        </progress>
                        <div className="h-40 bg-surface-muted rounded-lg p-2 overflow-y-auto">
                            <pre className="text-xs text-text-muted whitespace-pre-wrap">
                                {importLog.join('\n')}
                            </pre>
                        </div>
                    </div>
                )}
            </div>
            <div className="bg-surface p-6 rounded-2xl shadow-lg">
                <h3 className="font-semibold text-lg mb-2">Troubleshooting</h3>
                <div className="space-y-4">
                    <div>
                        <p className="text-sm text-text-muted mb-2">
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
            </div>
        </div>
    );
};

export default UserSettingsPage;
