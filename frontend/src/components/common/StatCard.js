import React from 'react';

const StatCard = ({ title, value, icon, customColorClass }) => (
    <div className={`${customColorClass ? customColorClass : 'bg-surface'} p-6 rounded-lg shadow-md flex items-center`}>
        {icon && <div className="mr-4">{icon}</div>}
        <div>
            <p className={`text-sm font-medium ${customColorClass ? 'text-current opacity-80' : 'text-text-secondary'}`}>{title}</p>
            <p className={`text-2xl font-semibold ${customColorClass ? 'text-current' : 'text-text-primary'}`}>{value}</p>
        </div>
    </div>
);

export default StatCard;
