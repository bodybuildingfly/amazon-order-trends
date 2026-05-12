import React, { useState, useEffect, useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import { useTheme } from '../context/ThemeContext';
import { Chart, registerables } from 'chart.js';
import 'chartjs-adapter-date-fns';
import { formatDistanceToNow, differenceInHours } from 'date-fns';
import { toast } from 'react-toastify';
import api from '../api';
import StatCard from './common/StatCard';
import SkeletonLoader from './common/SkeletonLoader';

Chart.register(...registerables);

// Generic Icons
const DollarIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>;
const ShoppingBagIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>;
const ClockIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>;

const DashboardSkeleton = () => (
    <div className="p-8 bg-background min-h-screen">
        <SkeletonLoader className="h-9 w-1/4 mb-6" />
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <SkeletonLoader className="h-24 rounded-lg" />
            <SkeletonLoader className="h-24 rounded-lg" />
        </div>

        <div className="bg-surface p-6 rounded-lg shadow-md">
            <SkeletonLoader className="h-8 w-1/3 mb-4" />
            <SkeletonLoader className="h-64 w-full" />
        </div>
    </div>
);

const Dashboard = () => {
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const { theme } = useTheme();

    useEffect(() => {
        const fetchSummary = async () => {
            try {
                const response = await api.get('/api/dashboard/summary');
                setSummary(response.data);
            } catch (err) {
                toast.error('Failed to fetch dashboard data.');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchSummary();
    }, []);

    const chartData = useMemo(() => {
        if (!summary) return { labels: [], datasets: [] };

        const rootStyles = getComputedStyle(document.documentElement);
        const primaryColor = rootStyles.getPropertyValue('--color-primary').trim();

        return {
            labels: summary.spending_trend.map(d => new Date(d.month)),
            datasets: [
                {
                    label: 'Monthly Spending',
                    data: summary.spending_trend.map(d => d.total_spending),
                    fill: true,
                    backgroundColor: primaryColor,
                    borderColor: primaryColor,
                    tension: 0.1,
                },
            ],
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [summary, theme]);

    const getSyncStatusProps = () => {
        if (!summary || !summary.last_sync_time) {
            return {
                value: 'Never',
                customColorClass: 'bg-red-500 text-white' // Red for never synced
            };
        }

        const syncDate = new Date(summary.last_sync_time);
        const hoursDiff = differenceInHours(new Date(), syncDate);
        const timeAgo = formatDistanceToNow(syncDate, { addSuffix: true });

        if (hoursDiff <= 24) {
            return {
                value: timeAgo,
                customColorClass: 'bg-green-500 text-white' // Green for < 24h
            };
        } else {
            return {
                value: timeAgo,
                customColorClass: 'bg-yellow-500 text-white' // Yellow for > 24h
            };
        }
    };

    const syncProps = getSyncStatusProps();

    const chartOptions = useMemo(() => {
        const rootStyles = getComputedStyle(document.documentElement);
        const textColor = rootStyles.getPropertyValue('--color-text-primary').trim();
        const gridColor = rootStyles.getPropertyValue('--color-border-color').trim();

        return {
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'month',
                    },
                    title: {
                        display: true,
                        text: 'Month',
                        color: textColor,
                    },
                    ticks: {
                        color: textColor,
                    },
                    grid: {
                        color: gridColor,
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Total Spending ($)',
                        color: textColor,
                    },
                    ticks: {
                        color: textColor,
                    },
                    grid: {
                        color: gridColor,
                    }
                },
            },
            plugins: {
                legend: {
                    labels: {
                        color: textColor,
                    }
                }
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [theme]);

    if (loading || !summary) {
        return <DashboardSkeleton />;
    }

    return (
        <div className="p-8 bg-background min-h-screen">
            <h1 className="text-3xl font-bold mb-6 text-text-primary">Dashboard</h1>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <StatCard 
                    title="Total Spending" 
                    value={`$${summary.total_spending.toFixed(2)}`}
                    icon={<DollarIcon />}
                />
                <StatCard 
                    title="Total Orders" 
                    value={summary.total_orders}
                    icon={<ShoppingBagIcon />}
                />
                <StatCard
                    title="Last Synced"
                    value={syncProps.value}
                    icon={<ClockIcon />}
                    customColorClass={syncProps.customColorClass}
                />
            </div>

            <div className="bg-surface p-6 rounded-lg shadow-md">
                <h2 className="text-xl font-semibold mb-4 text-text-primary">Spending Trend</h2>
                <Line data={chartData} options={chartOptions} />
            </div>
        </div>
    );
};

export default Dashboard;
