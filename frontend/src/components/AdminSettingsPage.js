import React, { useState, useEffect, useRef } from 'react';
import { toast } from 'react-toastify';
import { useAuth } from '../context/AuthContext';
import apiClient from '../api';

const Spinner = () => <div className="flex justify-center items-center p-10"><div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div></div>;

const JobStatusDisplay = ({ job, isImporting }) => {
    if (!job && !isImporting) {
        return <p className="text-sm text-text-muted">No recent job information available. Run the ingestion to see its status.</p>;
    }
    if (isImporting && !job) {
        return <p className="text-sm text-text-muted">Connecting to job stream...</p>;
    }

    const { id, status, progress, details, updated_at, error } = job;
    const userIds = details?.users ? Object.keys(details.users) : [];
    
    const getStatusPill = (status) => {
        const baseClasses = "px-2 py-1 text-xs font-medium rounded-full capitalize";
        const statusMap = {
            running: "bg-blue-100 text-blue-800 animate-pulse",
            completed: "bg-green-100 text-green-800",
            failed: "bg-red-100 text-red-800",
            pending: "bg-gray-100 text-gray-800",
        };
        return <span className={`${baseClasses} ${statusMap[status] || statusMap.pending}`}>{status}</span>;
    };

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center">
                <h4 className="text-lg font-medium text-text-primary">
                    Ingestion Status
                </h4>
                <div className="text-right">
                    {getStatusPill(isImporting ? 'running' : status)}
                    <p className="text-xs text-text-muted mt-1" title={id}>
                        Last updated: {new Date(updated_at).toLocaleString()}
                    </p>
                </div>
            </div>

            {progress && (
                <div>
                    <div className="flex justify-between mb-1">
                        <span className="text-sm font-medium text-text-secondary">Overall Progress</span>
                        <span className="text-sm font-medium text-text-secondary">{progress.current} / {progress.total} Users</span>
                    </div>
                    <progress 
                        value={progress.current} 
                        max={progress.total} 
                        className="w-full h-2 rounded-full [&::-webkit-progress-bar]:bg-surface-muted [&::-webkit-progress-value]:bg-primary [&::-moz-progress-bar]:bg-primary"
                    />
                </div>
            )}
            
            {error && <p className="text-sm text-red-500 bg-red-100 p-2 rounded-md">Error: {JSON.stringify(error)}</p>}

            {details?.users && userIds.length > 0 && (
                 <div className="space-y-2 pt-4 border-t border-border-color">
                     <h5 className="text-md font-medium text-text-primary">User Status</h5>
                     <div className="max-h-60 overflow-y-auto rounded-md bg-surface-muted p-2 space-y-1">
                        {userIds.map(userId => (
                            <div key={userId} className="flex justify-between items-center p-2 bg-surface rounded-md shadow-sm">
                                <span className="text-sm text-text-secondary">{details.users[userId].username}</span>
                                {getStatusPill(details.users[userId].status)}
                            </div>
                        ))}
                     </div>
                 </div>
            )}
        </div>
    );
};


const AdminSettingsPage = () => {
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [formData, setFormData] = useState({
        discord_webhook_url: '',
        discord_notification_preference: 'off',
    });
    
    const { user } = useAuth();
    const [job, setJob] = useState(null);
    const [isImporting, setIsImporting] = useState(false);
    const eventSourceRef = useRef(null);

    useEffect(() => {
        const fetchSettingsAndJob = async () => {
            setIsLoading(true);
            try {
                const settingsRes = await apiClient.get('/api/settings');
                setFormData({
                    discord_webhook_url: settingsRes.data.discord_webhook_url || '',
                    discord_notification_preference: settingsRes.data.discord_notification_preference || 'off',
                });

                const jobRes = await apiClient.get('/api/ingestion/jobs/latest');
                if (jobRes.data) {
                    setJob(jobRes.data);
                }
            } catch (err) {
                if (err.response?.status !== 404) {
                    toast.error('Failed to load initial page data.');
                }
            }
            setIsLoading(false);
        };
        fetchSettingsAndJob();
    }, []);
    
    useEffect(() => {
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
            }
        };
    }, []);

    const handleFormChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSaveSettings = async (e) => {
        e.preventDefault();
        setIsSaving(true);
        try {
            const { data } = await apiClient.post('/api/settings/admin', formData);
            toast.success(data.message);
        } catch (err) {
            toast.error(err.response?.data?.error || 'Failed to save admin settings.');
        }
        setIsSaving(false);
    };

    const handleRunScheduler = () => {
        if (!user?.token) {
            toast.error("Authentication token not found. Please log in again.");
            return;
        }

        setIsImporting(true);
        setJob(null);

        const baseUrl = process.env.NODE_ENV === 'production' ? '' : 'http://localhost:5001';
        const url = `${baseUrl}/api/scheduler/run?token=${user.token}`;
        
        const eventSource = new EventSource(url);
        eventSourceRef.current = eventSource;

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const { type, payload } = data;

            if (type === 'job_update') {
                setJob(prevJob => ({ ...prevJob, ...payload }));
            } else if (type === 'error') {
                toast.error(`An error occurred: ${payload}`);
                setJob(prevJob => ({ ...prevJob, status: 'failed', error: payload }));
                setIsImporting(false);
                eventSource.close();
            } else if (type === 'done') {
                setJob(prevJob => ({ ...prevJob, status: prevJob?.status === 'failed' ? 'failed' : 'completed' }));
                toast.success("Scheduled ingestion run has finished.");
                setIsImporting(false);
                eventSource.close();
            }
        };

        eventSource.onerror = () => {
            toast.error("Connection to server failed. Import stopped.");
            setIsImporting(false);
            setJob(prevJob => ({ ...(prevJob || {}), status: 'failed', error: 'Connection Error' }));
            eventSource.close();
        };
    };

    if (isLoading) return <Spinner />;

    return (
        <div className="space-y-8 max-w-3xl mx-auto">
            <div className="bg-surface p-6 rounded-2xl shadow-lg">
                <h2 className="text-3xl font-semibold text-text-primary mb-6">Admin Settings</h2>
                <form onSubmit={handleSaveSettings} className="space-y-6">
                    <div>
                        <h3 className="text-lg font-medium text-text-primary mb-1">Discord Notifications</h3>
                        <p className="text-sm text-text-muted mb-4">
                            Receive notifications in Discord when the scheduled data retrieval runs.
                        </p>
                        <div className="space-y-4">
                            <div>
                                <label htmlFor="discord_webhook_url" className="form-label">Webhook URL</label>
                                <input
                                    type="url"
                                    name="discord_webhook_url"
                                    id="discord_webhook_url"
                                    value={formData.discord_webhook_url}
                                    onChange={handleFormChange}
                                    className="form-input"
                                    placeholder="https://discord.com/api/webhooks/..."
                                />
                            </div>
                            <div>
                                <label htmlFor="discord_notification_preference" className="form-label">Notification Frequency</label>
                                <select
                                    name="discord_notification_preference"
                                    id="discord_notification_preference"
                                    value={formData.discord_notification_preference}
                                    onChange={handleFormChange}
                                    className="form-input"
                                >
                                    <option value="off">Disabled</option>
                                    <option value="on_error">Notify on Error</option>
                                    <option value="on_all">Notify on All Runs</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <div className="flex justify-end">
                        <button type="submit" disabled={isSaving} className="form-button-primary">
                            {isSaving ? 'Saving...' : 'Save Settings'}
                        </button>
                    </div>
                </form>
            </div>
            <div className="bg-surface p-6 rounded-2xl shadow-lg">
                <h3 className="font-semibold text-lg mb-2">System Administration</h3>
                <div className="space-y-4">
                    <div>
                        <p className="text-sm text-text-muted mb-2">
                            Manually trigger the daily scheduled job to run for all enabled users.
                        </p>
                        <button onClick={handleRunScheduler} disabled={isImporting} className="form-button-secondary">
                            {isImporting ? 'Running...' : 'Run Scheduled Ingestion'}
                        </button>
                    </div>
                    <div className="pt-4 border-t border-border-color">
                        <JobStatusDisplay job={job} isImporting={isImporting} />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AdminSettingsPage;
