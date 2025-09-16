import React from 'react';

const SkeletonLoader = ({ className }) => (
    <div className={`animate-pulse bg-surface-hover rounded ${className}`}></div>
);

export default SkeletonLoader;
