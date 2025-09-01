import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useReactTable, getCoreRowModel, flexRender } from '@tanstack/react-table';
import apiClient from '../api';
import { toast } from 'react-toastify';

// --- Helper Components ---
const Spinner = () => <div className="flex justify-center items-center p-10"><div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div></div>;

/**
 * @description A component to display and compare Subscribe & Save item prices.
 */
const SnsDataTable = () => {
    const [data, setData] = useState([]);
    const [isLoading, setIsLoading] = useState(true);

    const fetchData = useCallback(async () => {
        setIsLoading(true);
        try {
            const { data: response } = await apiClient.get('/api/sns-items');
            setData(response);
        } catch (error) {
            toast.error("Failed to fetch Subscribe & Save item data.");
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
        { accessorKey: 'asin', header: 'ASIN', size: 120 },
        { 
            header: 'Recent Purchase',
            cell: ({ row }) => (
                <div>
                    <p className="font-semibold">${parseFloat(row.original.price_per_unit).toFixed(2)}</p>
                    <p className="text-xs text-text-muted">{new Date(row.original.order_placed_date).toLocaleDateString()}</p>
                </div>
            )
        },
        { 
            header: 'Previous Purchase',
            cell: ({ row }) => (
                row.original.prev_price ? (
                    <div>
                        <p className="font-semibold">${parseFloat(row.original.prev_price).toFixed(2)}</p>
                        <p className="text-xs text-text-muted">{new Date(row.original.prev_date).toLocaleDateString()}</p>
                    </div>
                ) : <span className="text-text-muted">N/A</span>
            )
        },
        {
            header: 'Price Change',
            cell: ({ row }) => {
                const currentPrice = parseFloat(row.original.price_per_unit);
                const prevPrice = parseFloat(row.original.prev_price);

                if (!prevPrice) return <span className="text-text-muted">-</span>;

                const change = currentPrice - prevPrice;
                const percentageChange = ((change / prevPrice) * 100).toFixed(1);

                let colorClass = 'text-text-muted';
                let indicator = '▬';
                if (change > 0) {
                    colorClass = 'text-danger';
                    indicator = '▲';
                } else if (change < 0) {
                    colorClass = 'text-success';
                    indicator = '▼';
                }

                return (
                    <div className={`font-bold text-center ${colorClass}`}>
                        <span>{indicator} ${Math.abs(change).toFixed(2)}</span>
                        <span className="text-xs ml-1">({percentageChange}%)</span>
                    </div>
                );
            }
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
                <h2 className="text-3xl font-semibold text-text-primary">Subscribe & Save History</h2>
                <button onClick={fetchData} disabled={isLoading} className="form-button-secondary">
                    {isLoading ? 'Refreshing...' : 'Refresh'}
                </button>
            </div>
            <div className="flex-grow overflow-auto">
                {isLoading ? <Spinner /> : (
                    data.length === 0 ? (
                        <div className="text-center p-10 text-text-muted">
                            <h3 className="text-xl font-semibold">No Subscribe & Save Items Found</h3>
                            <p className="mt-2">This table will populate once your imported orders include items from Subscribe & Save.</p>
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

export default SnsDataTable;

