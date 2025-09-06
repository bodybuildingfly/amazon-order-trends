import React from 'react';

const SkeletonLoader = ({ className }) => (
    <div className={`animate-pulse bg-gray-300 dark:bg-gray-700 rounded ${className}`}></div>
);

export default SkeletonLoader;
