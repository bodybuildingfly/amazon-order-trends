import React, { useState, useEffect } from 'react';
import apiClient from '../api';
import { toast } from 'react-toastify';
import { useAuth } from '../context/AuthContext';

// A simple modal component
const Modal = ({ isOpen, onClose, children }) => {
    if (!isOpen) return null;
    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex justify-center items-center">
            <div className="bg-surface p-6 rounded-2xl shadow-lg w-full max-w-md">
                <div className="flex justify-end">
                    <button onClick={onClose} className="text-text-secondary hover:text-text-primary">&times;</button>
                </div>
                {children}
            </div>
        </div>
    );
};

const UserManagementPage = () => {
    const { user: currentUser } = useAuth();
    const [users, setUsers] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user' });
    const [isSaving, setIsSaving] = useState(false);

    // State for modals
    const [selectedUser, setSelectedUser] = useState(null);
    const [isResetModalOpen, setResetModalOpen] = useState(false);
    const [isDeleteModalOpen, setDeleteModalOpen] = useState(false);
    const [newPassword, setNewPassword] = useState('');

    const fetchUsers = async () => {
        setIsLoading(true);
        try {
            const { data } = await apiClient.get('/api/users');
            setUsers(data);
        } catch (error) {
            toast.error('Failed to fetch users.');
            console.error(error);
        }
        setIsLoading(false);
    };

    useEffect(() => {
        fetchUsers();
    }, []);
    
    const handleNewUserChange = (e) => {
        const { name, value } = e.target;
        setNewUser(prev => ({ ...prev, [name]: value }));
    };

    const handleAddUser = async (e) => {
        e.preventDefault();
        setIsSaving(true);
        try {
            const { data: createdUser } = await apiClient.post('/api/users', newUser);
            setUsers(prev => [...prev, createdUser].sort((a, b) => a.username.localeCompare(b.username)));
            setNewUser({ username: '', password: '', role: 'user' });
            toast.success(`User '${createdUser.username}' created successfully.`);
        } catch (error) {
            toast.error(error.response?.data?.error || 'Failed to create user.');
        }
        setIsSaving(false);
    };
    
    const openResetModal = (user) => {
        setSelectedUser(user);
        setNewPassword('');
        setResetModalOpen(true);
    };

    const handleResetPassword = async () => {
        if (!newPassword) {
            toast.warn('Password cannot be empty.');
            return;
        }
        setIsSaving(true);
        try {
            await apiClient.post(`/api/users/${selectedUser.id}/reset-password`, { password: newPassword });
            toast.success(`Password for '${selectedUser.username}' has been reset.`);
            setResetModalOpen(false);
        } catch (error) {
            toast.error(error.response?.data?.error || 'Failed to reset password.');
        }
        setIsSaving(false);
    };
    
    const openDeleteModal = (user) => {
        setSelectedUser(user);
        setDeleteModalOpen(true);
    };

    const handleDeleteUser = async () => {
        setIsSaving(true);
        try {
            await apiClient.delete(`/api/users/${selectedUser.id}`);
            setUsers(prev => prev.filter(u => u.id !== selectedUser.id));
            toast.success(`User '${selectedUser.username}' has been deleted.`);
            setDeleteModalOpen(false);
        } catch (error) {
            toast.error(error.response?.data?.error || 'Failed to delete user.');
        }
        setIsSaving(false);
    };

    if (isLoading) {
        return <div className="flex justify-center items-center p-10"><div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin"></div></div>;
    }

    return (
        <>
            <div className="space-y-8 max-w-7xl mx-auto">
                {/* Add User Form */}
                <div className="bg-surface p-6 rounded-2xl shadow-lg">
                    <h2 className="text-3xl font-semibold text-text-primary mb-6">User Management</h2>
                    <form onSubmit={handleAddUser} className="space-y-4 max-w-lg">
                        <h3 className="font-semibold text-lg text-text-primary">Add New User</h3>
                        <div>
                            <label className="form-label">Username</label>
                            <input type="text" name="username" value={newUser.username} onChange={handleNewUserChange} className="form-input" required />
                        </div>
                        <div>
                            <label className="form-label">Password</label>
                            <input type="password" name="password" value={newUser.password} onChange={handleNewUserChange} className="form-input" required />
                        </div>
                        <div>
                            <label className="form-label">Role</label>
                            <select name="role" value={newUser.role} onChange={handleNewUserChange} className="form-input">
                                <option value="user">User</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>
                        <div className="flex justify-end">
                            <button type="submit" disabled={isSaving} className="form-button-primary">
                                {isSaving ? 'Adding...' : 'Add User'}
                            </button>
                        </div>
                    </form>
                </div>

                {/* Users Table */}
                <div className="bg-surface p-6 rounded-2xl shadow-lg">
                    <h3 className="font-semibold text-lg mb-4 text-text-primary">Existing Users</h3>
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-border-color">
                            <thead className="bg-surface-muted">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Username</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Role</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-text-secondary uppercase tracking-wider">Created At</th>
                                    <th className="relative px-6 py-3"><span className="sr-only">Actions</span></th>
                                </tr>
                            </thead>
                            <tbody className="bg-surface divide-y divide-border-color">
                                {users.map((user) => (
                                    <tr key={user.id}>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-text-primary">{user.username}</td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">{user.role}</td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">{new Date(user.created_at).toLocaleDateString()}</td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                                            <button onClick={() => openResetModal(user)} className="form-button-secondary">Reset Password</button>
                                            <button onClick={() => openDeleteModal(user)} disabled={currentUser.id === user.id} className="form-button-secondary bg-warning-surface text-warning-text-on-surface hover:bg-warning-surface-hover disabled:opacity-50">Delete</button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            {/* Reset Password Modal */}
            <Modal isOpen={isResetModalOpen} onClose={() => setResetModalOpen(false)}>
                <h3 className="text-lg font-semibold mb-4">Reset Password for {selectedUser?.username}</h3>
                <div>
                    <label className="form-label">New Password</label>
                    <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="form-input" />
                </div>
                <div className="flex justify-end mt-6 space-x-2">
                    <button onClick={() => setResetModalOpen(false)} className="form-button-secondary">Cancel</button>
                    <button onClick={handleResetPassword} disabled={isSaving} className="form-button-primary">
                        {isSaving ? 'Resetting...' : 'Reset Password'}
                    </button>
                </div>
            </Modal>

            {/* Delete User Modal */}
            <Modal isOpen={isDeleteModalOpen} onClose={() => setDeleteModalOpen(false)}>
                <h3 className="text-lg font-semibold mb-4">Delete User</h3>
                <p>Are you sure you want to delete the user '{selectedUser?.username}'? This action cannot be undone.</p>
                <div className="flex justify-end mt-6 space-x-2">
                    <button onClick={() => setDeleteModalOpen(false)} className="form-button-secondary">Cancel</button>
                    <button onClick={handleDeleteUser} disabled={isSaving} className="form-button-primary bg-error-surface text-error-text-on-surface hover:bg-error-surface-hover">
                        {isSaving ? 'Deleting...' : 'Delete User'}
                    </button>
                </div>
            </Modal>
        </>
    );
};

export default UserManagementPage;
