import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import apiClient from '../api';

const Spinner = () => <div className="flex justify-center items-center p-10"><div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div></div>;

const AdminSettingsPage = () => {
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [formData, setFormData] = useState({
        discord_webhook_url: '',
        discord_notification_preference: 'off',
    });

    useEffect(() => {
        const fetchSettings = async () => {
            setIsLoading(true);
            try {
                const { data } = await apiClient.get('/api/settings');
                setFormData({
                    discord_webhook_url: data.discord_webhook_url || '',
                    discord_notification_preference: data.discord_notification_preference || 'off',
                });
            } catch (err) {
                toast.error('Failed to load admin settings.');
            }
            setIsLoading(false);
        };
        fetchSettings();
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

    const handleRunScheduler = async () => {
        try {
            const { data } = await apiClient.post('/api/scheduler/run');
            toast.success(data.message);
        } catch (err) {
            toast.error(err.response?.data?.error || 'Failed to trigger scheduler.');
        }
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
                        <button onClick={handleRunScheduler} className="form-button-secondary">
                            Run Scheduled Ingestion
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AdminSettingsPage;
