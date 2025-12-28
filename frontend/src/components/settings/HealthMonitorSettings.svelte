<script>
  import { createEventDispatcher } from "svelte";
  import { setDebugFlag } from "../../lib/api";

  export let healthData = {
    ai_providers: [],
    m365_integration: { connected: false },
    service_providers: []
  };
  export let debugEnabled = false;
  export let advancedMode = false;

  const dispatch = createEventDispatcher();

  let healthLoading = false;
  let healthError = null;
  let testingM365 = false;
  let m365TestResult = null;
  let savingDebug = false;

  function formatRelativeTime(isoString) {
    if (!isoString) return 'Never';

    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSecs < 60) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    return date.toLocaleDateString();
  }

  async function testM365Connection() {
    testingM365 = true;
    m365TestResult = null;

    try {
      const token = localStorage.getItem("auth_token");
      const response = await fetch("/api/health/test-m365", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error("Failed to test M365 connection");
      }

      m365TestResult = await response.json();
    } catch (err) {
      console.error("Failed to test M365 connection:", err);
      m365TestResult = {
        healthy: false,
        error: err.message
      };
    } finally {
      testingM365 = false;
    }
  }

  async function toggleDebug(value) {
    savingDebug = true;
    await setDebugFlag(value);
    debugEnabled = value;
    savingDebug = false;
  }

  function toggleAdvancedMode(value) {
    advancedMode = value;
    localStorage.setItem("theo.advancedMode", value.toString());
    // Dispatch event so Chat component can listen
    window.dispatchEvent(new CustomEvent("advancedModeChanged", { detail: { enabled: value } }));
  }

  function handleRefresh() {
    dispatch("reload");
  }
</script>

<div class="health-monitor-settings">
  <div class="health-header">
    <div>
      <h2>System Health Monitor</h2>
      <p class="subtitle">Monitor AI provider health, performance metrics, and system status.</p>
    </div>
    <button class="btn-secondary" on:click={handleRefresh} disabled={healthLoading}>
      {healthLoading ? 'Refreshing...' : 'Refresh All'}
    </button>
  </div>

  {#if healthError}
    <div class="error-message">{healthError}</div>
  {/if}

  <!-- Section 1: AI Providers Health -->
  <div class="section">
    <h3>AI Provider Health</h3>
    <p class="hint">Real-time health monitoring for all configured AI providers</p>

    {#if healthData.ai_providers && healthData.ai_providers.length === 0}
      <p class="empty-state">No AI providers configured yet. Add providers in the Accounts section.</p>
    {:else if healthData.ai_providers}
      <div class="health-grid">
        {#each healthData.ai_providers as provider}
          <div class="health-card">
            <div class="health-card-header">
              <h4>{provider.name}</h4>
              <span class="health-badge"
                class:badge-healthy={provider.enabled && provider.health_status === 'healthy' && !provider.circuit_breaker_open}
                class:badge-degraded={provider.health_status === 'degraded'}
                class:badge-unhealthy={provider.health_status === 'unhealthy' || provider.circuit_breaker_open}
                class:badge-inactive={!provider.enabled}
                class:badge-unknown={provider.health_status === 'unknown' && provider.enabled}>
                {#if !provider.enabled}
                  ⏸️ Inactive
                {:else if provider.circuit_breaker_open}
                  🔌 Circuit Breaker
                {:else if provider.health_status === 'healthy'}
                  🟢 Healthy
                {:else if provider.health_status === 'degraded'}
                  🟡 Degraded
                {:else if provider.health_status === 'unhealthy'}
                  🔴 Unhealthy
                {:else}
                  ⚪ Unknown
                {/if}
              </span>
            </div>
            <div class="health-card-body">
              <p><strong>Type:</strong> {provider.type}</p>
              <p><strong>Model:</strong> {provider.model || 'N/A'}</p>

              {#if provider.total_requests > 0}
                <div class="metric-group">
                  <p><strong>Requests:</strong> {provider.total_requests} total, {provider.failed_requests} failed</p>
                  <div class="success-rate-bar">
                    <div class="success-rate-fill"
                      class:rate-good={provider.success_rate >= 95}
                      class:rate-warning={provider.success_rate >= 80 && provider.success_rate < 95}
                      class:rate-poor={provider.success_rate < 80}
                      style="width: {provider.success_rate}%"></div>
                  </div>
                  <p class="metric-small">Success Rate: {provider.success_rate}%</p>
                </div>

                <p><strong>Avg Latency:</strong>
                  <span class:latency-good={provider.avg_latency_ms < 500}
                    class:latency-warning={provider.avg_latency_ms >= 500 && provider.avg_latency_ms < 1000}
                    class:latency-poor={provider.avg_latency_ms >= 1000}>
                    {provider.avg_latency_ms}ms
                  </span>
                </p>

                {#if provider.last_success_at}
                  <p class="metric-small">Last Success: {formatRelativeTime(provider.last_success_at)}</p>
                {/if}
                {#if provider.last_failure_at}
                  <p class="metric-small error-text">Last Failure: {formatRelativeTime(provider.last_failure_at)}</p>
                {/if}
              {:else}
                <p class="metric-small">No requests yet</p>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Section 2: Microsoft 365 Integration -->
  <div class="section">
    <h3>Microsoft 365 Integration</h3>
    <p class="hint">Connection status and token health for Microsoft Graph API</p>

    <div class="health-card m365-card">
      <div class="health-card-header">
        <h4>Microsoft 365</h4>
        <span class="health-badge"
          class:badge-healthy={healthData.m365_integration?.connected && healthData.m365_integration?.token_valid && healthData.m365_integration?.hours_until_expiry > 24}
          class:badge-degraded={healthData.m365_integration?.connected && healthData.m365_integration?.hours_until_expiry <= 24 && healthData.m365_integration?.hours_until_expiry > 0}
          class:badge-unhealthy={!healthData.m365_integration?.connected || !healthData.m365_integration?.token_valid || healthData.m365_integration?.hours_until_expiry <= 0}
          class:badge-unknown={!healthData.m365_integration?.connected}>
          {#if !healthData.m365_integration?.connected}
            ⚪ Not Configured
          {:else if !healthData.m365_integration.token_valid || healthData.m365_integration.hours_until_expiry <= 0}
            🔴 Disconnected
          {:else if healthData.m365_integration.hours_until_expiry <= 24}
            🟡 Token Expiring Soon
          {:else}
            🟢 Connected
          {/if}
        </span>
      </div>

      {#if healthData.m365_integration?.connected}
        <div class="health-card-body">
          <p><strong>Account:</strong> {healthData.m365_integration.account || 'Unknown'}</p>
          <p><strong>Token Status:</strong>
            <span class:error-text={!healthData.m365_integration.token_valid}>
              {healthData.m365_integration.token_valid ? 'Valid' : 'Invalid/Expired'}
            </span>
          </p>

          {#if healthData.m365_integration.hours_until_expiry !== null}
            <p><strong>Token Expires:</strong>
              <span class:warning-text={healthData.m365_integration.hours_until_expiry <= 24}
                class:error-text={healthData.m365_integration.hours_until_expiry <= 0}>
                {#if healthData.m365_integration.hours_until_expiry > 0}
                  in {healthData.m365_integration.hours_until_expiry} hours
                {:else}
                  Expired
                {/if}
              </span>
            </p>
          {/if}

          {#if healthData.m365_integration.last_refreshed_at}
            <p class="metric-small">Last Refreshed: {formatRelativeTime(healthData.m365_integration.last_refreshed_at)}</p>
          {/if}

          {#if healthData.m365_integration.last_error}
            <p class="error-text metric-small">Last Error: {healthData.m365_integration.last_error}</p>
          {/if}

          {#if healthData.m365_integration.scopes && healthData.m365_integration.scopes.length > 0}
            <div class="capabilities">
              <p><strong>Capabilities:</strong></p>
              <ul class="capability-list">
                {#each healthData.m365_integration.scopes as scope}
                  <li>
                    {#if scope.includes('Calendar')}
                      ✓ Calendar Access
                    {:else if scope.includes('Mail')}
                      ✓ Email Access
                    {:else}
                      ✓ {scope}
                    {/if}
                  </li>
                {/each}
              </ul>
            </div>
          {/if}

          <button class="btn-small" on:click={testM365Connection} disabled={testingM365}>
            {testingM365 ? 'Testing...' : 'Test Connection'}
          </button>

          {#if m365TestResult}
            <div class="test-result" class:test-success={m365TestResult.healthy} class:test-error={!m365TestResult.healthy}>
              {#if m365TestResult.healthy}
                ✓ Connected to Microsoft Graph API ({m365TestResult.response_time_ms}ms)
              {:else}
                ✗ Connection Failed: {m365TestResult.error}
              {/if}
            </div>
          {/if}
        </div>
      {:else}
        <div class="health-card-body">
          <p class="empty-state">Microsoft 365 account not connected. Connect in the Integrations section.</p>
        </div>
      {/if}
    </div>
  </div>

  <!-- Section 3: Service Providers -->
  <div class="section">
    <h3>Service Providers</h3>
    <p class="hint">External service providers for bookings and appointments</p>

    {#if healthData.service_providers && healthData.service_providers.length === 0}
      <p class="empty-state">No service providers configured yet. Add providers in the Service Providers section.</p>
    {:else if healthData.service_providers}
      <div class="health-grid">
        {#each healthData.service_providers as provider}
          <div class="health-card">
            <div class="health-card-header">
              <h4>{provider.name}</h4>
              <span class="health-badge"
                class:badge-healthy={provider.is_enabled}
                class:badge-inactive={!provider.is_enabled}>
                {provider.is_enabled ? '🟢 Active' : '⏸️ Disabled'}
              </span>
            </div>
            <div class="health-card-body">
              <p><strong>Category:</strong> {provider.category}</p>
              <p><strong>Type:</strong> {provider.provider_type === 'manual' ? 'Manual Booking' : 'API Integration'}</p>

              {#if provider.last_synced_at}
                <p class="metric-small">Last Synced: {formatRelativeTime(provider.last_synced_at)}</p>
              {/if}

              {#if provider.booking_url}
                <p><a href={provider.booking_url} target="_blank" class="booking-link">Open Booking URL →</a></p>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Debug Settings -->
  <div class="section">
    <h3>Debug Settings</h3>
    <div class="rule">
      <label>Debug logs</label>
      <input
        type="checkbox"
        checked={debugEnabled}
        disabled={savingDebug}
        on:change={(e) => toggleDebug(e.target.checked)}
      />
      <small style="display: block; margin-top: 0.5rem; color: #6b7280;">
        Enable detailed logging for troubleshooting
      </small>
    </div>

    <div class="rule">
      <label>Advanced mode</label>
      <input
        type="checkbox"
        checked={advancedMode}
        on:change={(e) => toggleAdvancedMode(e.target.checked)}
      />
      <small style="display: block; margin-top: 0.5rem; color: #6b7280;">
        Shows Export and Fork features in chat interface
      </small>
    </div>
  </div>
</div>

<style>
  .health-monitor-settings {
    width: 100%;
  }

  h2 {
    margin-top: 0;
    margin-bottom: var(--space-2);
  }

  .subtitle {
    color: var(--gray-600);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .health-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-6);
  }

  .section {
    margin-bottom: var(--space-6);
    padding-bottom: var(--space-6);
    border-bottom: 1px solid var(--gray-200);
  }

  .section:last-child {
    border-bottom: none;
  }

  h3 {
    margin-bottom: var(--space-2);
  }

  .hint {
    font-size: var(--font-size-sm);
    color: var(--gray-500);
    margin-bottom: var(--space-4);
  }

  .error-message {
    padding: var(--space-3);
    background: #FEE2E2;
    border: 1px solid #F87171;
    border-radius: 4px;
    color: #991B1B;
    margin-bottom: var(--space-4);
  }

  .health-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: var(--space-4);
    margin-top: var(--space-4);
  }

  .health-card {
    border: 1px solid var(--gray-200);
    border-radius: 8px;
    padding: var(--space-4);
    background: white;
    transition: box-shadow 0.2s;
  }

  .health-card:hover {
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  }

  .health-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-3);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--gray-100);
  }

  .health-card-header h4 {
    margin: 0;
    font-size: var(--font-size-lg);
    color: var(--gray-800);
  }

  .health-badge {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: var(--font-size-sm);
    font-weight: 500;
  }

  .health-badge.badge-healthy {
    background: #DCFCE7;
    color: #166534;
  }

  .health-badge.badge-degraded {
    background: #FEF3C7;
    color: #92400E;
  }

  .health-badge.badge-unhealthy {
    background: #FEE2E2;
    color: #991B1B;
  }

  .health-badge.badge-inactive {
    background: var(--gray-100);
    color: var(--gray-600);
  }

  .health-badge.badge-unknown {
    background: var(--gray-100);
    color: var(--gray-500);
  }

  .health-card-body p {
    margin: var(--space-2) 0;
    font-size: var(--font-size-sm);
    color: var(--gray-700);
  }

  .metric-group {
    margin: var(--space-3) 0;
  }

  .success-rate-bar {
    height: 8px;
    background: var(--gray-200);
    border-radius: 4px;
    overflow: hidden;
    margin: var(--space-2) 0;
  }

  .success-rate-fill {
    height: 100%;
    transition: width 0.3s ease;
  }

  .success-rate-fill.rate-good {
    background: #10B981;
  }

  .success-rate-fill.rate-warning {
    background: #F59E0B;
  }

  .success-rate-fill.rate-poor {
    background: #EF4444;
  }

  .metric-small {
    font-size: var(--font-size-xs);
    color: var(--gray-600);
    margin: var(--space-1) 0;
  }

  .latency-good {
    color: #10B981;
    font-weight: 500;
  }

  .latency-warning {
    color: #F59E0B;
    font-weight: 500;
  }

  .latency-poor {
    color: #EF4444;
    font-weight: 500;
  }

  .error-text {
    color: #EF4444;
  }

  .warning-text {
    color: #F59E0B;
  }

  .empty-state {
    text-align: center;
    padding: var(--space-8);
    color: var(--gray-500);
    font-style: italic;
  }

  .m365-card {
    max-width: 100%;
  }

  .capabilities {
    margin-top: var(--space-3);
  }

  .capability-list {
    margin: var(--space-2) 0;
    padding-left: var(--space-5);
    list-style: none;
  }

  .capability-list li {
    margin: var(--space-1) 0;
    font-size: var(--font-size-sm);
    color: var(--gray-700);
  }

  .btn-small {
    padding: 6px 12px;
    font-size: var(--font-size-sm);
    border: 1px solid var(--gray-300);
    background: white;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
    margin-top: var(--space-3);
  }

  .btn-small:hover:not(:disabled) {
    background: var(--gray-50);
    border-color: var(--gray-400);
  }

  .btn-small:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .test-result {
    margin-top: var(--space-3);
    padding: var(--space-2) var(--space-3);
    border-radius: 4px;
    font-size: var(--font-size-sm);
  }

  .test-success {
    background: #DCFCE7;
    color: #166534;
    border: 1px solid #86EFAC;
  }

  .test-error {
    background: #FEE2E2;
    color: #991B1B;
    border: 1px solid #FCA5A5;
  }

  .booking-link {
    color: var(--info-600);
    text-decoration: none;
    font-size: var(--font-size-sm);
  }

  .booking-link:hover {
    text-decoration: underline;
  }

  .rule {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  .rule label {
    width: 140px;
    font-weight: 500;
  }

  input[type="checkbox"] {
    transform: scale(1.2);
    cursor: pointer;
  }
</style>
