import React, { useState, useEffect, useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import { useTheme } from '../context/ThemeContext';
import { Chart, registerables } from 'chart.js';
import 'chartjs-adapter-date-fns';
import { toast } from 'react-toastify';
import api from '../api';
import StatCard from './common/StatCard';
import SkeletonLoader from './common/SkeletonLoader';

Chart.register(...registerables);

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
                />
                <StatCard 
                    title="Total Orders" 
                    value={summary.total_orders}
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
