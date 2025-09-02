import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useReactTable, getCoreRowModel, flexRender } from '@tanstack/react-table';
import apiClient from '../api';
import { toast } from 'react-toastify';

// --- Helper Components ---
const Spinner = () => <div className="flex justify-center items-center p-10"><div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div></div>;

const PriceWithIndicatorCell = ({ price, date, comparePrice }) => {
    if (!price) return <span className="text-text-muted">N/A</span>;

    const currentPrice = parseFloat(price);
    const historicalPrice = parseFloat(comparePrice);
    
    let indicator = null;
    if (comparePrice && !isNaN(historicalPrice)) {
        const change = currentPrice - historicalPrice;
        let colorClass = '';
        if (change > 0) {
            colorClass = 'text-danger';
            indicator = <span className={`ml-2 font-bold ${colorClass}`}>▲</span>;
        } else if (change < 0) {
            colorClass = 'text-success';
            indicator = <span className={`ml-2 font-bold ${colorClass}`}>▼</span>;
        }
    }

    return (
        <div>
            <p className="font-semibold">
                ${currentPrice.toFixed(2)}
                {indicator}
            </p>
            <p className="text-xs text-text-muted">{new Date(date).toLocaleDateString()}</p>
        </div>
    );
};

/**
 * @description A component to display and compare repeat purchase item prices.
 */
const RepeatOrdersTable = () => {
    const [data, setData] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [sortBy, setSortBy] = useState('date_current');
    const [sortOrder, setSortOrder] = useState('desc');
    const [filterText, setFilterText] = useState('');
    const [inputValue, setInputValue] = useState('');
    const [priceChangedOnly, setPriceChangedOnly] = useState(false);

    const fetchData = useCallback(async () => {
        setIsLoading(true);
        try {
            const params = { sortBy, sortOrder, filterText, priceChangedOnly };
            const { data: response } = await apiClient.get('/api/repeat-items', { params });
            setData(response);
        } catch (error) {
            toast.error("Failed to fetch repeat purchase item data.");
        }
        setIsLoading(false);
    }, [sortBy, sortOrder, filterText, priceChangedOnly]);

    useEffect(() => {
        const timeoutId = setTimeout(() => {
            setFilterText(inputValue);
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
    };

    const columns = useMemo(() => [
        {
            accessorKey: 'full_title',
            header: 'Product Title',
            cell: ({ row }) => (
                <div className="flex items-center space-x-3">
                    <a href={row.original.link} target="_blank" rel="noopener noreferrer">
                        <img 
                            src={row.original.thumbnail_url} 
                            alt={row.original.full_title}
                            className="w-16 h-16 object-cover rounded-md"
                        />
                    </a>
                    <a 
                        href={row.original.link} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-primary hover:underline font-medium"
                        title={row.original.full_title}
                    >
                        {row.original.full_title}
                    </a>
                </div>
            ),
        },
        {
            accessorKey: 'is_subscribe_and_save',
            header: 'Subscribe & Save',
            size: 100,
            cell: ({ getValue }) => (
                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                    getValue()
                        ? 'bg-success-muted text-success'
                        : 'bg-surface-hover text-text-muted'
                }`}>
                    {getValue() ? 'Yes' : 'No'}
                </span>
            )
        },
        { 
            accessorKey: 'price_current',
            header: 'Current',
            cell: ({ row }) => (
                <PriceWithIndicatorCell
                    price={row.original.price_current}
                    date={row.original.date_current}
                    comparePrice={row.original.price_prev_1}
                />
            )
        },
        {
            header: 'Previous',
            cell: ({ row }) => (
                <PriceWithIndicatorCell
                    price={row.original.price_prev_1}
                    date={row.original.date_prev_1}
                    comparePrice={row.original.price_prev_2}
                />
            )
        },
        {
            header: '2 Ago',
            cell: ({ row }) => (
                <PriceWithIndicatorCell
                    price={row.original.price_prev_2}
                    date={row.original.date_prev_2}
                    comparePrice={row.original.price_prev_3}
                />
            )
        },
        {
            header: '3 Ago',
            cell: ({ row }) => (
                <PriceWithIndicatorCell
                    price={row.original.price_prev_3}
                    date={row.original.date_prev_3}
                />
            )
        }
    ], []);

    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        manualSorting: true,
    });

    return (
        <div className="bg-surface p-6 rounded-2xl shadow-lg h-full flex flex-col">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-3xl font-semibold text-text-primary">Repeat Orders</h2>
                <button onClick={fetchData} disabled={isLoading} className="form-button-secondary">
                    {isLoading ? 'Refreshing...' : 'Refresh'}
                </button>
            </div>
            <div className="flex justify-between items-center mb-4">
                <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder="Search by title..."
                    className="form-input w-full md:w-1/3"
                />
                <div className="flex items-center space-x-2">
                    <input
                        type="checkbox"
                        id="price-changed-only"
                        checked={priceChangedOnly}
                        onChange={(e) => setPriceChangedOnly(e.target.checked)}
                        className="form-checkbox"
                    />
                    <label htmlFor="price-changed-only" className="text-sm font-medium text-text-primary">
                        Show only current price changes
                    </label>
                </div>
            </div>
            <div className="flex-grow overflow-auto">
                {isLoading ? <Spinner /> : (
                    data.length === 0 ? (
                        <div className="text-center p-10 text-text-muted">
                            <h3 className="text-xl font-semibold">No Repeat Orders Found</h3>
                            <p className="mt-2">This table will populate with items that have been purchased more than once.</p>
                        </div>
                    ) : (
                        <table className="w-full text-sm text-left text-text-secondary">
                            <thead className="text-xs text-text-primary uppercase bg-surface-muted">
                                {table.getHeaderGroups().map(headerGroup => (
                                    <tr key={headerGroup.id}>
                                        {headerGroup.headers.map(header => (
                                            <th key={header.id} scope="col" className="px-6 py-3 whitespace-nowrap">
                                                {header.isPlaceholder ? null : (
                                                    <div
                                                        className='flex items-center cursor-pointer'
                                                        onClick={() => handleSort(header.column.id)}
                                                    >
                                                        {flexRender(
                                                            header.column.columnDef.header,
                                                            header.getContext()
                                                        )}
                                                        <span className="ml-2">
                                                            {sortBy === header.column.id ? (sortOrder === 'asc' ? '🔼' : '🔽') : '↕️'}
                                                        </span>
                                                    </div>
                                                )}
                                            </th>
                                        ))}
                                    </tr>
                                ))}
                            </thead>
                            <tbody>
                                {table.getRowModel().rows.map(row => (
                                    <tr key={row.id} className="bg-surface border-b border-border-color hover:bg-surface-hover">
                                        {row.getVisibleCells().map(cell => (
                                            <td key={cell.id} className="px-6 py-4 align-top">
                                                {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )
                )}
            </div>
        </div>
    );
};

export default RepeatOrdersTable;

