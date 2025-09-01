import React, { useState, useEffect, useMemo } from 'react';
import {
    useReactTable,
    getCoreRowModel,
    flexRender,
} from '@tanstack/react-table';
import { toast } from 'react-toastify';
import apiClient from '../api';

// --- Helper Components ---
const LoadingSpinner = () => (
    <div className="flex items-center justify-center h-full py-10">
        <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
    </div>
);

/**
 * @description A component that renders a fully-featured, server-side data table for items.
 */
const InteractiveDataTable = () => {
    const [data, setData] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    
    // Server-side state management
    const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 15 });
    const [sorting, setSorting] = useState([]);
    const [globalFilter, setGlobalFilter] = useState('');
    const [pageCount, setPageCount] = useState(0);

    // Debounce the global filter input to avoid excessive API calls
    const [debouncedFilter, setDebouncedFilter] = useState(globalFilter);
    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedFilter(globalFilter);
            setPagination(p => ({ ...p, pageIndex: 0 })); // Reset to first page on search
        }, 500);
        return () => clearTimeout(handler);
    }, [globalFilter]);

    // Fetch data from the API whenever pagination, sorting, or filtering changes
    useEffect(() => {
        const fetchData = async () => {
            setIsLoading(true);
            try {
                const params = new URLSearchParams({
                    page: pagination.pageIndex + 1,
                    limit: pagination.pageSize,
                });

                if (sorting.length > 0) {
                    params.append('sortBy', sorting[0].id);
                    params.append('sortOrder', sorting[0].desc ? 'desc' : 'asc');
                }

                if (debouncedFilter) {
                    params.append('filter[full_title]', debouncedFilter);
                }
                
                const { data: responseData } = await apiClient.get(`/api/items?${params.toString()}`);

                if (responseData && Array.isArray(responseData.data)) {
                    setData(responseData.data);
                    setPageCount(Math.ceil(responseData.total / pagination.pageSize));
                }
            } catch (error) {
                toast.error("Failed to fetch item data.");
                setData([]);
                setPageCount(0);
            } finally {
                setIsLoading(false);
            }
        };
        fetchData();
    }, [pagination, sorting, debouncedFilter]);

    // Define table columns
    const columns = useMemo(() => [
        {
            accessorKey: 'full_title',
            header: 'Product Title',
            cell: info => <div className="font-medium text-text-primary">{info.getValue()}</div>,
        },
        {
            accessorKey: 'asin',
            header: 'ASIN',
            cell: info => <span className="font-mono text-sm">{info.getValue()}</span>,
        },
        {
            accessorKey: 'price_per_unit',
            header: 'Price',
            cell: info => `$${parseFloat(info.getValue()).toFixed(2)}`,
        },
        {
            accessorKey: 'order_placed_date',
            header: 'Purchase Date',
            cell: info => new Date(info.getValue()).toLocaleDateString(),
        },
    ], []);
    
    // Initialize the table instance
    const table = useReactTable({
        data,
        columns,
        pageCount,
        state: {
            pagination,
            sorting,
            globalFilter,
        },
        onPaginationChange: setPagination,
        onSortingChange: setSorting,
        onGlobalFilterChange: setGlobalFilter,
        getCoreRowModel: getCoreRowModel(),
        manualPagination: true,
        manualSorting: true,
        manualFiltering: true,
    });

    return (
        <div className="bg-surface p-6 rounded-2xl shadow-lg">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-3xl font-semibold text-text-primary">All Purchased Items</h2>
                <input
                    type="text"
                    value={globalFilter ?? ''}
                    onChange={e => setGlobalFilter(e.target.value)}
                    className="form-input w-full md:w-1/3"
                    placeholder="Search all items..."
                />
            </div>
            
            <div className="overflow-x-auto">
                <table className="w-full">
                    <thead>
                        {table.getHeaderGroups().map(headerGroup => (
                            <tr key={headerGroup.id}>
                                {headerGroup.headers.map(header => (
                                    <th 
                                        key={header.id}
                                        className="p-3 text-left text-sm font-semibold text-text-secondary uppercase tracking-wider border-b border-border-color cursor-pointer"
                                        onClick={header.column.getToggleSortingHandler()}
                                    >
                                        {flexRender(header.column.columnDef.header, header.getContext())}
                                        {{
                                            asc: ' 🔼',
                                            desc: ' 🔽',
                                        }[header.column.getIsSorted()] ?? null}
                                    </th>
                                ))}
                            </tr>
                        ))}
                    </thead>
                    <tbody>
                        {isLoading ? (
                            <tr>
                                <td colSpan={columns.length}>
                                    <LoadingSpinner />
                                </td>
                            </tr>
                        ) : table.getRowModel().rows.length > 0 ? (
                            table.getRowModel().rows.map(row => (
                                <tr key={row.id} className="hover:bg-surface-hover border-b border-border-color">
                                    {row.getVisibleCells().map(cell => (
                                        <td key={cell.id} className="p-3 text-sm text-text-secondary">
                                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                        </td>
                                    ))}
                                </tr>
                            ))
                        ) : (
                            <tr>
                                <td colSpan={columns.length} className="text-center py-10 text-text-muted">
                                    No items found.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <div className="flex justify-between items-center mt-4">
                <button
                    onClick={() => table.previousPage()}
                    disabled={!table.getCanPreviousPage()}
                    className="form-button-secondary"
                >
                    Previous
                </button>
                <span className="text-sm text-text-muted">
                    Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
                </span>
                <button
                    onClick={() => table.nextPage()}
                    disabled={!table.getCanNextPage()}
                    className="form-button-secondary"
                >
                    Next
                </button>
            </div>
        </div>
    );
};

export default InteractiveDataTable;

