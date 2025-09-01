import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useReactTable, getCoreRowModel, flexRender } from '@tanstack/react-table';
import apiClient from '../api';
import { toast } from 'react-toastify';

// --- Helper Components ---
const Spinner = () => <div className="flex justify-center items-center p-10"><div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div></div>;

const InteractiveDataTable = () => {
    const [data, setData] = useState([]);
    const [totalItems, setTotalItems] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [limit] = useState(20);
    const [sortBy, setSortBy] = useState('order_placed_date');
    const [sortOrder, setSortOrder] = useState('desc');
    const [filterText, setFilterText] = useState('');
    const [inputValue, setInputValue] = useState('');

    const totalPages = Math.ceil(totalItems / limit);

    const fetchData = useCallback(async () => {
        setIsLoading(true);
        try {
            const params = { page, limit, sortBy, sortOrder, filterText };
            const { data: response } = await apiClient.get('/api/items', { params });
            setData(response.data);
            setTotalItems(response.total);
        } catch (error) {
            toast.error("Failed to fetch item data.");
        }
        setIsLoading(false);
    }, [page, limit, sortBy, sortOrder, filterText]);

    useEffect(() => {
        const timeoutId = setTimeout(() => {
            setFilterText(inputValue);
            setPage(1); // Reset to first page on new search
        }, 500); // Debounce search input
        return () => clearTimeout(timeoutId);
    }, [inputValue]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const handleSort = (columnId) => {
        if (sortBy === columnId) {
            setSortOrder(prev => (prev === 'asc' ? 'desc' : 'asc'));
        } else {
            setSortBy(columnId);
            setSortOrder('desc');
        }
        setPage(1); // Reset to first page on sort
    };

    const columns = useMemo(() => [
        {
            accessorKey: 'full_title',
            header: 'Product Title',
            // UPDATED: Use a custom cell renderer to create a hyperlink
            cell: ({ row }) => (
                <a 
                    href={row.original.link} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-primary hover:underline font-medium"
                    title={row.original.full_title}
                >
                    {row.original.full_title}
                </a>
            ),
        },
        { accessorKey: 'asin', header: 'ASIN' },
        { 
            accessorKey: 'price_per_unit', 
            header: 'Price',
            cell: info => `$${parseFloat(info.getValue()).toFixed(2)}`
        },
        { 
            accessorKey: 'order_placed_date', 
            header: 'Purchase Date',
            cell: info => new Date(info.getValue()).toLocaleDateString()
        },
    ], []);

    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        manualPagination: true,
        manualSorting: true,
        manualFiltering: true,
    });

    return (
        <div className="bg-surface p-6 rounded-2xl shadow-lg h-full flex flex-col">
            <h2 className="text-3xl font-semibold mb-4 text-text-primary">All Purchased Items</h2>
            <div className="mb-4">
                <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder="Search by title or date..."
                    className="form-input"
                />
            </div>
            <div className="flex-grow overflow-auto">
                {isLoading ? <Spinner /> : (
                    <table className="w-full text-sm text-left text-text-secondary">
                        <thead className="text-xs text-text-primary uppercase bg-surface-muted">
                            {table.getHeaderGroups().map(headerGroup => (
                                <tr key={headerGroup.id}>
                                    {headerGroup.headers.map(header => (
                                        <th key={header.id} scope="col" className="px-6 py-3">
                                            <div
                                                className="flex items-center cursor-pointer"
                                                onClick={() => handleSort(header.column.id)}
                                            >
                                                {flexRender(header.column.columnDef.header, header.getContext())}
                                                <span className="ml-2">
                                                    {sortBy === header.column.id ? (sortOrder === 'asc' ? '🔼' : '🔽') : '↕️'}
                                                </span>
                                            </div>
                                        </th>
                                    ))}
                                </tr>
                            ))}
                        </thead>
                        <tbody>
                            {table.getRowModel().rows.map(row => (
                                <tr key={row.id} className="bg-surface border-b border-border-color hover:bg-surface-hover">
                                    {row.getVisibleCells().map(cell => (
                                        <td key={cell.id} className="px-6 py-4">
                                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
            <div className="flex justify-between items-center pt-4">
                <span className="text-sm text-text-muted">
                    Page {page} of {totalPages} ({totalItems} items)
                </span>
                <div className="flex items-center space-x-2">
                    <button onClick={() => setPage(1)} disabled={page === 1} className="form-button-secondary">First</button>
                    <button onClick={() => setPage(p => p - 1)} disabled={page === 1} className="form-button-secondary">Prev</button>
                    <button onClick={() => setPage(p => p + 1)} disabled={page === totalPages} className="form-button-secondary">Next</button>
                    <button onClick={() => setPage(totalPages)} disabled={page === totalPages} className="form-button-secondary">Last</button>
                </div>
            </div>
        </div>
    );
};

export default InteractiveDataTable;

