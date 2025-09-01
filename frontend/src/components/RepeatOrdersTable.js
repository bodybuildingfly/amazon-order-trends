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

    const fetchData = useCallback(async () => {
        setIsLoading(true);
        try {
            const { data: response } = await apiClient.get('/api/repeat-items');
            setData(response);
        } catch (error) {
            toast.error("Failed to fetch repeat purchase item data.");
        }
        setIsLoading(false);
    }, []);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

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
            header: 'Previous Order',
            cell: ({ row }) => (
                <PriceWithIndicatorCell
                    price={row.original.price_prev_1}
                    date={row.original.date_prev_1}
                    comparePrice={row.original.price_prev_2}
                />
            )
        },
        {
            header: '2 Orders Ago',
            cell: ({ row }) => (
                <PriceWithIndicatorCell
                    price={row.original.price_prev_2}
                    date={row.original.date_prev_2}
                    comparePrice={row.original.price_prev_3}
                />
            )
        },
        {
            header: '3 Orders Ago',
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
    });

    return (
        <div className="bg-surface p-6 rounded-2xl shadow-lg h-full flex flex-col">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-3xl font-semibold text-text-primary">Repeat Orders</h2>
                <button onClick={fetchData} disabled={isLoading} className="form-button-secondary">
                    {isLoading ? 'Refreshing...' : 'Refresh'}
                </button>
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
                                            <th key={header.id} scope="col" className="px-6 py-3">
                                                {flexRender(header.column.columnDef.header, header.getContext())}
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

