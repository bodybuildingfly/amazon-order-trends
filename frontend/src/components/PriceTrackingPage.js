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
    const [editingItemId, setEditingItemId] = useState(null);
    const [editingName, setEditingName] = useState('');
    const [editingThresholdType, setEditingThresholdType] = useState('percent');
    const [editingThresholdValue, setEditingThresholdValue] = useState('');

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

    const handleEditClick = (item) => {
        setEditingItemId(item.id);
        setEditingName(item.name || '');
        setEditingThresholdType(item.notification_threshold_type || 'percent');
        setEditingThresholdValue(item.notification_threshold_value || '');
    };

    const handleCancelEdit = () => {
        setEditingItemId(null);
        setEditingName('');
        setEditingThresholdType('percent');
        setEditingThresholdValue('');
    };

    const handleSaveEdit = async (itemId) => {
        if (!editingName.trim()) {
            toast.error("Name cannot be empty.");
            return;
        }

        const payload = {
            name: editingName,
            notification_threshold_type: editingThresholdType,
            notification_threshold_value: editingThresholdValue ? parseFloat(editingThresholdValue) : null
        };

        try {
            const response = await apiClient.put(`/api/tracked-items/${itemId}`, payload);

            // Update local state
            setItems(items.map(item => item.id === itemId ? {
                ...item,
                name: response.data.name,
                notification_threshold_type: response.data.notification_threshold_type,
                notification_threshold_value: response.data.notification_threshold_value
            } : item));

            // If the selected item is the one being edited, update it too
            if (selectedItem?.id === itemId) {
                setSelectedItem({
                    ...selectedItem,
                    name: response.data.name,
                    notification_threshold_type: response.data.notification_threshold_type,
                    notification_threshold_value: response.data.notification_threshold_value
                });
            }

            setEditingItemId(null);
            setEditingName('');
            setEditingThresholdValue('');
            toast.success("Item updated successfully.");
        } catch (error) {
            console.error("Error updating item:", error);
            toast.error("Failed to update item.");
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
                                            {editingItemId === item.id ? (
                                                <div className="mb-2">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <input
                                                            type="text"
                                                            value={editingName}
                                                            onChange={(e) => setEditingName(e.target.value)}
                                                            className="p-1 rounded border border-border-color bg-background text-text-primary focus:outline-none focus:border-primary flex-grow max-w-md"
                                                            placeholder="Item Name"
                                                        />
                                                    </div>
                                                    <div className="flex items-center gap-2 text-sm text-text-secondary">
                                                        <span>Notify if price drops by:</span>
                                                        <select
                                                            value={editingThresholdType}
                                                            onChange={(e) => setEditingThresholdType(e.target.value)}
                                                            className="p-1 rounded border border-border-color bg-background text-text-primary focus:outline-none focus:border-primary"
                                                        >
                                                            <option value="percent">Percentage (%)</option>
                                                            <option value="absolute">Amount ($)</option>
                                                        </select>
                                                        <input
                                                            type="number"
                                                            value={editingThresholdValue}
                                                            onChange={(e) => setEditingThresholdValue(e.target.value)}
                                                            className="p-1 w-20 rounded border border-border-color bg-background text-text-primary focus:outline-none focus:border-primary"
                                                            placeholder="Value"
                                                            step="0.01"
                                                        />
                                                    </div>
                                                    <div className="flex gap-2 mt-2">
                                                        <button
                                                            onClick={() => handleSaveEdit(item.id)}
                                                            className="text-primary hover:text-primary-hover text-sm font-medium"
                                                        >
                                                            Save
                                                        </button>
                                                        <button
                                                            onClick={handleCancelEdit}
                                                            className="text-text-secondary hover:text-text-primary text-sm font-medium"
                                                        >
                                                            Cancel
                                                        </button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="mb-1">
                                                    <div className="flex items-center gap-2">
                                                        <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-primary font-medium hover:underline block">
                                                            {item.name || "Unknown Item"}
                                                        </a>
                                                        <button
                                                            onClick={() => handleEditClick(item)}
                                                            className="text-text-secondary hover:text-primary transition-colors"
                                                            title="Edit Settings"
                                                        >
                                                            {/* Simple Edit Icon (Pencil) */}
                                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                                                          <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
                                                        </svg>
                                                        </button>
                                                    </div>
                                                    <div className="text-sm text-text-secondary mt-1">
                                                        {item.notification_threshold_value ? (
                                                            <span className="mr-2 text-text-accent">
                                                                Notify drop &ge; {item.notification_threshold_value}{item.notification_threshold_type === 'percent' ? '%' : ''}
                                                            </span>
                                                        ) : (
                                                            <span className="mr-2 text-text-muted">No notification set</span>
                                                        )}
                                                        <span>
                                                            | ASIN: {item.asin || 'N/A'} | Last Checked: {item.last_checked ? new Date(item.last_checked).toLocaleString() : 'Never'}
                                                        </span>
                                                    </div>
                                                </div>
                                            )}
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
