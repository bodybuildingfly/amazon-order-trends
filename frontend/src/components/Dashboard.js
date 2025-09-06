import React, { useState, useEffect } from 'react';
import { Line } from 'react-chartjs-2';
import { Chart, registerables } from 'chart.js';
import 'chartjs-adapter-date-fns';
import { toast } from 'react-toastify';
import api from '../api';
import StatCard from './common/StatCard';
import SkeletonLoader from './common/SkeletonLoader';

Chart.register(...registerables);

const DashboardSkeleton = () => (
    <div className="p-8 bg-gray-50 dark:bg-gray-900 min-h-screen">
        <SkeletonLoader className="h-9 w-1/4 mb-6" />
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <SkeletonLoader className="h-24 rounded-lg" />
            <SkeletonLoader className="h-24 rounded-lg" />
        </div>

        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
            <SkeletonLoader className="h-8 w-1/3 mb-4" />
            <SkeletonLoader className="h-64 w-full" />
        </div>
    </div>
);

const Dashboard = () => {
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);

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

    if (loading || !summary) {
        return <DashboardSkeleton />;
    }

    const chartData = {
        labels: summary.spending_trend.map(d => new Date(d.month)),
        datasets: [
            {
                label: 'Monthly Spending',
                data: summary.spending_trend.map(d => d.total_spending),
                fill: false,
                backgroundColor: 'rgb(75, 192, 192)',
                borderColor: 'rgba(75, 192, 192, 0.2)',
            },
        ],
    };

    const chartOptions = {
        scales: {
            x: {
                type: 'time',
                time: {
                    unit: 'month',
                },
                title: {
                    display: true,
                    text: 'Month',
                },
            },
            y: {
                title: {
                    display: true,
                    text: 'Total Spending ($)',
                },
            },
        },
    };

    return (
        <div className="p-8 bg-gray-50 dark:bg-gray-900 min-h-screen">
            <h1 className="text-3xl font-bold mb-6 text-gray-900 dark:text-white">Dashboard</h1>
            
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

            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md">
                <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">Spending Trend</h2>
                <Line data={chartData} options={chartOptions} />
            </div>
        </div>
    );
};

export default Dashboard;
