<script>
    import { onMount } from 'svelte';
    import { listUsers, createUser, updateUser, resetUserPassword } from '../../lib/api';

    let users = [];
    let loading = true;
    let showDisabled = false;
    let searchQuery = '';
    let sortBy = 'username';
    let sortOrder = 'asc';

    // Modals
    let showCreateModal = false;
    let showEditModal = false;
    let showResetPasswordModal = false;
    let showDeactivateConfirm = false;
    let showPasswordDisplay = false;

    // Selected user for operations
    let selectedUser = null;

    // Form state
    let newUsername = '';
    let newName = '';
    let newEmail = '';
    let newIsAdmin = false;
    let editUsername = '';
    let editName = '';
    let editEmail = '';
    let editIsAdmin = false;
    let editIsEnabled = true;

    // Generated password display
    let generatedPassword = '';

    // Messages
    let error = '';
    let success = '';

    onMount(async () => {
        await loadUsers();
    });

    async function loadUsers() {
        loading = true;
        error = '';
        try {
            const response = await listUsers(showDisabled);
            users = response.users;
        } catch (e) {
            error = e.message || 'Failed to load users';
        } finally {
            loading = false;
        }
    }

    async function handleCreateUser() {
        if (!newUsername.trim()) {
            error = 'Username is required';
            return;
        }

        try {
            const response = await createUser(newUsername, newIsAdmin, newName || null, newEmail || null);
            generatedPassword = response.password;
            showCreateModal = false;
            showPasswordDisplay = true;
            await loadUsers();
            success = `User "${newUsername}" created successfully`;
            newUsername = '';
            newName = '';
            newEmail = '';
            newIsAdmin = false;
        } catch (e) {
            error = e.message || 'Failed to create user';
        }
    }

    function openEditModal(user) {
        selectedUser = user;
        editUsername = user.username;
        editName = user.name || '';
        editEmail = user.email || '';
        editIsAdmin = user.is_admin;
        editIsEnabled = user.is_enabled;
        showEditModal = true;
        error = '';
    }

    async function handleUpdateUser() {
        if (!selectedUser) return;

        const updates = {};
        if (editUsername !== selectedUser.username) updates.username = editUsername;
        if ((editName || null) !== (selectedUser.name || null)) updates.name = editName || null;
        if ((editEmail || null) !== (selectedUser.email || null)) updates.email = editEmail || null;
        if (editIsAdmin !== selectedUser.is_admin) updates.is_admin = editIsAdmin;
        if (editIsEnabled !== selectedUser.is_enabled) updates.is_enabled = editIsEnabled;

        if (Object.keys(updates).length === 0) {
            showEditModal = false;
            return;
        }

        try {
            await updateUser(selectedUser.id, updates);
            showEditModal = false;
            await loadUsers();
            success = `User "${selectedUser.username}" updated successfully`;
        } catch (e) {
            error = e.message || 'Failed to update user';
        }
    }

    function openDeactivateConfirm(user) {
        selectedUser = user;
        showDeactivateConfirm = true;
        error = '';
    }

    async function handleDeactivateUser() {
        if (!selectedUser) return;

        try {
            await updateUser(selectedUser.id, { is_enabled: false });
            showDeactivateConfirm = false;
            await loadUsers();
            success = `User "${selectedUser.username}" deactivated successfully`;
        } catch (e) {
            error = e.message || 'Failed to deactivate user';
        }
    }

    function openResetPasswordModal(user) {
        selectedUser = user;
        showResetPasswordModal = true;
        error = '';
    }

    async function handleResetPassword() {
        if (!selectedUser) return;

        try {
            const response = await resetUserPassword(selectedUser.id);
            generatedPassword = response.password;
            showResetPasswordModal = false;
            showPasswordDisplay = true;
            success = `Password reset for "${selectedUser.username}"`;
        } catch (e) {
            error = e.message || 'Failed to reset password';
        }
    }

    function copyToClipboard(text) {
        navigator.clipboard.writeText(text);
        success = 'Password copied to clipboard';
    }

    // Computed
    $: filteredUsers = users.filter(u =>
        u.username.toLowerCase().includes(searchQuery.toLowerCase())
    );

    $: sortedUsers = [...filteredUsers].sort((a, b) => {
        let aVal = a[sortBy];
        let bVal = b[sortBy];

        if (typeof aVal === 'string') {
            aVal = aVal.toLowerCase();
            bVal = bVal.toLowerCase();
        }

        if (sortOrder === 'asc') {
            return aVal > bVal ? 1 : -1;
        } else {
            return aVal < bVal ? 1 : -1;
        }
    });

    function toggleSort(field) {
        if (sortBy === field) {
            sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
        } else {
            sortBy = field;
            sortOrder = 'asc';
        }
    }

    function formatDate(dateString) {
        if (!dateString) return 'Never';
        return new Date(dateString).toLocaleDateString();
    }

    function clearMessages() {
        setTimeout(() => {
            error = '';
            success = '';
        }, 5000);
    }

    $: if (error || success) clearMessages();
</script>

<div class="user-management">
    <div class="header">
        <h2>User Management</h2>
        <button class="btn-primary" on:click={() => { showCreateModal = true; error = ''; }}>
            Create User
        </button>
    </div>

    {#if error}
        <div class="alert alert-error">{error}</div>
    {/if}

    {#if success}
        <div class="alert alert-success">{success}</div>
    {/if}

    <div class="controls">
        <input
            type="text"
            placeholder="Search users..."
            bind:value={searchQuery}
            class="search-input"
        />

        <label class="checkbox-label">
            <input type="checkbox" bind:checked={showDisabled} on:change={loadUsers} />
            Show deactivated users
        </label>
    </div>

    {#if loading}
        <div class="loading">Loading users...</div>
    {:else}
        <table class="users-table">
            <thead>
                <tr>
                    <th on:click={() => toggleSort('name')} class="sortable">
                        Name {sortBy === 'name' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
                    </th>
                    <th on:click={() => toggleSort('username')} class="sortable">
                        Username {sortBy === 'username' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
                    </th>
                    <th on:click={() => toggleSort('email')} class="sortable">
                        Email {sortBy === 'email' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
                    </th>
                    <th on:click={() => toggleSort('is_admin')} class="sortable">
                        Role {sortBy === 'is_admin' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
                    </th>
                    <th on:click={() => toggleSort('is_enabled')} class="sortable">
                        Status {sortBy === 'is_enabled' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
                    </th>
                    <th>Activity</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {#each sortedUsers as user}
                    <tr>
                        <td>{user.name || '—'}</td>
                        <td>{user.username}</td>
                        <td>{user.email || '—'}</td>
                        <td>
                            <span class="badge" class:badge-admin={user.is_admin}>
                                {user.is_admin ? 'Admin' : 'User'}
                            </span>
                        </td>
                        <td>
                            <span class="badge" class:badge-active={user.is_enabled} class:badge-inactive={!user.is_enabled}>
                                {user.is_enabled ? 'Active' : 'Deactivated'}
                            </span>
                        </td>
                        <td class="stats">
                            <div>{user.stats.session_count} sessions</div>
                            <div>{user.stats.api_key_count} API keys</div>
                            <div class="last-activity">
                                Last: {formatDate(user.stats.last_activity)}
                            </div>
                        </td>
                        <td class="actions">
                            <button class="btn-sm" on:click={() => openEditModal(user)}>Edit</button>
                            <button class="btn-sm" on:click={() => openResetPasswordModal(user)}>Reset Password</button>
                            {#if user.is_enabled}
                                <button class="btn-sm btn-danger" on:click={() => openDeactivateConfirm(user)}>
                                    Deactivate
                                </button>
                            {:else}
                                <button class="btn-sm btn-success" on:click={() => updateUser(user.id, { is_enabled: true }).then(loadUsers)}>
                                    Activate
                                </button>
                            {/if}
                        </td>
                    </tr>
                {/each}
            </tbody>
        </table>
    {/if}
</div>

<!-- Create User Modal -->
{#if showCreateModal}
    <div class="modal-backdrop" on:click={() => showCreateModal = false}>
        <div class="modal" on:click|stopPropagation>
            <h3>Create New User</h3>

            <div class="form-group">
                <label>Name</label>
                <input type="text" bind:value={newName} placeholder="Enter full name" />
            </div>

            <div class="form-group">
                <label>Username</label>
                <input type="text" bind:value={newUsername} placeholder="Enter username" />
            </div>

            <div class="form-group">
                <label>Email</label>
                <input type="email" bind:value={newEmail} placeholder="Enter email address" />
            </div>

            <div class="form-group">
                <label class="checkbox-label">
                    <input type="checkbox" bind:checked={newIsAdmin} />
                    Admin user
                </label>
            </div>

            <p class="note">A random secure password will be generated and shown once.</p>

            <div class="modal-actions">
                <button class="btn-secondary" on:click={() => showCreateModal = false}>Cancel</button>
                <button class="btn-primary" on:click={handleCreateUser}>Create</button>
            </div>
        </div>
    </div>
{/if}

<!-- Edit User Modal -->
{#if showEditModal}
    <div class="modal-backdrop" on:click={() => showEditModal = false}>
        <div class="modal" on:click|stopPropagation>
            <h3>Edit User</h3>

            <div class="form-group">
                <label>Name</label>
                <input type="text" bind:value={editName} placeholder="Enter full name" />
            </div>

            <div class="form-group">
                <label>Username</label>
                <input type="text" bind:value={editUsername} />
            </div>

            <div class="form-group">
                <label>Email</label>
                <input type="email" bind:value={editEmail} placeholder="Enter email address" />
            </div>

            <div class="form-group">
                <label class="checkbox-label">
                    <input type="checkbox" bind:checked={editIsAdmin} />
                    Admin user
                </label>
            </div>

            <div class="form-group">
                <label class="checkbox-label">
                    <input type="checkbox" bind:checked={editIsEnabled} />
                    Account enabled
                </label>
            </div>

            <div class="modal-actions">
                <button class="btn-secondary" on:click={() => showEditModal = false}>Cancel</button>
                <button class="btn-primary" on:click={handleUpdateUser}>Save</button>
            </div>
        </div>
    </div>
{/if}

<!-- Reset Password Modal -->
{#if showResetPasswordModal}
    <div class="modal-backdrop" on:click={() => showResetPasswordModal = false}>
        <div class="modal" on:click|stopPropagation>
            <h3>Reset Password</h3>

            <p>Generate a new random password for <strong>{selectedUser?.username}</strong>?</p>
            <p class="note">This will invalidate all active sessions. The new password will be shown once.</p>

            <div class="modal-actions">
                <button class="btn-secondary" on:click={() => showResetPasswordModal = false}>Cancel</button>
                <button class="btn-primary" on:click={handleResetPassword}>Reset Password</button>
            </div>
        </div>
    </div>
{/if}

<!-- Deactivate Confirm Modal -->
{#if showDeactivateConfirm}
    <div class="modal-backdrop" on:click={() => showDeactivateConfirm = false}>
        <div class="modal" on:click|stopPropagation>
            <h3>Deactivate User</h3>

            <p>Deactivate user <strong>{selectedUser?.username}</strong>?</p>
            <p class="note">The user will not be able to log in. You can re-enable the account later.</p>

            <div class="modal-actions">
                <button class="btn-secondary" on:click={() => showDeactivateConfirm = false}>Cancel</button>
                <button class="btn-danger" on:click={handleDeactivateUser}>Deactivate</button>
            </div>
        </div>
    </div>
{/if}

<!-- Password Display Modal -->
{#if showPasswordDisplay}
    <div class="modal-backdrop" on:click={() => showPasswordDisplay = false}>
        <div class="modal" on:click|stopPropagation>
            <h3>Password Generated</h3>

            <p><strong>IMPORTANT:</strong> This password will only be shown once. Copy it now.</p>

            <div class="password-display">
                <code>{generatedPassword}</code>
                <button class="btn-sm" on:click={() => copyToClipboard(generatedPassword)}>
                    Copy
                </button>
            </div>

            <div class="modal-actions">
                <button class="btn-primary" on:click={() => showPasswordDisplay = false}>Done</button>
            </div>
        </div>
    </div>
{/if}

<style>
    .user-management {
        padding: 1.5rem;
    }

    .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.5rem;
    }

    h2 {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 600;
        color: #111827;
    }

    .controls {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
        align-items: center;
    }

    .search-input {
        flex: 1;
        padding: 0.625rem;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        font-size: 0.875rem;
    }

    .search-input:focus {
        outline: none;
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }

    .loading {
        text-align: center;
        padding: 2rem;
        color: #6b7280;
    }

    .users-table {
        width: 100%;
        border-collapse: collapse;
        background-color: white;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }

    .users-table th {
        text-align: left;
        padding: 0.875rem;
        border-bottom: 2px solid #e5e7eb;
        background-color: #f9fafb;
        font-weight: 600;
        font-size: 0.875rem;
        color: #374151;
    }

    .users-table th.sortable {
        cursor: pointer;
        user-select: none;
    }

    .users-table th.sortable:hover {
        background-color: #f3f4f6;
    }

    .users-table td {
        padding: 0.875rem;
        border-bottom: 1px solid #e5e7eb;
        font-size: 0.875rem;
    }

    .users-table tbody tr:hover {
        background-color: #f9fafb;
    }

    .badge {
        display: inline-block;
        padding: 0.25rem 0.625rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.025em;
    }

    .badge-admin {
        background-color: #dbeafe;
        color: #1e40af;
    }

    .badge-active {
        background-color: #d1fae5;
        color: #065f46;
    }

    .badge-inactive {
        background-color: #fee2e2;
        color: #991b1b;
    }

    .stats {
        font-size: 0.8125rem;
        color: #6b7280;
    }

    .stats > div {
        margin-bottom: 0.25rem;
    }

    .last-activity {
        font-size: 0.75rem;
        color: #9ca3af;
    }

    .actions {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
    }

    .modal-backdrop {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    }

    .modal {
        background-color: white;
        padding: 2rem;
        border-radius: 12px;
        max-width: 500px;
        width: 90%;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
    }

    .modal h3 {
        margin: 0 0 1.5rem 0;
        font-size: 1.25rem;
        font-weight: 600;
        color: #111827;
    }

    .form-group {
        margin-bottom: 1.25rem;
    }

    .form-group label {
        display: block;
        margin-bottom: 0.5rem;
        font-weight: 500;
        font-size: 0.875rem;
        color: #374151;
    }

    .form-group input[type="text"] {
        width: 100%;
        padding: 0.625rem;
        border: 1px solid #d1d5db;
        border-radius: 6px;
        font-size: 0.875rem;
    }

    .form-group input[type="text"]:focus {
        outline: none;
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }

    .checkbox-label {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        cursor: pointer;
        font-weight: normal;
        font-size: 0.875rem;
    }

    .checkbox-label input[type="checkbox"] {
        cursor: pointer;
    }

    .note {
        font-size: 0.8125rem;
        color: #6b7280;
        margin: 1rem 0;
        line-height: 1.5;
    }

    .password-display {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 1rem;
        background-color: #f9fafb;
        border-radius: 6px;
        margin: 1rem 0;
        border: 1px solid #e5e7eb;
    }

    .password-display code {
        flex: 1;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 1rem;
        word-break: break-all;
        color: #111827;
    }

    .modal-actions {
        display: flex;
        gap: 0.75rem;
        justify-content: flex-end;
        margin-top: 1.5rem;
    }

    .alert {
        padding: 0.875rem 1rem;
        border-radius: 6px;
        margin-bottom: 1rem;
        font-size: 0.875rem;
    }

    .alert-error {
        background-color: #fee2e2;
        color: #991b1b;
        border: 1px solid #fecaca;
    }

    .alert-success {
        background-color: #d1fae5;
        color: #065f46;
        border: 1px solid #a7f3d0;
    }

    .btn-primary, .btn-secondary, .btn-danger, .btn-success, .btn-sm {
        padding: 0.5rem 1rem;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 500;
        font-size: 0.875rem;
        transition: all 0.2s;
    }

    .btn-primary {
        background-color: #3b82f6;
        color: white;
    }

    .btn-primary:hover {
        background-color: #2563eb;
    }

    .btn-secondary {
        background-color: #e5e7eb;
        color: #374151;
    }

    .btn-secondary:hover {
        background-color: #d1d5db;
    }

    .btn-danger {
        background-color: #dc2626;
        color: white;
    }

    .btn-danger:hover {
        background-color: #b91c1c;
    }

    .btn-success {
        background-color: #10b981;
        color: white;
    }

    .btn-success:hover {
        background-color: #059669;
    }

    .btn-sm {
        padding: 0.375rem 0.75rem;
        font-size: 0.8125rem;
        background-color: #f3f4f6;
        color: #374151;
    }

    .btn-sm:hover {
        background-color: #e5e7eb;
    }

    .btn-sm.btn-danger {
        background-color: #dc2626;
        color: white;
    }

    .btn-sm.btn-danger:hover {
        background-color: #b91c1c;
    }

    .btn-sm.btn-success {
        background-color: #10b981;
        color: white;
    }

    .btn-sm.btn-success:hover {
        background-color: #059669;
    }
</style>
