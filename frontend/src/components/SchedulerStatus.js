/**
 * @file frontend/src/components/SchedulerStatus.js
 * @description Refactored to use semantic color classes.
 */
import { useState, useEffect, useCallback } from 'react';
import apiClient from '../api';

const SchedulerStatus = () => {
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(true);

    const formatDisplayDate = (dateString) => {
        if (!dateString || dateString === 'Never' || dateString === 'Not scheduled') {
            return dateString;
        }
        const options = {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
        };
        return new Date(dateString).toLocaleString('en-US', options);
    };

    const fetchStatus = useCallback(async () => {
        // The isConfigured prop is not directly applicable in the same way as the
        // original Trello app. We will rely on the backend to determine if the
        // scheduler can run (e.g., if there are any users with scheduled
        // ingestion enabled). The backend will return an appropriate status or error.
        // For now, we remove the explicit client-side check.
        setLoading(true);
        try {
            const res = await apiClient.get('/api/scheduler/status');
            setStatus(res.data);
        } catch (error) {
            console.error("Failed to fetch scheduler status", error);
            setStatus({ error: "Could not load status." });
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        fetchStatus();
    }, [fetchStatus]);

    return (
        <div className="bg-surface p-4 rounded-xl shadow-md mb-8 max-w-5xl mx-auto">
            <div className="flex justify-between items-center">
                <h3 className="text-xl font-semibold text-text-secondary">Scheduler Status</h3>
                <button onClick={fetchStatus} disabled={loading} className="text-sm text-text-accent hover:text-primary-hover disabled:text-text-muted">
                    {loading ? 'Refreshing...' : 'Refresh'}
                </button>
            </div>
            {!status || loading ? <div className="text-center p-4">Loading status...</div> : (
                status.error ? <p className="text-center p-4 text-danger">{status.error}</p> :
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 text-center">
                    <div>
                        <p className="text-sm text-text-muted">Last Run</p>
                        <p className="text-lg font-bold text-text-primary whitespace-nowrap">{formatDisplayDate(status.lastRun)}</p>
                    </div>
                    <div>
                        <p className="text-sm text-text-muted">Duration</p>
                        <p className="text-lg font-bold text-text-primary">{status.duration}</p>
                    </div>
                    <div>
                        <p className="text-sm text-text-muted">Orders Processed</p>
                        <p className="text-lg font-bold text-text-primary">{status.ordersProcessed}</p>
                    </div>
                    <div>
                        <p className="text-sm text-text-muted">Next Scheduled Run</p>
                        <p className="text-lg font-bold text-text-primary whitespace-nowrap">{formatDisplayDate(status.nextRun)}</p>
                    </div>
                </div>
            )}
        </div>
    );
};

export default SchedulerStatus;
