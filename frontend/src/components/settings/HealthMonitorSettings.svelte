<script>
  import { createEventDispatcher, onMount } from "svelte";
  import { setDebugFlag, setMessageDebugFlag, getProviderCosts, getVoiceCosts, resetProviderUsage } from "../../lib/api";

  export let healthData = {
    ai_providers: [],
    m365_integration: { connected: false },
    whoop_integration: { connected: false },
    plex_integration: { connected: false },
    service_providers: [],
    feature_providers: []
  };
  export let debugEnabled = false;
  export let messageDebugEnabled = false;
  export let advancedMode = false;

  const dispatch = createEventDispatcher();

  let healthLoading = false;
  let healthError = null;
  let testingM365 = false;
  let m365TestResult = null;
  let savingDebug = false;
  let savingMessageDebug = false;

  // Cost tracking state
  let costData = null;
  let voiceCostData = null;
  let selectedPeriod = 30;
  let costLoading = false;
  let resettingUsage = false;

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

  async function toggleMessageDebug(value) {
    savingMessageDebug = true;
    await setMessageDebugFlag(value);
    messageDebugEnabled = value;
    savingMessageDebug = false;
  }

  function toggleAdvancedMode(value) {
    advancedMode = value;
    localStorage.setItem("theo.advancedMode", value.toString());
    // Dispatch event so Chat component can listen
    window.dispatchEvent(new CustomEvent("advancedModeChanged", { detail: { enabled: value } }));
  }

  function handleRefresh() {
    dispatch("reload");
    loadCostData();
  }

  async function loadCostData() {
    costLoading = true;
    try {
      const period = selectedPeriod === "all" ? null : selectedPeriod;
      [costData, voiceCostData] = await Promise.all([
        getProviderCosts(period),
        getVoiceCosts(period)
      ]);
    } catch (e) {
      console.error("Failed to load cost data:", e);
      costData = null;
      voiceCostData = null;
    } finally {
      costLoading = false;
    }
  }

  async function changePeriod(days) {
    selectedPeriod = days;
    await loadCostData();
  }

  async function handleResetUsage() {
    const confirmed = confirm(
      "⚠️ WARNING: This will permanently delete ALL provider usage data including:\n\n" +
      "• All request logs\n" +
      "• All voice usage logs\n" +
      "• All cost tracking history\n" +
      "• All health metrics\n\n" +
      "Provider configurations will be preserved.\n\n" +
      "This action cannot be undone. Continue?"
    );

    if (!confirmed) return;

    resettingUsage = true;
    try {
      await resetProviderUsage();
      // Reload health data and costs after reset
      dispatch("reload");
      await loadCostData();
      alert("✓ Provider usage data has been reset successfully");
    } catch (e) {
      console.error("Failed to reset provider usage:", e);
      alert("Failed to reset provider usage: " + e.message);
    } finally {
      resettingUsage = false;
    }
  }

  function getProviderCost(providerId) {
    if (!costData || !costData.providers) return null;
    return costData.providers.find(p => p.provider_id === providerId);
  }

  function getTotalCostUSD() {
    const providerCost = costData?.total_cost_usd || 0;
    const voiceCost = voiceCostData?.total_cost_usd || 0;
    return providerCost + voiceCost;
  }

  onMount(() => {
    loadCostData();
  });
</script>

<div class="health-monitor-settings">
  <div class="health-header">
    <div>
      <h2>System Health Monitor</h2>
      <p class="subtitle">Monitor AI provider health, performance metrics, and system status.</p>
    </div>
    <div class="header-actions">
      <button class="btn-secondary" on:click={handleRefresh} disabled={healthLoading}>
        {healthLoading ? 'Refreshing...' : 'Refresh All'}
      </button>
      <button class="btn-danger" on:click={handleResetUsage} disabled={resettingUsage}>
        {resettingUsage ? 'Resetting...' : 'Reset Provider Usage'}
      </button>
    </div>
  </div>

  {#if healthError}
    <div class="error-message">{healthError}</div>
  {/if}

  <!-- Cost Summary Banner -->
  {#if !costLoading && costData}
    <div class="cost-banner">
      <div class="cost-banner-header">
        <h3>💰 Cost Summary</h3>
        <div class="period-selector">
          <button
            class="period-btn"
            class:active={selectedPeriod === 7}
            on:click={() => changePeriod(7)}>
            7 Days
          </button>
          <button
            class="period-btn"
            class:active={selectedPeriod === 30}
            on:click={() => changePeriod(30)}>
            30 Days
          </button>
          <button
            class="period-btn"
            class:active={selectedPeriod === 90}
            on:click={() => changePeriod(90)}>
            90 Days
          </button>
          <button
            class="period-btn"
            class:active={selectedPeriod === null}
            on:click={() => changePeriod(null)}>
            All Time
          </button>
        </div>
      </div>
      <div class="cost-banner-body">
        <div class="cost-main">
          <div class="cost-total">
            <span class="cost-label">Total Cost</span>
            <span class="cost-amount">${getTotalCostUSD().toFixed(6)}</span>
          </div>
          <div class="cost-stats">
            <div class="cost-stat">
              <span class="stat-label">AI Providers</span>
              <span class="stat-value">{costData.providers.length}</span>
              <span class="stat-sublabel">${costData.total_cost_usd.toFixed(4)}</span>
            </div>
            <div class="cost-stat">
              <span class="stat-label">Voice Services</span>
              <span class="stat-value">{voiceCostData?.services?.length || 0}</span>
              <span class="stat-sublabel">${(voiceCostData?.total_cost_usd || 0).toFixed(4)}</span>
            </div>
            <div class="cost-stat">
              <span class="stat-label">Total Requests</span>
              <span class="stat-value">
                {costData.providers.reduce((sum, p) => sum + p.request_count, 0) + (voiceCostData?.total_requests || 0)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  {/if}

  <!-- Section 1: AI Providers Health -->
  <div class="section">
    <h3>AI Provider Health</h3>
    <p class="hint">Real-time health monitoring and usage for all configured AI providers</p>

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
                  Healthy
                {:else if provider.health_status === 'degraded'}
                  Degraded
                {:else if provider.health_status === 'unhealthy'}
                  Unhealthy
                {:else}
                  Unknown
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

                {#if costData && !costLoading}
                  {@const providerCost = getProviderCost(provider.id)}
                  {#if providerCost}
                    <div class="cost-info">
                      <p><strong>Cost ({selectedPeriod ? selectedPeriod + 'd' : 'All Time'}):</strong>
                        <span class="cost-value">${providerCost.total_cost_usd.toFixed(6)}</span>
                      </p>
                      <p class="metric-small">
                        {providerCost.input_tokens_total.toLocaleString()} input + {providerCost.output_tokens_total.toLocaleString()} output tokens
                      </p>
                    </div>
                  {/if}
                {/if}

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

  <!-- Section 2: Voice Services -->
  {#if voiceCostData && voiceCostData.services && voiceCostData.services.length > 0}
    <div class="section">
      <h3>Voice Services</h3>
      <p class="hint">Text-to-Speech and Speech-to-Text usage and costs</p>

      <div class="health-grid">
        {#each voiceCostData.services as service}
          <div class="health-card">
            <div class="health-card-header">
              <h4>{service.name}</h4>
              <span class="health-badge badge-healthy">
                Active
              </span>
            </div>
            <div class="health-card-body">
              <p><strong>Service Type:</strong> {service.service_type.toUpperCase()}</p>

              <div class="metric-group">
                <p><strong>Usage ({selectedPeriod ? selectedPeriod + 'd' : 'All Time'}):</strong></p>
                {#if service.service_type === 'tts'}
                  <p class="metric-small">{service.total_characters.toLocaleString()} characters synthesized</p>
                {:else if service.service_type === 'stt'}
                  <p class="metric-small">{Math.round(service.total_audio_seconds / 60)} minutes transcribed</p>
                {/if}
                <p class="metric-small">{service.request_count} requests</p>
              </div>

              <div class="cost-info">
                <p><strong>Cost ({selectedPeriod ? selectedPeriod + 'd' : 'All Time'}):</strong>
                  <span class="cost-value">${service.total_cost_usd.toFixed(6)}</span>
                </p>
              </div>
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Section 3: Integrations -->
  <div class="section">
    <h3>Integrations</h3>
    <p class="hint">External service integrations for calendar, email, fitness tracking, and media</p>

    <div class="health-grid">
      <!-- Microsoft 365 Card -->
      <div class="health-card m365-card">
      <div class="health-card-header">
        <h4>Microsoft 365</h4>
        <span class="health-badge"
          class:badge-healthy={healthData.m365_integration?.connected && healthData.m365_integration?.token_valid && healthData.m365_integration?.hours_until_expiry > 0.25}
          class:badge-degraded={healthData.m365_integration?.connected && healthData.m365_integration?.hours_until_expiry <= 0.25 && healthData.m365_integration?.hours_until_expiry > 0}
          class:badge-unhealthy={!healthData.m365_integration?.connected || !healthData.m365_integration?.token_valid || healthData.m365_integration?.hours_until_expiry <= 0}
          class:badge-unknown={!healthData.m365_integration?.connected}>
          {#if !healthData.m365_integration?.connected}
            Not Configured
          {:else if !healthData.m365_integration.token_valid || healthData.m365_integration.hours_until_expiry <= 0}
            Disconnected
          {:else if healthData.m365_integration.hours_until_expiry <= 0.25}
            Token Expiring Soon
          {:else}
            Connected
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
              <span class:warning-text={healthData.m365_integration.hours_until_expiry <= 0.25}
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

          <div class="capabilities">
            <p><strong>Capabilities:</strong></p>
            <ul class="capability-list">
              <li>✓ Email Read and Send</li>
              <li>✓ Calendar and Planning</li>
              <li>✓ Tasks Management</li>
            </ul>
          </div>

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

    <!-- WHOOP Card -->
    <div class="health-card">
      <div class="health-card-header">
        <h4>WHOOP</h4>
        <span class="health-badge"
          class:badge-healthy={healthData.whoop_integration?.connected && healthData.whoop_integration?.token_valid && healthData.whoop_integration?.hours_until_expiry > 0.25}
          class:badge-degraded={healthData.whoop_integration?.connected && healthData.whoop_integration?.hours_until_expiry <= 0.25 && healthData.whoop_integration?.hours_until_expiry > 0}
          class:badge-unhealthy={!healthData.whoop_integration?.connected || !healthData.whoop_integration?.token_valid || healthData.whoop_integration?.hours_until_expiry <= 0}
          class:badge-unknown={!healthData.whoop_integration?.connected}>
          {#if !healthData.whoop_integration?.connected}
            Not Configured
          {:else if !healthData.whoop_integration.token_valid || healthData.whoop_integration.hours_until_expiry <= 0}
            Disconnected
          {:else if healthData.whoop_integration.hours_until_expiry <= 0.25}
            Token Expiring Soon
          {:else}
            Connected
          {/if}
        </span>
      </div>

      {#if healthData.whoop_integration?.connected}
        <div class="health-card-body">
          <p><strong>WHOOP User ID:</strong> {healthData.whoop_integration.whoop_user_id || 'Unknown'}</p>
          <p><strong>Token Status:</strong>
            <span class:error-text={!healthData.whoop_integration.token_valid}>
              {healthData.whoop_integration.token_valid ? 'Valid' : 'Invalid/Expired'}
            </span>
          </p>

          {#if healthData.whoop_integration.hours_until_expiry !== null}
            <p><strong>Token Expires:</strong>
              <span class:warning-text={healthData.whoop_integration.hours_until_expiry <= 0.25}
                class:error-text={healthData.whoop_integration.hours_until_expiry <= 0}>
                {#if healthData.whoop_integration.hours_until_expiry > 0}
                  in {healthData.whoop_integration.hours_until_expiry} hours
                {:else}
                  Expired
                {/if}
              </span>
            </p>
          {/if}

          {#if healthData.whoop_integration.last_refreshed_at}
            <p class="metric-small">Last Refreshed: {formatRelativeTime(healthData.whoop_integration.last_refreshed_at)}</p>
          {/if}

          {#if healthData.whoop_integration.last_error}
            <p class="error-text metric-small">Last Error: {healthData.whoop_integration.last_error}</p>
          {/if}

          <div class="capabilities">
            <p><strong>Capabilities:</strong></p>
            <ul class="capability-list">
              <li>✓ Sleep Data Access</li>
              <li>✓ Recovery Metrics</li>
              <li>✓ Workout Data</li>
            </ul>
          </div>
        </div>
      {:else}
        <div class="health-card-body">
          <p class="empty-state">WHOOP account not connected. Connect in the Integrations section.</p>
        </div>
      {/if}
    </div>

    <!-- Plex Card -->
    <div class="health-card">
      <div class="health-card-header">
        <h4>Plex Media Server</h4>
        <span class="health-badge"
          class:badge-healthy={healthData.plex_integration?.connected && healthData.plex_integration?.token_valid}
          class:badge-unhealthy={healthData.plex_integration?.connected && !healthData.plex_integration?.token_valid}
          class:badge-unknown={!healthData.plex_integration?.connected}>
          {#if !healthData.plex_integration?.connected}
            Not Configured
          {:else if !healthData.plex_integration.token_valid}
            Disconnected
          {:else}
            Connected
          {/if}
        </span>
      </div>

      {#if healthData.plex_integration?.connected}
        <div class="health-card-body">
          <p><strong>Server:</strong> {healthData.plex_integration.server_name || 'Unknown'}</p>
          <p><strong>Username:</strong> {healthData.plex_integration.plex_username || 'Unknown'}</p>
          <p><strong>Token Status:</strong>
            <span class:error-text={!healthData.plex_integration.token_valid}>
              {healthData.plex_integration.token_valid ? 'Valid' : 'Invalid/Expired'}
            </span>
          </p>

          {#if healthData.plex_integration.server_url}
            <p class="metric-small">Server URL: {healthData.plex_integration.server_url}</p>
          {/if}

          {#if healthData.plex_integration.updated_at}
            <p class="metric-small">Last Updated: {formatRelativeTime(healthData.plex_integration.updated_at)}</p>
          {/if}

          {#if healthData.plex_integration.last_error}
            <p class="error-text metric-small">Last Error: {healthData.plex_integration.last_error}</p>
          {/if}

          <div class="capabilities">
            <p><strong>Capabilities:</strong></p>
            <ul class="capability-list">
              <li>✓ Recently Watched</li>
              <li>✓ On Deck Recommendations</li>
              <li>✓ Currently Playing Sessions</li>
              <li>✓ Routines Integration</li>
            </ul>
          </div>
        </div>
      {:else}
        <div class="health-card-body">
          <p class="empty-state">Plex account not connected. Connect in the Integrations section.</p>
        </div>
      {/if}
    </div>
  </div>
  </div>

  <!-- Section 4: Service Providers -->
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
                {provider.is_enabled ? 'Active' : '⏸Disabled'}
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

  <!-- Section 5: Feature Providers -->
  <div class="section">
    <h3>Feature Providers</h3>
    <p class="hint">External API integrations for weather, routing, and other features</p>

    {#if healthData.feature_providers && healthData.feature_providers.length === 0}
      <p class="empty-state">No feature providers configured yet. Add providers in the Feature Providers section.</p>
    {:else if healthData.feature_providers}
      <div class="health-grid">
        {#each healthData.feature_providers as provider}
          <div class="health-card">
            <div class="health-card-header">
              <h4>{provider.provider_name}</h4>
              <span class="health-badge"
                class:badge-healthy={provider.health_status === 'healthy'}
                class:badge-degraded={provider.health_status === 'warning'}
                class:badge-unhealthy={provider.health_status === 'error'}
                class:badge-inactive={!provider.is_enabled}>
                {#if provider.health_status === 'healthy'}
                  Healthy
                {:else if provider.health_status === 'warning'}
                  Warning
                {:else if provider.health_status === 'error'}
                  Error
                {:else if !provider.is_enabled}
                  ⏸ Disabled
                {:else}
                  Unknown
                {/if}
              </span>
            </div>
            <div class="health-card-body">
              <p><strong>Type:</strong> {provider.provider_type}</p>

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

  <!-- Debug Settings -->
  <div class="section">
    <h3>Advanced</h3>
    <div class="rule">
      <label for="debug-logs">Debug logs</label>
      <input
        id="debug-logs"
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
      <label for="message-debug">Message debug</label>
      <input
        id="message-debug"
        type="checkbox"
        checked={messageDebugEnabled}
        disabled={savingMessageDebug}
        on:change={(e) => toggleMessageDebug(e.target.checked)}
      />
      <small style="display: block; margin-top: 0.5rem; color: #6b7280;">
        Display full LLM instructions in chat
      </small>
    </div>

    <div class="rule">
      <label for="advanced-mode">Advanced mode</label>
      <input
        id="advanced-mode"
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
    color: var(--text-secondary);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-4);
  }

  .health-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: var(--space-6);
  }

  .header-actions {
    display: flex;
    gap: var(--space-3);
  }

  .btn-danger {
    padding: 8px 16px;
    font-size: var(--font-size-sm);
    font-weight: 500;
    border: 1px solid #DC2626;
    background: #DC2626;
    color: white;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-danger:hover:not(:disabled) {
    background: #B91C1C;
    border-color: #B91C1C;
    box-shadow: 0 2px 4px rgba(220, 38, 38, 0.2);
  }

  .btn-danger:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .section {
    margin-bottom: var(--space-6);
    padding: var(--space-5);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
  }

  .section:last-child {
    margin-bottom: 0;
  }

  h3 {
    margin-bottom: var(--space-2);
    color: var(--text-primary);
  }

  .hint {
    font-size: var(--font-size-sm);
    color: var(--text-tertiary);
    margin-bottom: var(--space-4);
  }

  .error-message {
    padding: var(--space-3);
    background: var(--error-50);
    border: 1px solid var(--error-500);
    border-radius: 4px;
    color: var(--error-700);
    margin-bottom: var(--space-4);
  }

  .health-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: var(--space-4);
    margin-top: var(--space-4);
  }

  .health-card {
    border: 1px solid var(--border-primary);
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
    border-bottom: 1px solid var(--border-secondary);
  }

  .health-card-header h4 {
    margin: 0;
    font-size: var(--font-size-lg);
    color: var(--text-primary);
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
    background: var(--bg-secondary);
    color: var(--text-secondary);
  }

  .health-badge.badge-unknown {
    background: var(--bg-secondary);
    color: var(--text-tertiary);
  }

  .health-card-body p {
    margin: var(--space-2) 0;
    font-size: var(--font-size-sm);
    color: var(--text-secondary);
  }

  .metric-group {
    margin: var(--space-3) 0;
  }

  .success-rate-bar {
    height: 8px;
    background: var(--bg-secondary);
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
    color: var(--text-secondary);
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
    color: var(--text-tertiary);
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
    color: var(--text-secondary);
  }

  .btn-small {
    padding: 6px 12px;
    font-size: var(--font-size-sm);
    border: 1px solid var(--border-primary);
    background: var(--bg-primary);
    color: var(--text-primary);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
    margin-top: var(--space-3);
  }

  .btn-small:hover:not(:disabled) {
    background: var(--bg-hover);
    border-color: var(--border-secondary);
  }

  .btn-small:focus {
    outline: none;
    border-color: var(--border-focus);
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

  /* Cost Banner Styles */
  .cost-banner {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin-bottom: var(--space-6);
    color: white;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  }

  .cost-banner-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-4);
  }

  .cost-banner-header h3 {
    margin: 0;
    color: white;
    font-size: var(--font-size-xl);
  }

  .period-selector {
    display: flex;
    gap: var(--space-2);
  }

  .period-btn {
    padding: 6px 12px;
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 6px;
    color: white;
    font-size: var(--font-size-sm);
    cursor: pointer;
    transition: all 0.2s;
  }

  .period-btn:hover {
    background: rgba(255, 255, 255, 0.3);
  }

  .period-btn.active {
    background: white;
    color: #667eea;
    font-weight: 600;
  }

  .cost-banner-body {
    display: flex;
    gap: var(--space-6);
  }

  .cost-main {
    flex: 1;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .cost-total {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .cost-label {
    font-size: var(--font-size-sm);
    opacity: 0.9;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .cost-amount {
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 1;
  }

  .cost-stats {
    display: flex;
    gap: var(--space-5);
  }

  .cost-stat {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .stat-label {
    font-size: var(--font-size-sm);
    opacity: 0.8;
  }

  .stat-value {
    font-size: var(--font-size-xl);
    font-weight: 600;
  }

  .stat-sublabel {
    font-size: var(--font-size-xs);
    opacity: 0.7;
    font-weight: normal;
  }

  /* Cost Info in Provider Cards */
  .cost-info {
    margin-top: var(--space-3);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border-secondary);
  }

  .cost-value {
    color: #667eea;
    font-weight: 600;
  }
</style>
