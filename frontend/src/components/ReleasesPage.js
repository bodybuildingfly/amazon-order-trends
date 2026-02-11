import React, { useState, useEffect } from 'react';
import apiClient from '../api';
import ReactMarkdown from 'react-markdown';

const ReleasesPage = () => {
    const [releases, setReleases] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchReleases = async () => {
            try {
                const response = await apiClient.get('/api/releases');
                setReleases(response.data);
                setLoading(false);
            } catch (err) {
                console.error("Failed to fetch releases:", err);
                setError('Failed to fetch releases. Please try again later.');
                setLoading(false);
            }
        };

        fetchReleases();
    }, []);

    if (loading) {
        return <div className="text-text-primary p-4">Loading releases...</div>;
    }

    if (error) {
        return <div className="text-danger p-4">{error}</div>;
    }

    return (
        <div className="container mx-auto p-4">
            <h1 className="text-2xl font-bold mb-6 text-text-primary">Application Releases</h1>
            <div className="space-y-6">
                {releases.map(release => (
                    <div key={release.id} className="bg-surface p-6 rounded-lg shadow border border-border-color">
                        <div className="flex justify-between items-start mb-4">
                            <div>
                                <h2 className="text-xl font-semibold text-text-primary">
                                    <a href={release.html_url} target="_blank" rel="noopener noreferrer" className="hover:text-text-accent transition-colors">
                                        {release.name || release.tag_name}
                                    </a>
                                </h2>
                                <p className="text-sm text-text-secondary mt-1">
                                    Published on {new Date(release.published_at).toLocaleDateString()}
                                </p>
                            </div>
                            <span className="bg-surface-hover text-text-primary px-3 py-1 rounded-full text-xs font-medium border border-border-color">
                                {release.tag_name}
                            </span>
                        </div>
                        <div className="prose prose-sm max-w-none text-text-secondary">
                            <ReactMarkdown>{release.body}</ReactMarkdown>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default ReleasesPage;
