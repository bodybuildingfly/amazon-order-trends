import React from 'react';

const LoadingSpinner = () => (
    <div className="flex h-screen w-screen items-center justify-center bg-background">
        <div className="w-16 h-16 border-8 border-primary border-t-transparent rounded-full animate-spin"></div>
    </div>
);

export default LoadingSpinner;
