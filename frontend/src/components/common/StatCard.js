import React from 'react';

const StatCard = ({ title, value, icon }) => (
    <div className="bg-surface p-6 rounded-lg shadow-md flex items-center">
        <div className="mr-4">{icon}</div>
        <div>
            <p className="text-sm font-medium text-text-secondary">{title}</p>
            <p className="text-2xl font-semibold text-text-primary">{value}</p>
        </div>
    </div>
);

export default StatCard;
