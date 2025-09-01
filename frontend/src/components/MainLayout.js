import React from 'react';
import { Link, useLocation } from 'react-router-dom';

// --- Component & Context Imports ---
import ThemeToggle from './ThemeToggle';
import { useAuth } from '../context/AuthContext';

// --- Icon Imports ---
const TableIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.37 2.63 14 7l-1.5-1.5" /><path d="m21.5 5.5-1.5-1.5" /></svg>;
const SettingsIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06-.06a1.65 1.65 0 0 0-.33-1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>;
const SnsIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>;
const UsersIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>;

// --- Helper Components ---
const NavLink = ({ to, icon, children }) => {
    const location = useLocation();
    const isActive = location.pathname.startsWith(to);
    const activeClasses = 'bg-surface-hover text-primary font-bold';
    const inactiveClasses = 'text-text-secondary hover:bg-surface-hover hover:text-text-primary';
    
    return (
        <Link to={to} className={`w-full flex items-center px-3 py-2.5 rounded-lg transition-colors duration-200 ${isActive ? activeClasses : inactiveClasses}`}>
            {icon}
            <span className="ml-3">{children}</span>
        </Link>
    );
};

/**
 * @description The main layout for the authenticated part of the application.
 */
const MainLayout = ({ children }) => {
    const { user, logout } = useAuth();

    return (
        <div className="min-h-screen bg-background text-text-primary">
            <div className="grid grid-cols-12">
                {/* --- Left Sidebar --- */}
                <aside className="col-span-3 bg-surface border-r border-border-color h-screen p-6 flex flex-col">
                    <h1 className="text-2xl font-bold text-text-primary mb-10 text-center">Amazon Order Trends</h1>
                    <nav className="space-y-2 flex-grow">
                        <NavLink to="/table" icon={<TableIcon />}>All Orders</NavLink>
                        {/* NEW: Navigation link for Subscribe & Save page */}
                        <NavLink to="/sns-table" icon={<SnsIcon />}>Subscribe & Save</NavLink>
                    </nav>
                    {/* --- Admin & User Section --- */}
                    <div className="flex-shrink-0 pt-6 border-t border-border-color">
                        <div className="space-y-2 mb-4">
                             <NavLink to="/settings" icon={<SettingsIcon />}>Settings</NavLink>
                            {user?.role === 'admin' && (
                                <NavLink to="/user-management" icon={<UsersIcon />}>User Management</NavLink>
                            )}
                        </div>
                        <div className="grid grid-cols-3 items-center">
                            <div />
                            <div className="text-center">
                                <p className="text-sm text-text-secondary">Signed in as <span className="font-bold">{user?.username}</span></p>
                                <button onClick={logout} className="text-sm text-text-accent hover:underline">Logout</button>
                            </div>
                            <div className="flex justify-end">
                                <ThemeToggle />
                            </div>
                        </div>
                    </div>
                </aside>

                {/* --- Main Content Area --- */}
                <main className="col-span-9 p-8 overflow-y-auto h-screen">
                    {children}
                </main>
            </div>
        </div>
    );
};

export default MainLayout;

