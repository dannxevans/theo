<script>
  import { onMount } from "svelte";
  import { getAuditSessions, getSessionTurns, getAuditStats } from "../../lib/api";

  let isAdmin = false;
  let loading = false;
  let error = null;

  // View state
  let currentView = "sessions"; // "sessions" or "turns"
  let selectedSession = null;

  // Sessions data
  let sessions = [];
  let sessionsTotal = 0;
  let sessionsOffset = 0;
  let sessionsLimit = 20;
  let sessionsHasMore = false;

  // Turns data
  let turns = [];
  let turnsTotal = 0;
  let turnsOffset = 0;
  let turnsLimit = 50;
  let turnsHasMore = false;

  // UI state for expandable request context
  let expandedTurns = new Set();

  // Filters
  let modeFilter = "";
  let roleFilter = "";
  let providerFilter = "";

  // Statistics
  let stats = null;

  function checkAdminStatus() {
    const userStr = localStorage.getItem("user");
    if (userStr) {
      try {
        const user = JSON.parse(userStr);
        isAdmin = user.is_admin === true;
      } catch (e) {
        console.error("Failed to parse user data:", e);
        isAdmin = false;
      }
    }
  }

  async function loadSessions() {
    if (!isAdmin) return;

    loading = true;
    error = null;

    try {
      const filters = {
        limit: sessionsLimit,
        offset: sessionsOffset
      };

      if (modeFilter) {
        filters.mode = modeFilter;
      }

      const data = await getAuditSessions(filters);
      sessions = data.sessions;
      sessionsTotal = data.total;
      sessionsHasMore = data.has_more;
    } catch (e) {
      console.error("Failed to load sessions:", e);
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function loadSessionTurns(sessionId) {
    loading = true;
    error = null;

    try {
      const filters = {
        limit: turnsLimit,
        offset: turnsOffset
      };

      if (roleFilter) {
        filters.role = roleFilter;
      }

      if (providerFilter) {
        filters.provider_id = providerFilter;
      }

      const data = await getSessionTurns(sessionId, filters);
      selectedSession = data.session;
      turns = data.turns;
      turnsTotal = data.total;
      turnsHasMore = data.has_more;
      currentView = "turns";
    } catch (e) {
      console.error("Failed to load turns:", e);
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function loadStats() {
    if (!isAdmin) return;

    try {
      stats = await getAuditStats();
    } catch (e) {
      console.error("Failed to load stats:", e);
    }
  }

  function viewSessionTurns(session) {
    turnsOffset = 0;
    roleFilter = "";
    providerFilter = "";
    loadSessionTurns(session.id);
  }

  function backToSessions() {
    currentView = "sessions";
    selectedSession = null;
    turns = [];
    turnsOffset = 0;
  }

  function nextSessionsPage() {
    sessionsOffset += sessionsLimit;
    loadSessions();
  }

  function prevSessionsPage() {
    sessionsOffset = Math.max(0, sessionsOffset - sessionsLimit);
    loadSessions();
  }

  function nextTurnsPage() {
    turnsOffset += turnsLimit;
    loadSessionTurns(selectedSession.id);
  }

  function prevTurnsPage() {
    turnsOffset = Math.max(0, turnsOffset - turnsLimit);
    loadSessionTurns(selectedSession.id);
  }

  function formatDate(dateString) {
    if (!dateString) return "N/A";
    const date = new Date(dateString);
    return date.toLocaleString();
  }

  function applyModeFilter() {
    sessionsOffset = 0;
    loadSessions();
  }

  function applyTurnsFilter() {
    turnsOffset = 0;
    loadSessionTurns(selectedSession.id);
  }

  function toggleRequestContext(turnId) {
    if (expandedTurns.has(turnId)) {
      expandedTurns.delete(turnId);
    } else {
      expandedTurns.add(turnId);
    }
    expandedTurns = expandedTurns; // Trigger reactivity
  }

  onMount(() => {
    checkAdminStatus();
    if (isAdmin) {
      loadSessions();
      loadStats();
    }
  });
</script>

<div class="database-audit-settings">
  {#if !isAdmin}
    <div class="admin-required">
      <div class="warning-icon">⚠️</div>
      <h3>Admin Access Required</h3>
      <p>Database audit features are only available to administrators.</p>
    </div>
  {:else}
    <div class="audit-header">
      <div>
        <h2>Database Audit</h2>
        <p class="subtitle">View conversation turns and LLM responses stored in the database (read-only).</p>
      </div>
      {#if currentView === "turns"}
        <button class="btn-secondary" on:click={backToSessions}>
          ← Back to Sessions
        </button>
      {/if}
    </div>

    {#if error}
      <div class="error-message">{error}</div>
    {/if}

    <!-- Statistics Dashboard -->
    {#if stats && currentView === "sessions"}
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{stats.total_sessions}</div>
          <div class="stat-label">Total Sessions</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{stats.total_turns}</div>
          <div class="stat-label">Total Turns</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{Object.keys(stats.turns_by_provider || {}).length}</div>
          <div class="stat-label">Providers Used</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{Object.keys(stats.turns_by_model || {}).length}</div>
          <div class="stat-label">Models Used</div>
        </div>
      </div>
    {/if}

    <!-- Sessions View -->
    {#if currentView === "sessions"}
      <div class="data-section">
        <div class="section-header">
          <h3>Conversation Sessions</h3>
          <div class="filter-controls">
            <select bind:value={modeFilter} on:change={applyModeFilter}>
              <option value="">All Modes</option>
              <option value="work">Work</option>
              <option value="personal">Personal</option>
            </select>
          </div>
        </div>

        {#if loading}
          <div class="loading">Loading sessions...</div>
        {:else if sessions.length === 0}
          <div class="empty-state">No sessions found</div>
        {:else}
          <div class="sessions-table">
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Mode</th>
                  <th>Turns</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {#each sessions as session}
                  <tr>
                    <td class="session-title">{session.title || "Untitled"}</td>
                    <td><span class="badge badge-{session.mode}">{session.mode}</span></td>
                    <td>{session.turn_count}</td>
                    <td class="date-cell">{formatDate(session.created_at)}</td>
                    <td>
                      <button class="btn-link" on:click={() => viewSessionTurns(session)}>
                        View Turns →
                      </button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <div class="pagination">
            <div class="pagination-info">
              Showing {sessionsOffset + 1} to {Math.min(sessionsOffset + sessionsLimit, sessionsTotal)} of {sessionsTotal}
            </div>
            <div class="pagination-controls">
              <button
                class="btn-secondary"
                on:click={prevSessionsPage}
                disabled={sessionsOffset === 0}>
                Previous
              </button>
              <button
                class="btn-secondary"
                on:click={nextSessionsPage}
                disabled={!sessionsHasMore}>
                Next
              </button>
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Turns View -->
    {#if currentView === "turns" && selectedSession}
      <div class="data-section">
        <div class="section-header">
          <div>
            <h3>Conversation Turns</h3>
            <p class="session-info">
              Session: {selectedSession.title || "Untitled"} • Mode: {selectedSession.mode}
            </p>
          </div>
          <div class="filter-controls">
            <select bind:value={roleFilter} on:change={applyTurnsFilter}>
              <option value="">All Roles</option>
              <option value="user">User</option>
              <option value="assistant">Assistant</option>
            </select>
            <button class="btn-secondary" on:click={applyTurnsFilter}>Apply Filters</button>
          </div>
        </div>

        {#if loading}
          <div class="loading">Loading turns...</div>
        {:else if turns.length === 0}
          <div class="empty-state">No turns found</div>
        {:else}
          <div class="turns-list">
            {#each turns as turn}
              <div class="turn-card turn-{turn.role}">
                <div class="turn-header">
                  <span class="turn-role">{turn.role}</span>
                  <span class="turn-date">{formatDate(turn.created_at)}</span>
                </div>
                <div class="turn-content">{turn.content}</div>
                {#if turn.role === "assistant"}
                  <div class="turn-metadata">
                    {#if turn.provider_id}
                      <span class="metadata-item">
                        <strong>Provider:</strong> {turn.provider_id}
                      </span>
                    {/if}
                    {#if turn.model}
                      <span class="metadata-item">
                        <strong>Model:</strong> {turn.model}
                      </span>
                    {/if}
                    {#if turn.intent}
                      <span class="metadata-item">
                        <strong>Intent:</strong> {turn.intent}
                      </span>
                    {/if}
                    {#if turn.metadata && turn.metadata.tokens}
                      <span class="metadata-item">
                        <strong>Tokens:</strong> {turn.metadata.tokens}
                      </span>
                    {/if}
                  </div>

                  {#if turn.full_request_context}
                    <button class="btn-expand" on:click={() => toggleRequestContext(turn.id)}>
                      {expandedTurns.has(turn.id) ? '▼ Hide' : '▶ View'} Full LLM Request ({turn.full_request_context.length} messages)
                    </button>

                    {#if expandedTurns.has(turn.id)}
                      <div class="request-context">
                        <div class="context-header">Full Request Sent to LLM:</div>
                        <div class="context-messages">
                          {#each turn.full_request_context as message, idx}
                            <div class="context-message context-{message.role}">
                              <div class="context-message-header">
                                <span class="context-role">{message.role}</span>
                                <span class="context-index">Message {idx + 1}</span>
                              </div>
                              <pre class="context-content">{message.content}</pre>
                            </div>
                          {/each}
                        </div>
                      </div>
                    {/if}
                  {/if}
                {/if}
              </div>
            {/each}
          </div>

          <div class="pagination">
            <div class="pagination-info">
              Showing {turnsOffset + 1} to {Math.min(turnsOffset + turnsLimit, turnsTotal)} of {turnsTotal}
            </div>
            <div class="pagination-controls">
              <button
                class="btn-secondary"
                on:click={prevTurnsPage}
                disabled={turnsOffset === 0}>
                Previous
              </button>
              <button
                class="btn-secondary"
                on:click={nextTurnsPage}
                disabled={!turnsHasMore}>
                Next
              </button>
            </div>
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .database-audit-settings {
    padding: 24px;
    max-width: 1400px;
    margin: 0 auto;
  }

  .admin-required {
    text-align: center;
    padding: 60px 24px;
    background: var(--bg-secondary);
    border-radius: 8px;
    border: 2px dashed var(--border-color);
  }

  .warning-icon {
    font-size: 48px;
    margin-bottom: 16px;
  }

  .admin-required h3 {
    margin: 0 0 8px 0;
    color: var(--text-primary);
  }

  .admin-required p {
    margin: 0;
    color: var(--text-secondary);
  }

  .audit-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
  }

  .audit-header h2 {
    margin: 0 0 4px 0;
    color: var(--text-primary);
  }

  .subtitle {
    margin: 0;
    color: var(--text-secondary);
    font-size: 14px;
  }

  .error-message {
    padding: 12px 16px;
    background: var(--error-bg);
    color: var(--error-text);
    border-radius: 6px;
    margin-bottom: 16px;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }

  .stat-card {
    background: var(--bg-secondary);
    padding: 20px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    text-align: center;
  }

  .stat-value {
    font-size: 32px;
    font-weight: 600;
    color: var(--accent-color);
    margin-bottom: 4px;
  }

  .stat-label {
    font-size: 14px;
    color: var(--text-secondary);
  }

  .data-section {
    background: var(--bg-secondary);
    border-radius: 8px;
    padding: 24px;
    border: 1px solid var(--border-color);
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
  }

  .section-header h3 {
    margin: 0 0 4px 0;
    color: var(--text-primary);
  }

  .session-info {
    margin: 4px 0 0 0;
    color: var(--text-secondary);
    font-size: 14px;
  }

  .filter-controls {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .filter-controls select {
    padding: 6px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 14px;
  }

  .loading, .empty-state {
    text-align: center;
    padding: 40px;
    color: var(--text-secondary);
  }

  .sessions-table {
    overflow-x: auto;
    margin-bottom: 16px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead th {
    text-align: left;
    padding: 12px;
    background: var(--bg-primary);
    color: var(--text-secondary);
    font-weight: 600;
    font-size: 14px;
    border-bottom: 2px solid var(--border-color);
  }

  tbody td {
    padding: 12px;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-primary);
  }

  tbody tr:hover {
    background: var(--bg-primary);
  }

  .session-title {
    font-weight: 500;
  }

  .date-cell {
    color: var(--text-secondary);
    font-size: 14px;
  }

  .badge {
    display: inline-block;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
  }

  .badge-work {
    background: var(--info-bg);
    color: var(--info-text);
  }

  .badge-personal {
    background: var(--success-bg);
    color: var(--success-text);
  }

  .btn-link {
    background: none;
    border: none;
    color: var(--accent-color);
    cursor: pointer;
    font-size: 14px;
    padding: 0;
  }

  .btn-link:hover {
    text-decoration: underline;
  }

  .turns-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 16px;
  }

  .turn-card {
    padding: 16px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
  }

  .turn-user {
    background: var(--bg-primary);
  }

  .turn-assistant {
    background: var(--bg-tertiary);
  }

  .turn-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .turn-role {
    font-weight: 600;
    text-transform: capitalize;
    color: var(--accent-color);
  }

  .turn-date {
    font-size: 12px;
    color: var(--text-secondary);
  }

  .turn-content {
    color: var(--text-primary);
    line-height: 1.5;
    white-space: pre-wrap;
    word-wrap: break-word;
    margin-bottom: 8px;
  }

  .turn-metadata {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    padding-top: 8px;
    border-top: 1px solid var(--border-color);
    font-size: 12px;
  }

  .metadata-item {
    color: var(--text-secondary);
  }

  .metadata-item strong {
    color: var(--text-primary);
  }

  .pagination {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
  }

  .pagination-info {
    color: var(--text-secondary);
    font-size: 14px;
  }

  .pagination-controls {
    display: flex;
    gap: 8px;
  }

  .btn-secondary {
    padding: 8px 16px;
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 14px;
  }

  .btn-secondary:hover:not(:disabled) {
    background: var(--bg-tertiary);
  }

  .btn-secondary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-expand {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--accent-color);
    cursor: pointer;
    font-size: 13px;
    padding: 8px 12px;
    margin-top: 8px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .btn-expand:hover {
    background: var(--bg-tertiary);
  }

  .request-context {
    margin-top: 12px;
    padding: 16px;
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .context-header {
    font-weight: 600;
    font-size: 14px;
    color: var(--text-primary);
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color);
  }

  .context-messages {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .context-message {
    padding: 12px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
  }

  .context-message.context-system {
    background: var(--warning-bg);
    border-color: var(--warning-border);
  }

  .context-message.context-user {
    background: var(--bg-secondary);
  }

  .context-message.context-assistant {
    background: var(--bg-tertiary);
  }

  .context-message-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
    font-size: 12px;
  }

  .context-role {
    font-weight: 600;
    text-transform: capitalize;
    color: var(--accent-color);
  }

  .context-index {
    color: var(--text-secondary);
    font-size: 11px;
  }

  .context-content {
    margin: 0;
    padding: 8px;
    background: var(--bg-code);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 12px;
    line-height: 1.5;
    color: var(--text-primary);
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-x: auto;
  }
</style>
