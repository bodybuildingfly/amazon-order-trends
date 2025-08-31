import React, { useState, useEffect, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useTable, useSortBy, usePagination, useFilters } from '@tanstack/react-table';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// --- Main App Component ---
function App() {
    const [activeView, setActiveView] = useState('trends'); // 'trends' or 'table'
    
    return (
        <div className="min-h-screen bg-background text-text-primary">
            <ToastContainer theme="colored" />
            <div className="grid grid-cols-12">
                {/* --- Left Sidebar --- */}
                <aside className="col-span-3 bg-surface border-r border-border-color h-screen p-6">
                    <h1 className="text-2xl font-bold text-text-primary mb-8">Price Tracker</h1>
                    <nav className="space-y-2">
                        <button onClick={() => setActiveView('trends')} className={`w-full text-left px-4 py-2 rounded-lg ${activeView === 'trends' ? 'bg-primary text-white' : 'hover:bg-gray-200 dark:hover:bg-gray-700'}`}>Price Trend Graph</button>
                        <button onClick={() => setActiveView('table')} className={`w-full text-left px-4 py-2 rounded-lg ${activeView === 'table' ? 'bg-primary text-white' : 'hover:bg-gray-200 dark:hover:bg-gray-700'}`}>Interactive Data Table</button>
                    </nav>
                </aside>

                {/* --- Main Content --- */}
                <main className="col-span-9 p-8">
                    {activeView === 'trends' && <PriceTrendGraph />}
                    {activeView === 'table' && <InteractiveDataTable />}
                </main>
            </div>
        </div>
    );
}

// --- Price Trend Graph Component ---
const PriceTrendGraph = () => {
    const [products, setProducts] = useState([]);
    const [selectedProduct, setSelectedProduct] = useState('');
    const [trendData, setTrendData] = useState([]);

    useEffect(() => {
        fetch('/api/products')
            .then(res => res.json())
            .then(data => setProducts(data))
            .catch(() => toast.error("Failed to fetch product list."));
    }, []);

    useEffect(() => {
        if (selectedProduct) {
            fetch(`/api/trends/${selectedProduct}`)
                .then(res => res.json())
                .then(data => setTrendData(data))
                .catch(() => toast.error("Failed to fetch price trend data."));
        }
    }, [selectedProduct]);

    return (
        <div className="bg-surface p-6 rounded-2xl shadow-lg">
            <h2 className="text-3xl font-semibold mb-4">Price Trend Analysis</h2>
            <select 
                value={selectedProduct} 
                onChange={e => setSelectedProduct(e.target.value)}
                className="w-full p-2 mb-6 border rounded-lg bg-background border-border-color"
            >
                <option value="">Select a Product...</option>
                {products.map(p => <option key={p.asin} value={p.asin}>{p.short_title}</option>)}
            </select>
            <div style={{ height: '400px' }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trendData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="price" stroke="#8884d8" activeDot={{ r: 8 }} />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

// --- Interactive Data Table Component ---
const InteractiveDataTable = () => {
    // This is a simplified version. Full implementation would require more state management for server-side operations.
    const [data, setData] = useState([]);
    const columns = useMemo(() => [
        { Header: 'Short Title', accessor: 'short_title' },
        { Header: 'Full Title', accessor: 'full_title' },
        { Header: 'ASIN', accessor: 'asin' },
        { Header: 'Last Price', accessor: 'price_per_unit' },
        { Header: 'Last Purchase Date', accessor: 'order_placed_date' },
    ], []);

    useEffect(() => {
        fetch('/api/items')
            .then(res => res.json())
            .then(apiData => setData(apiData.data))
            .catch(() => toast.error("Failed to fetch item data."));
    }, []);

    const {
        getTableProps,
        getTableBodyProps,
        headerGroups,
        page,
        prepareRow,
    } = useTable({ columns, data }, useFilters, useSortBy, usePagination);

    return (
         <div className="bg-surface p-6 rounded-2xl shadow-lg">
            <h2 className="text-3xl font-semibold mb-4">All Purchased Items</h2>
            <table {...getTableProps()} className="w-full">
                <thead>
                    {headerGroups.map(headerGroup => (
                        <tr {...headerGroup.getHeaderGroupProps()}>
                            {headerGroup.headers.map(column => (
                                <th {...column.getHeaderProps(column.getSortByToggleProps())} className="p-2 border-b border-border-color text-left">
                                    {column.render('Header')}
                                    <span>{column.isSorted ? (column.isSortedDesc ? ' 🔽' : ' 🔼') : ''}</span>
                                </th>
                            ))}
                        </tr>
                    ))}
                </thead>
                <tbody {...getTableBodyProps()}>
                    {page.map(row => {
                        prepareRow(row);
                        return (
                            <tr {...row.getRowProps()} className="hover:bg-gray-200 dark:hover:bg-gray-700">
                                {row.cells.map(cell => (
                                    <td {...cell.getCellProps()} className="p-2 border-b border-border-color">{cell.render('Cell')}</td>
                                ))}
                            </tr>
                        );
                    })}
                </tbody>
            </table>
         </div>
    );
};

export default App;
