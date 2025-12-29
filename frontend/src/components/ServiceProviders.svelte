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
    <div class="page-header">
        <div>
            <h2>Service Providers</h2>
            <p class="subtitle">Manage your service providers for appointments and bookings.</p>
        </div>
        <button class="btn-primary" on:click={openAddModal}>
            + Add Provider
        </button>
    </div>

    {#if error}
        <div class="error-message">{error}</div>
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
                            <span class="status-badge status-badge--success">Preferred</span>
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
    /* Match standard settings page structure */
    .service-providers {
        max-width: 900px;
        margin: 0 auto;
    }

    .page-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: var(--space-6);
        gap: var(--space-4);
    }

    .page-header h2 {
        margin: 0 0 var(--space-2) 0;
    }

    .page-header .subtitle {
        margin: 0;
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
    }

    .providers-list {
        display: grid;
        gap: var(--space-4);
    }

    .provider-card {
        border: 1px solid var(--border-primary);
        border-radius: var(--radius-lg);
        padding: var(--space-4);
        background: var(--bg-tertiary);
    }

    .provider-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: var(--space-3);
    }

    .provider-header h3 {
        margin: 0;
        font-size: var(--font-size-lg);
        color: var(--text-primary);
    }

    .provider-actions {
        display: flex;
        gap: var(--space-2);
    }

    .provider-details p {
        margin: var(--space-1) 0;
        font-size: var(--font-size-sm);
        color: var(--text-secondary);
    }

    .close-btn {
        background: none;
        border: none;
        font-size: var(--font-size-2xl);
        cursor: pointer;
        padding: 0;
        width: 30px;
        height: 30px;
        color: var(--text-primary);
    }

    .form-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--space-4);
    }

    .form-group.checkbox label {
        display: flex;
        align-items: center;
        gap: var(--space-2);
    }

    .form-group.checkbox input {
        width: auto;
    }

    .loading {
        text-align: center;
        padding: var(--space-10);
        color: var(--text-secondary);
    }

    /* All other styles now imported from global CSS:
       - .empty-state from utilities.css
       - .status-badge--success from utilities.css
       - .modal-overlay, .modal, .modal-header, .modal-body, .modal-footer from modals.css
       - .form-group from forms.css
       - .btn-primary, .btn-secondary, .btn-small, .btn-danger from buttons.css
       - .error-message from settings.css
    */
</style>
