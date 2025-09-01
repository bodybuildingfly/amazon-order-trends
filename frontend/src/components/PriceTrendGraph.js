import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { toast } from 'react-toastify';
import apiClient from '../api';

// --- Helper Components ---
const LoadingSpinner = () => (
    <div className="flex items-center justify-center h-full">
        <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
    </div>
);

const EmptyState = () => (
    <div className="flex flex-col items-center justify-center h-full text-center text-text-muted">
        <h3 className="text-xl font-semibold">No Product Selected</h3>
        <p>Please select a product from the dropdown above to view its price trend.</p>
    </div>
);


/**
 * @description A component for visualizing the price trend of a selected product.
 */
const PriceTrendGraph = () => {
    const [products, setProducts] = useState([]);
    const [selectedProduct, setSelectedProduct] = useState('');
    const [trendData, setTrendData] = useState([]);
    const [isLoading, setIsLoading] = useState(false);

    // Fetch the list of unique products when the component mounts
    useEffect(() => {
        const fetchProducts = async () => {
            try {
                const { data } = await apiClient.get('/api/products');
                if (Array.isArray(data)) {
                    setProducts(data);
                }
            } catch (error) {
                toast.error("Failed to fetch product list.");
            }
        };
        fetchProducts();
    }, []);

    // Fetch the price trend data whenever a new product is selected
    useEffect(() => {
        if (selectedProduct) {
            const fetchTrendData = async () => {
                setIsLoading(true);
                try {
                    const { data } = await apiClient.get(`/api/trends/${selectedProduct}`);
                    if (Array.isArray(data)) {
                        setTrendData(data);
                    }
                } catch (error) {
                    toast.error("Failed to fetch price trend data.");
                    setTrendData([]); // Clear data on error
                } finally {
                    setIsLoading(false);
                }
            };
            fetchTrendData();
        } else {
            setTrendData([]); // Clear data if no product is selected
        }
    }, [selectedProduct]);

    const selectedProductName = products.find(p => p.asin === selectedProduct)?.full_title || 'Price Trend';

    return (
        <div className="bg-surface p-6 rounded-2xl shadow-lg h-full flex flex-col">
            <h2 className="text-3xl font-semibold text-text-primary mb-4">Price Trend Analysis</h2>
            
            <select
                value={selectedProduct}
                onChange={e => setSelectedProduct(e.target.value)}
                className="form-input w-full md:w-1/2 lg:w-1/3 mb-6"
                aria-label="Select a product to view its price trend"
            >
                <option value="">-- Select a Product --</option>
                {products.map(p => (
                    <option key={p.asin} value={p.asin}>
                        {p.full_title}
                    </option>
                ))}
            </select>
            
            <div className="flex-grow min-h-[400px]">
                {isLoading ? <LoadingSpinner /> : (
                    trendData.length > 0 ? (
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart
                                data={trendData}
                                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                            >
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-color)" />
                                <XAxis dataKey="date" stroke="var(--color-text-secondary)" />
                                <YAxis stroke="var(--color-text-secondary)" tickFormatter={(value) => `$${value.toFixed(2)}`} />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: 'var(--color-surface)',
                                        borderColor: 'var(--color-border-color)'
                                    }}
                                />
                                <Legend />
                                <Line
                                    type="monotone"
                                    dataKey="price"
                                    name={selectedProductName}
                                    stroke="var(--color-primary)"
                                    strokeWidth={2}
                                    activeDot={{ r: 8 }}
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    ) : (
                        <EmptyState />
                    )
                )}
            </div>
        </div>
    );
};

export default PriceTrendGraph;

