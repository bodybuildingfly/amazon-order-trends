import React, { useState, useEffect } from 'react';
import apiClient from '../api';
import { toast } from 'react-toastify';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
} from 'chart.js';
import 'chartjs-adapter-date-fns';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
);

const PriceTrackingPage = () => {
    const [items, setItems] = useState([]);
    const [newItemUrl, setNewItemUrl] = useState('');
    const [loading, setLoading] = useState(false);
    const [adding, setAdding] = useState(false);
    const [selectedItem, setSelectedItem] = useState(null);

    useEffect(() => {
        fetchItems();
    }, []);

    const fetchItems = async () => {
        setLoading(true);
        try {
            const response = await apiClient.get('/api/tracked-items');
            setItems(response.data);
        } catch (error) {
            console.error("Error fetching items:", error);
            toast.error("Failed to load tracked items.");
        } finally {
            setLoading(false);
        }
    };

    const handleAddItem = async (e) => {
        e.preventDefault();
        if (!newItemUrl) return;

        setAdding(true);
        try {
            const response = await apiClient.post('/api/tracked-items', { url: newItemUrl });
            // Add the new item to the list.
            setItems([response.data, ...items]);
            setNewItemUrl('');
            toast.success("Item added successfully!");
        } catch (error) {
            console.error("Error adding item:", error);
            const msg = error.response?.data?.error || "Failed to add item.";
            toast.error(msg);
        } finally {
            setAdding(false);
        }
    };

    const handleDeleteItem = async (itemId) => {
        if (!window.confirm("Are you sure you want to stop tracking this item?")) return;
        try {
            await apiClient.delete(`/api/tracked-items/${itemId}`);
            setItems(items.filter(item => item.id !== itemId));
            if (selectedItem?.id === itemId) setSelectedItem(null);
            toast.success("Item removed.");
        } catch (error) {
            console.error("Error deleting item:", error);
            toast.error("Failed to delete item.");
        }
    };

    const handleViewDetails = async (item) => {
        if (selectedItem?.id === item.id) {
            setSelectedItem(null); // Toggle off
            return;
        }

        try {
            const response = await apiClient.get(`/api/tracked-items/${item.id}`);
            setSelectedItem(response.data);
        } catch (error) {
            console.error("Error fetching details:", error);
            toast.error("Failed to load item details.");
        }
    };

    const renderChart = () => {
        if (!selectedItem || !selectedItem.history || selectedItem.history.length === 0) {
            return <p className="text-text-secondary mt-4">No price history available.</p>;
        }

        const data = {
            labels: selectedItem.history.map(h => new Date(h.recorded_at)),
            datasets: [
                {
                    label: 'Price',
                    data: selectedItem.history.map(h => h.price),
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1
                }
            ]
        };

        const options = {
            responsive: true,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day',
                        displayFormats: {
                            day: 'MMM d'
                        }
                    },
                    title: {
                        display: true,
                        text: 'Date'
                    },
                    ticks: {
                        color: '#6b7280' // text-secondary
                    },
                    grid: {
                        color: '#374151' // dark grid lines
                    }
                },
                y: {
                    beginAtZero: false,
                    title: {
                        display: true,
                        text: 'Price'
                    },
                    ticks: {
                        color: '#6b7280'
                    },
                    grid: {
                        color: '#374151'
                    }
                }
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#9ca3af' // text-text-primary ish
                    }
                }
            }
        };

        // If the theme is light, we should adjust colors, but for now I'll stick to generic or dark-friendly.
        // The app has a theme toggle, so ideally I should detect theme.
        // But the chart background is white in my previous snippet:
        // <div className="mt-4 bg-white p-4 rounded shadow text-black">
        // Wait, if I use bg-white, text-black is good.

        return (
            <div className="mt-4 bg-surface p-4 rounded shadow">
                <Line data={data} options={options} />
            </div>
        );
    };

    return (
        <div className="container mx-auto">
            <h1 className="text-3xl font-bold mb-6 text-text-primary">Price Tracking</h1>

            {/* Add Item Form */}
            <div className="bg-surface p-6 rounded-lg shadow mb-8 border border-border-color">
                <h2 className="text-xl font-semibold mb-4 text-text-primary">Add New Item</h2>
                <form onSubmit={handleAddItem} className="flex gap-4">
                    <input
                        type="url"
                        placeholder="Enter Amazon URL"
                        value={newItemUrl}
                        onChange={(e) => setNewItemUrl(e.target.value)}
                        required
                        className="flex-grow p-2 rounded border border-border-color bg-background text-text-primary focus:outline-none focus:border-primary"
                    />
                    <button
                        type="submit"
                        disabled={adding}
                        className="bg-primary hover:bg-primary-hover text-white font-bold py-2 px-6 rounded disabled:opacity-50 transition-colors"
                    >
                        {adding ? 'Adding...' : 'Track Item'}
                    </button>
                </form>
            </div>

            {/* Items List */}
            <div className="bg-surface rounded-lg shadow overflow-hidden border border-border-color">
                <h2 className="text-xl font-semibold p-6 border-b border-border-color text-text-primary">Tracked Items</h2>
                {loading ? (
                    <div className="p-6 text-center text-text-secondary">Loading...</div>
                ) : items.length === 0 ? (
                    <div className="p-6 text-center text-text-secondary">No items tracked yet. Add one above!</div>
                ) : (
                    <ul>
                        {items.map(item => (
                            <li key={item.id} className="border-b border-border-color last:border-0">
                                <div className="p-4">
                                    <div className="flex items-center justify-between">
                                        <div className="flex-grow">
                                            <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-primary font-medium hover:underline block mb-1">
                                                {item.name || "Unknown Item"}
                                            </a>
                                            <div className="text-sm text-text-secondary">
                                                ASIN: {item.asin || 'N/A'} | Last Checked: {item.last_checked ? new Date(item.last_checked).toLocaleString() : 'Never'}
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-6">
                                            <div className="text-right">
                                                <div className="text-lg font-bold text-text-primary">
                                                    {item.currency} {item.current_price}
                                                </div>
                                            </div>
                                            <div className="flex gap-2">
                                                <button
                                                    onClick={() => handleViewDetails(item)}
                                                    className="text-text-accent hover:text-primary px-3 py-1 rounded border border-border-color hover:border-primary transition-colors"
                                                >
                                                    {selectedItem?.id === item.id ? 'Hide History' : 'View History'}
                                                </button>
                                                <button
                                                    onClick={() => handleDeleteItem(item.id)}
                                                    className="text-danger hover:text-danger-hover px-3 py-1 rounded border border-border-color hover:border-danger transition-colors"
                                                >
                                                    Delete
                                                </button>
                                            </div>
                                        </div>
                                    </div>

                                    {selectedItem?.id === item.id && (
                                        <div className="mt-4 pt-4 border-t border-border-color">
                                            <h3 className="text-lg font-semibold mb-2 text-text-primary">Price History</h3>
                                            {renderChart()}
                                        </div>
                                    )}
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
};

export default PriceTrackingPage;
