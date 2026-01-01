<script>
  import { onMount } from "svelte";
  import { getProactiveSettings, updateProactiveSettings } from "../../lib/api.js";

  let settings = {
    calendar_enabled: true,
    email_enabled: true,
    calendar_lead_time_minutes: 15,
    calendar_check_frequency_minutes: 15,
    email_check_frequency_minutes: 15,
    email_digest_frequency_minutes: 60,
    max_messages_per_hour: 10,
    quiet_hours_enabled: false,
    quiet_hours_start: "22:00",
    quiet_hours_end: "07:00",
    frontend_poll_interval_minutes: 5
  };

  let loading = false;
  let saving = false;
  let saveMessage = "";

  onMount(async () => {
    await loadSettings();
  });

  async function loadSettings() {
    try {
      loading = true;
      const data = await getProactiveSettings();

      // Format time strings for HTML time inputs
      if (data.quiet_hours_start) {
        data.quiet_hours_start = data.quiet_hours_start.substring(0, 5);
      }
      if (data.quiet_hours_end) {
        data.quiet_hours_end = data.quiet_hours_end.substring(0, 5);
      }

      settings = { ...settings, ...data };
    } catch (err) {
      console.error("Failed to load proactive settings:", err);
    } finally {
      loading = false;
    }
  }

  async function saveSettings() {
    try {
      saving = true;
      saveMessage = "";

      // Convert time strings to full format (HH:MM:SS)
      const saveData = { ...settings };
      if (saveData.quiet_hours_start && !saveData.quiet_hours_start.includes(":00")) {
        saveData.quiet_hours_start = saveData.quiet_hours_start + ":00";
      }
      if (saveData.quiet_hours_end && !saveData.quiet_hours_end.includes(":00")) {
        saveData.quiet_hours_end = saveData.quiet_hours_end + ":00";
      }

      await updateProactiveSettings(saveData);
      saveMessage = "Settings saved successfully";

      setTimeout(() => {
        saveMessage = "";
      }, 3000);
    } catch (err) {
      console.error("Failed to save proactive settings:", err);
      saveMessage = "Error saving settings";
    } finally {
      saving = false;
    }
  }
</script>

<div class="proactive-settings">
  {#if loading}
    <p class="loading-state">Loading settings...</p>
  {:else}
    <!-- Calendar Settings -->
    <div class="subsection">
      <h4>Calendar Reminders</h4>

      <div class="setting-row">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={settings.calendar_enabled} />
          <span>Enable calendar reminders</span>
        </label>
        <span class="setting-hint">Get notified before upcoming calendar events</span>
      </div>

      {#if settings.calendar_enabled}
        <div class="indent">
          <div class="setting-row">
            <label class="input-label">
              <span>Lead time (minutes before event)</span>
              <input
                type="number"
                bind:value={settings.calendar_lead_time_minutes}
                min="5"
                max="60"
                step="5"
                class="number-input"
              />
            </label>
            <span class="setting-hint">How far in advance to notify you</span>
          </div>

          <div class="setting-row">
            <label class="input-label">
              <span>Check frequency (minutes)</span>
              <input
                type="number"
                bind:value={settings.calendar_check_frequency_minutes}
                min="5"
                max="60"
                step="5"
                class="number-input"
              />
            </label>
            <span class="setting-hint">How often to check for upcoming events</span>
          </div>
        </div>
      {/if}
    </div>

    <!-- Email Settings -->
    <div class="subsection">
      <h4>Email Notifications</h4>

      <div class="setting-row">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={settings.email_enabled} />
          <span>Enable email notifications</span>
        </label>
        <span class="setting-hint">Get notified about important emails and daily summaries</span>
      </div>

      {#if settings.email_enabled}
        <div class="indent">
          <div class="setting-row">
            <label class="input-label">
              <span>Check frequency (minutes)</span>
              <input
                type="number"
                bind:value={settings.email_check_frequency_minutes}
                min="5"
                max="60"
                step="5"
                class="number-input"
              />
            </label>
            <span class="setting-hint">How often to check for important emails</span>
          </div>

          <div class="setting-row">
            <label class="input-label">
              <span>Digest frequency (minutes)</span>
              <input
                type="number"
                bind:value={settings.email_digest_frequency_minutes}
                min="30"
                max="240"
                step="30"
                class="number-input"
              />
            </label>
            <span class="setting-hint">How often to send email summaries</span>
          </div>
        </div>
      {/if}
    </div>

    <!-- Rate Limiting -->
    <div class="subsection">
      <h4>Notification Limits</h4>

      <div class="setting-row">
        <label class="input-label">
          <span>Maximum notifications per hour</span>
          <input
            type="number"
            bind:value={settings.max_messages_per_hour}
            min="1"
            max="30"
            class="number-input"
          />
        </label>
        <span class="setting-hint">Prevents notification overload</span>
      </div>
    </div>

    <!-- Quiet Hours -->
    <div class="subsection">
      <h4>Quiet Hours</h4>

      <div class="setting-row">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={settings.quiet_hours_enabled} />
          <span>Enable quiet hours</span>
        </label>
        <span class="setting-hint">Suppress notifications during specific hours</span>
      </div>

      {#if settings.quiet_hours_enabled}
        <div class="indent">
          <div class="setting-row">
            <label class="input-label">
              <span>Start time</span>
              <input
                type="time"
                bind:value={settings.quiet_hours_start}
                class="time-input"
              />
            </label>
          </div>

          <div class="setting-row">
            <label class="input-label">
              <span>End time</span>
              <input
                type="time"
                bind:value={settings.quiet_hours_end}
                class="time-input"
              />
            </label>
          </div>
        </div>
      {/if}
    </div>

    <!-- Frontend Polling -->
    <div class="subsection">
      <h4>Advanced Settings</h4>

      <div class="setting-row">
        <label class="input-label">
          <span>Check for new notifications (minutes)</span>
          <input
            type="number"
            bind:value={settings.frontend_poll_interval_minutes}
            min="1"
            max="15"
            class="number-input"
          />
        </label>
        <span class="setting-hint">How often your browser checks for new notifications</span>
      </div>
    </div>

    <!-- Save Button -->
    <div class="actions">
      <button class="btn-info" on:click={saveSettings} disabled={saving}>
        {saving ? "Saving..." : "Save Settings"}
      </button>

      {#if saveMessage}
        <span class={saveMessage.includes("Error") ? "save-error" : "save-success"}>
          {saveMessage}
        </span>
      {/if}
    </div>
  {/if}
</div>

<style>
  .proactive-settings {
    max-width: 800px;
  }

  .loading-state {
    color: var(--text-secondary);
    font-style: italic;
  }

  .subsection {
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border-primary);
  }

  .subsection:last-of-type {
    border-bottom: none;
  }

  h4 {
    font-size: 1.125rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: var(--text-primary);
  }

  .setting-row {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .indent {
    margin-left: 1.5rem;
    margin-top: 0.75rem;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    cursor: pointer;
    font-weight: 500;
    color: var(--text-primary);
  }

  .checkbox-label input[type="checkbox"] {
    width: 1.25rem;
    height: 1.25rem;
    cursor: pointer;
  }

  .input-label {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .input-label > span {
    font-weight: 500;
    color: var(--text-primary);
  }

  .number-input,
  .time-input {
    padding: 0.5rem;
    border: 1px solid var(--border-primary);
    border-radius: 4px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 1rem;
    max-width: 200px;
  }

  .number-input:focus,
  .time-input:focus {
    outline: none;
    border-color: var(--info-500);
  }

  .setting-hint {
    font-size: 0.875rem;
    color: var(--text-tertiary);
    font-style: italic;
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-top: 2rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border-primary);
  }

  .save-success {
    color: var(--success-500);
    font-weight: 500;
  }

  .save-error {
    color: var(--danger-500);
    font-weight: 500;
  }
</style>
