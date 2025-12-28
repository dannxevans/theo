# Service Booking Implementation - Code to Add

This document contains the code snippets to add to complete the service booking feature.

---

## 1. Add Helper Methods to ActionRouter Class

Add these methods at the end of the `ActionRouter` class in `backend/core/action_router.py` (after line 2067):

```python
    def _detect_service_category(self, user_text: str) -> str:
        """
        Detect if user is requesting a service booking (haircut, doctor, etc.).

        Args:
            user_text: User's input text

        Returns:
            Service category (haircut, doctor, dentist) or empty string if none detected
        """
        text_lower = user_text.lower()

        # Service keywords mapping
        service_patterns = {
            "haircut": ["haircut", "hair cut", "barber", "salon", "trim", "hairstyle"],
            "doctor": ["doctor", "physician", "gp", "medical appointment", "checkup"],
            "dentist": ["dentist", "dental", "teeth cleaning", "tooth"],
            "massage": ["massage", "spa", "therapist"],
            "gym": ["gym", "personal trainer", "fitness", "workout session"]
        }

        for category, keywords in service_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                return category

        return ""

    def _handle_service_booking(
        self,
        user_text: str,
        user_id: int,
        session_id: str,
        service_category: str
    ) -> Dict:
        """
        Handle external service booking with calendar-aware suggestions.

        Flow:
        1. Check for configured service provider
        2. Read user's calendar for availability
        3. Suggest optimal booking times
        4. Provide booking link/instructions

        Args:
            user_text: User's request
            user_id: User ID
            session_id: Session ID
            service_category: Type of service (haircut, doctor, etc.)

        Returns:
            Response with booking assistance
        """
        import json
        from datetime import timedelta

        # Check for service provider
        service_provider = self.memory.get_preferred_provider(user_id, service_category)

        if not service_provider:
            # No provider configured - offer to set one up
            return {
                "text": f"I don't have a {service_category} provider configured yet. "
                       f"Would you like to add one in Settings → Service Providers?",
                "provider": "action_router",
                "task_type": "book_appointment",
                "metadata": {
                    "service_category": service_category,
                    "needs_configuration": True
                }
            }

        # Get provider details
        provider_name = service_provider.get("name", f"{service_category} provider")
        booking_method = service_provider.get("booking_method", "manual")

        # Parse additional metadata if present
        additional_metadata = service_provider.get("additional_metadata")
        if isinstance(additional_metadata, str):
            try:
                additional_metadata = json.loads(additional_metadata)
            except:
                additional_metadata = {}
        elif not additional_metadata:
            additional_metadata = {}

        # Get typical duration and travel time
        typical_duration = additional_metadata.get("typical_duration_minutes", 30)
        travel_time_home = additional_metadata.get("travel_time_from_home", 15)
        travel_time_office = additional_metadata.get("travel_time_from_office", 15)
        booking_url = additional_metadata.get("booking_url", service_provider.get("api_base_url"))

        # Read calendar to find availability
        # Look ahead 2 weeks
        today = datetime.now()
        end_date = today + timedelta(days=14)

        # Load M365 provider to read calendar
        self.action_registry.load_providers(user_id)
        calendar_providers = self.action_registry.get_providers_by_capability("read_calendar", user_id)

        calendar_events = []
        if calendar_providers:
            provider_id, provider = calendar_providers[0]
            try:
                calendar_events = provider.read_calendar(today, end_date)
            except Exception as e:
                logging.warning(f"[ACTION_ROUTER] Failed to read calendar: {e}")

        # Find free slots
        free_slots = self._find_optimal_slots(
            calendar_events,
            start_date=today,
            end_date=end_date,
            duration_minutes=typical_duration + travel_time_home
        )

        # Build response
        if free_slots:
            slots_text = self._format_free_slots(free_slots[:5])  # Top 5 slots

            response_text = f"I found some good times for your {service_category} at {provider_name}:\n\n"
            response_text += slots_text
            response_text += f"\n\n"

            if booking_url:
                response_text += f"**Book here:** {booking_url}\n\n"
            else:
                response_text += f"Contact {provider_name} to book.\n\n"

            response_text += "Would you like me to add a reminder to your calendar once you've booked?"
        else:
            response_text = f"Your calendar is quite full! "
            response_text += f"You may want to check {provider_name} directly for availability.\n\n"

            if booking_url:
                response_text += f"**Book here:** {booking_url}"

        return {
            "text": response_text,
            "provider": "action_router",
            "task_type": "book_appointment",
            "metadata": {
                "service_category": service_category,
                "provider_name": provider_name,
                "booking_url": booking_url,
                "suggested_slots": [slot.isoformat() for slot in free_slots[:5]] if free_slots else []
            }
        }

    def _find_optimal_slots(
        self,
        calendar_events: list,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int = 60,
        preferred_hours: tuple = (9, 18)  # 9am to 6pm
    ) -> list:
        """
        Find optimal free time slots in the user's calendar.

        Args:
            calendar_events: List of existing calendar events
            start_date: Start of search range
            end_date: End of search range
            duration_minutes: Required duration for slot
            preferred_hours: Tuple of (start_hour, end_hour) for preferred times

        Returns:
            List of datetime objects representing optimal start times
        """
        from datetime import timedelta

        free_slots = []
        current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        while current_date <= end_date:
            # Skip past dates
            if current_date.date() < datetime.now().date():
                current_date += timedelta(days=1)
                continue

            # Only check weekdays (Monday=0, Sunday=6)
            if current_date.weekday() >= 5:  # Saturday or Sunday
                current_date += timedelta(days=1)
                continue

            # Check each hour in preferred range
            for hour in range(preferred_hours[0], preferred_hours[1]):
                slot_start = current_date.replace(hour=hour, minute=0)
                slot_end = slot_start + timedelta(minutes=duration_minutes)

                # Check if slot conflicts with any event
                is_free = True
                for event in calendar_events:
                    event_start = event.get("start_time")
                    event_end = event.get("end_time")

                    if isinstance(event_start, str):
                        event_start = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
                    if isinstance(event_end, str):
                        event_end = datetime.fromisoformat(event_end.replace('Z', '+00:00'))

                    # Check for overlap
                    if (slot_start < event_end and slot_end > event_start):
                        is_free = False
                        break

                if is_free and slot_start > datetime.now():
                    free_slots.append(slot_start)

            current_date += timedelta(days=1)

        # Sort by closeness to preferred times (favor early afternoon)
        def time_score(dt):
            # Prefer 1pm-3pm (13-15)
            hour = dt.hour
            if 13 <= hour < 15:
                return 0  # Best
            elif 15 <= hour < 17:
                return 1  # Good
            elif 11 <= hour < 13:
                return 2  # Morning
            else:
                return 3  # Other

        free_slots.sort(key=time_score)
        return free_slots

    def _format_free_slots(self, slots: list) -> str:
        """
        Format free time slots for display.

        Args:
            slots: List of datetime objects

        Returns:
            Formatted string with suggested times
        """
        if not slots:
            return "No free slots found."

        formatted = []
        for i, slot in enumerate(slots, 1):
            day = slot.strftime("%A, %B %d")
            time = slot.strftime("%I:%M %p").lstrip("0")
            formatted.append(f"{i}. {day} at {time}")

        return "\n".join(formatted)
```

---

## 2. Frontend Components

### Create `frontend/src/components/ServiceProviders.svelte`

This will be a new settings tab. Create this file with the following content:

```svelte
<script>
    import { onMount } from 'svelte';
    import { getToken } from '../lib/api.js';

    let providers = [];
    let loading = true;
    let error = null;
    let showAddModal = false;
    let editingProvider = null;

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
            const token = getToken();
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
        const token = getToken();

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

        const token = getToken();

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
                        {#if provider.additional_metadata}
                            {#try JSON.parse(provider.additional_metadata)}
                                {#if JSON.parse(provider.additional_metadata).booking_url}
                                    <p><strong>Booking URL:</strong> <a href={JSON.parse(provider.additional_metadata).booking_url} target="_blank">Open</a></p>
                                {/if}
                            {/try}
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
```

---

## 3. Integration Steps

1. **Add the helper methods to ActionRouter**:
   - Copy the three methods (`_detect_service_category`, `_handle_service_booking`, `_find_optimal_slots`, `_format_free_slots`) to the end of the `ActionRouter` class in `backend/core/action_router.py`

2. **Add the frontend component to Settings**:
   - Create `frontend/src/components/ServiceProviders.svelte` with the code above
   - Add a new tab in `frontend/src/components/Settings.svelte` for "Service Providers"

3. **Test the flow**:
   - Add your haircut provider via the UI
   - Try: "Book me a haircut"
   - THEO should suggest optimal times and provide your booking link

---

## 4. Example Service Provider Configuration

For your Cuts Barber example:

```json
{
  "name": "Cuts Barber - Rory",
  "category": "haircut",
  "provider_type": "manual",
  "booking_method": "manual",
  "trust_level": "manual",
  "preferred_for_category": true,
  "additional_metadata": {
    "booking_url": "https://book.squareup.com/appointments/1lnkcqzsw7cc9m/location/MZGDSMEMXS3/services",
    "typical_duration_minutes": 30,
    "travel_time_from_home": 18,
    "travel_time_from_office": 25,
    "location": "123 Main St"
  }
}
```

When you say "Book me a haircut", THEO will:
1. Check your calendar for the next 2 weeks
2. Find free slots (preferring afternoons)
3. Account for 30min haircut + 18min travel
4. Suggest top 5 slots
5. Provide your Square booking link

---

## Next Steps After Implementation

1. Test manual booking flow
2. Add Square API integration (Phase 2)
3. Add more provider types (doctor, dentist)
4. Enhance slot optimization (prefer specific days, etc.)

