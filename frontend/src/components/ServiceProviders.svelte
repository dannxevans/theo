<script>
    import { onMount } from 'svelte';

    let providers = [];
    let loading = true;
    let error = null;
    let showAddModal = false;
    let editingProvider = null;

    function getAuthToken() {
        return localStorage.getItem("auth_token");
    }

    // Form fields
    let formName = '';
    let formCategory = 'haircut';
    let formProviderType = 'manual';
    let formBookingUrl = '';
    let formTrustLevel = 'manual';
    let formPreferred = false;
    let formDuration = 30;
    let formTravelTimeHome = 15;
    let formTravelTimeOffice = 15;

    const categories = [
        { value: 'haircut', label: 'Haircut / Barber' },
        { value: 'doctor', label: 'Doctor / GP' },
        { value: 'dentist', label: 'Dentist' },
        { value: 'massage', label: 'Massage / Spa' },
        { value: 'gym', label: 'Gym / Trainer' },
        { value: 'other', label: 'Other' }
    ];

    const providerTypes = [
        { value: 'manual', label: 'Manual Booking (I book myself)' },
        { value: 'square_api', label: 'Square Appointments API' },
        { value: 'api', label: 'Generic API' }
    ];

    onMount(async () => {
        await loadProviders();
    });

    async function loadProviders() {
        loading = true;
        error = null;

        try {
            const token = getAuthToken();
            const response = await fetch('/api/service-providers', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error('Failed to load service providers');
            }

            const data = await response.json();
            providers = data.providers || [];
        } catch (err) {
            error = err.message;
            console.error('Failed to load providers:', err);
        } finally {
            loading = false;
        }
    }

    function openAddModal() {
        resetForm();
        showAddModal = true;
        editingProvider = null;
    }

    function openEditModal(provider) {
        editingProvider = provider;
        formName = provider.name;
        formCategory = provider.category;
        formProviderType = provider.provider_type;
        formTrustLevel = provider.trust_level || 'manual';
        formPreferred = provider.preferred_for_category || false;

        // Parse additional metadata
        try {
            const metadata = JSON.parse(provider.additional_metadata || '{}');
            formBookingUrl = metadata.booking_url || provider.api_base_url || '';
            formDuration = metadata.typical_duration_minutes || 30;
            formTravelTimeHome = metadata.travel_time_from_home || 15;
            formTravelTimeOffice = metadata.travel_time_from_office || 15;
        } catch (e) {
            formBookingUrl = provider.api_base_url || '';
        }

        showAddModal = true;
    }

    function resetForm() {
        formName = '';
        formCategory = 'haircut';
        formProviderType = 'manual';
        formBookingUrl = '';
        formTrustLevel = 'manual';
        formPreferred = false;
        formDuration = 30;
        formTravelTimeHome = 15;
        formTravelTimeOffice = 15;
    }

    async function saveProvider() {
        const token = getAuthToken();

        // Build additional metadata
        const metadata = {
            booking_url: formBookingUrl,
            typical_duration_minutes: parseInt(formDuration),
            travel_time_from_home: parseInt(formTravelTimeHome),
            travel_time_from_office: parseInt(formTravelTimeOffice)
        };

        const payload = {
            name: formName,
            category: formCategory,
            provider_type: formProviderType,
            trust_level: formTrustLevel,
            preferred_for_category: formPreferred,
            booking_method: formProviderType === 'manual' ? 'manual' : 'api',
            api_base_url: formBookingUrl,
            additional_metadata: JSON.stringify(metadata)
        };

        try {
            let response;
            if (editingProvider) {
                // Update
                response = await fetch(`/api/service-providers/${editingProvider.id}`, {
                    method: 'PUT',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });
            } else {
                // Create
                response = await fetch('/api/service-providers', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });
            }

            if (!response.ok) {
                throw new Error('Failed to save provider');
            }

            showAddModal = false;
            await loadProviders();
        } catch (err) {
            error = err.message;
            console.error('Failed to save provider:', err);
        }
    }

    async function deleteProvider(id) {
        if (!confirm('Are you sure you want to delete this provider?')) {
            return;
        }

        const token = getAuthToken();

        try {
            const response = await fetch(`/api/service-providers/${id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                throw new Error('Failed to delete provider');
            }

            await loadProviders();
        } catch (err) {
            error = err.message;
            console.error('Failed to delete provider:', err);
        }
    }

    function getBookingUrl(provider) {
        try {
            const metadata = JSON.parse(provider.additional_metadata || '{}');
            return metadata.booking_url || null;
        } catch (e) {
            return null;
        }
    }
</script>

<div class="service-providers">
    <div class="header">
        <h2>Service Providers</h2>
        <button class="btn-primary" on:click={openAddModal}>
            + Add Provider
        </button>
    </div>

    {#if error}
        <div class="error">{error}</div>
    {/if}

    {#if loading}
        <div class="loading">Loading providers...</div>
    {:else if providers.length === 0}
        <div class="empty-state">
            <p>No service providers configured yet.</p>
            <p>Add providers for services like haircuts, doctors, dentists, etc.</p>
            <button class="btn-primary" on:click={openAddModal}>
                Add Your First Provider
            </button>
        </div>
    {:else}
        <div class="providers-list">
            {#each providers as provider}
                <div class="provider-card">
                    <div class="provider-header">
                        <h3>{provider.name}</h3>
                        <div class="provider-actions">
                            <button class="btn-small" on:click={() => openEditModal(provider)}>
                                Edit
                            </button>
                            <button class="btn-small btn-danger" on:click={() => deleteProvider(provider.id)}>
                                Delete
                            </button>
                        </div>
                    </div>
                    <div class="provider-details">
                        <p><strong>Category:</strong> {provider.category}</p>
                        <p><strong>Type:</strong> {provider.provider_type === 'manual' ? 'Manual Booking' : 'API Integration'}</p>
                        {#if provider.preferred_for_category}
                            <span class="badge">Preferred</span>
                        {/if}
                        {#if getBookingUrl(provider)}
                            <p><strong>Booking URL:</strong> <a href={getBookingUrl(provider)} target="_blank">Open</a></p>
                        {/if}
                    </div>
                </div>
            {/each}
        </div>
    {/if}
</div>

{#if showAddModal}
    <div class="modal-overlay" on:click={() => showAddModal = false}>
        <div class="modal" on:click|stopPropagation>
            <div class="modal-header">
                <h2>{editingProvider ? 'Edit' : 'Add'} Service Provider</h2>
                <button class="close-btn" on:click={() => showAddModal = false}>×</button>
            </div>

            <div class="modal-body">
                <div class="form-group">
                    <label>Provider Name</label>
                    <input type="text" bind:value={formName} placeholder="e.g., Cuts Barber - Rory">
                </div>

                <div class="form-group">
                    <label>Category</label>
                    <select bind:value={formCategory}>
                        {#each categories as cat}
                            <option value={cat.value}>{cat.label}</option>
                        {/each}
                    </select>
                </div>

                <div class="form-group">
                    <label>Provider Type</label>
                    <select bind:value={formProviderType}>
                        {#each providerTypes as type}
                            <option value={type.value}>{type.label}</option>
                        {/each}
                    </select>
                </div>

                <div class="form-group">
                    <label>Booking URL</label>
                    <input type="url" bind:value={formBookingUrl} placeholder="https://...">
                    <small>The link where you book appointments</small>
                </div>

                <div class="form-group">
                    <label>Typical Duration (minutes)</label>
                    <input type="number" bind:value={formDuration} min="5" max="240">
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label>Travel Time from Home (minutes)</label>
                        <input type="number" bind:value={formTravelTimeHome} min="0" max="120">
                    </div>

                    <div class="form-group">
                        <label>Travel Time from Office (minutes)</label>
                        <input type="number" bind:value={formTravelTimeOffice} min="0" max="120">
                    </div>
                </div>

                <div class="form-group checkbox">
                    <label>
                        <input type="checkbox" bind:checked={formPreferred}>
                        Preferred provider for this category
                    </label>
                </div>
            </div>

            <div class="modal-footer">
                <button class="btn-secondary" on:click={() => showAddModal = false}>
                    Cancel
                </button>
                <button class="btn-primary" on:click={saveProvider}>
                    {editingProvider ? 'Update' : 'Add'} Provider
                </button>
            </div>
        </div>
    </div>
{/if}

<style>
    .service-providers {
        padding: 20px;
    }

    .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }

    .empty-state {
        text-align: center;
        padding: 40px;
        color: #666;
    }

    .providers-list {
        display: grid;
        gap: 15px;
    }

    .provider-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 15px;
        background: white;
    }

    .provider-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }

    .provider-header h3 {
        margin: 0;
        font-size: 1.1em;
    }

    .provider-actions {
        display: flex;
        gap: 10px;
    }

    .provider-details p {
        margin: 5px 0;
        font-size: 0.9em;
    }

    .badge {
        display: inline-block;
        padding: 2px 8px;
        background: #4CAF50;
        color: white;
        border-radius: 12px;
        font-size: 0.8em;
        margin-left: 10px;
    }

    .modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    }

    .modal {
        background: white;
        border-radius: 8px;
        width: 90%;
        max-width: 600px;
        max-height: 90vh;
        overflow-y: auto;
    }

    .modal-header {
        padding: 20px;
        border-bottom: 1px solid #ddd;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .modal-header h2 {
        margin: 0;
    }

    .close-btn {
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        padding: 0;
        width: 30px;
        height: 30px;
    }

    .modal-body {
        padding: 20px;
    }

    .form-group {
        margin-bottom: 15px;
    }

    .form-group label {
        display: block;
        margin-bottom: 5px;
        font-weight: 500;
    }

    .form-group input,
    .form-group select {
        width: 100%;
        padding: 8px;
        border: 1px solid #ddd;
        border-radius: 4px;
    }

    .form-group small {
        display: block;
        margin-top: 5px;
        color: #666;
        font-size: 0.85em;
    }

    .form-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 15px;
    }

    .form-group.checkbox label {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .form-group.checkbox input {
        width: auto;
    }

    .modal-footer {
        padding: 20px;
        border-top: 1px solid #ddd;
        display: flex;
        justify-content: flex-end;
        gap: 10px;
    }

    .btn-primary, .btn-secondary, .btn-small, .btn-danger {
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
    }

    .btn-primary {
        background: #007bff;
        color: white;
    }

    .btn-secondary {
        background: #6c757d;
        color: white;
    }

    .btn-small {
        padding: 4px 12px;
        font-size: 13px;
        background: #007bff;
        color: white;
    }

    .btn-danger {
        background: #dc3545;
        color: white;
    }

    .error {
        padding: 10px;
        background: #fee;
        border: 1px solid #fcc;
        border-radius: 4px;
        color: #c00;
        margin-bottom: 15px;
    }

    .loading {
        text-align: center;
        padding: 40px;
        color: #666;
    }
</style>
