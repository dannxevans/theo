<script>
  import { onMount, onDestroy } from 'svelte';
  import { fetchDebugLogs, streamDebugLogs, toggleDebugMode, clearDebugLogs } from '../../lib/api.js';

  let logs = [];
  let eventSource = null;
  let isPaused = false;
  let debugEnabled = false;
  let isLoading = false;
  let error = null;
  let consoleContainer;
  let isUserScrolling = false;

  // Filter state
  let selectedLevels = { DEBUG: true, INFO: true, WARNING: true, ERROR: true };
  let selectedSource = 'all'; // 'all', 'backend', 'frontend'
  let searchTerm = '';
  let selectedComponent = 'all';

  // Component tags (extracted from logs)
  let availableComponents = new Set();

  // Stats
  let totalLogs = 0;
  let connectionStatus = 'disconnected'; // 'disconnected', 'connecting', 'connected', 'error'

  onMount(async () => {
    await checkDebugStatus();
    if (debugEnabled) {
      await loadHistoricalLogs();
      await startLogStream();
    }
  });

  onDestroy(() => {
    stopLogStream();
  });

  async function checkDebugStatus() {
    try {
      // Use full API URL to handle different environments
      const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:1066';
      const response = await fetch(`${API_BASE}/api/debug/status`);
      const data = await response.json();
      debugEnabled = data.enabled;
      totalLogs = data.log_count;
    } catch (e) {
      error = `Failed to check debug status: ${e.message}`;
      console.error('Debug status check error:', e);
    }
  }

  async function loadHistoricalLogs() {
    try {
      isLoading = true;
      error = null;
      const data = await fetchDebugLogs({ limit: 100 });
      logs = data.logs.reverse(); // Reverse to show oldest first
      totalLogs = data.total;

      // Extract unique components
      logs.forEach(log => {
        if (log.component) {
          availableComponents.add(log.component);
        }
      });
      availableComponents = availableComponents; // Trigger reactivity

      scrollToBottom();
    } catch (e) {
      error = `Failed to load logs: ${e.message}`;
    } finally {
      isLoading = false;
    }
  }

  async function startLogStream() {
    if (eventSource) {
      stopLogStream();
    }

    try {
      connectionStatus = 'connecting';
      eventSource = await streamDebugLogs((event) => {
        connectionStatus = 'connected';
        const log = event.data;

        // Add to available components
        if (log.component && !availableComponents.has(log.component)) {
          availableComponents.add(log.component);
          availableComponents = availableComponents; // Trigger reactivity
        }

        // Add log to list
        logs = [...logs, log];
        totalLogs++;

        // Auto-scroll if not paused
        if (!isPaused) {
          scrollToBottom();
        }
      });

      eventSource.onerror = () => {
        connectionStatus = 'error';
      };
    } catch (e) {
      error = `Failed to connect to log stream: ${e.message}`;
      connectionStatus = 'error';
    }
  }

  function stopLogStream() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
      connectionStatus = 'disconnected';
    }
  }

  function isScrolledToBottom() {
    if (!consoleContainer) return true;
    const threshold = 50; // pixels from bottom to be considered "at bottom"
    const scrollBottom = consoleContainer.scrollHeight - consoleContainer.scrollTop - consoleContainer.clientHeight;
    return scrollBottom < threshold;
  }

  function handleScroll() {
    // Check if user is scrolled to bottom
    isUserScrolling = !isScrolledToBottom();
  }

  function scrollToBottom() {
    setTimeout(() => {
      if (consoleContainer && !isPaused && !isUserScrolling) {
        consoleContainer.scrollTop = consoleContainer.scrollHeight;
      }
    }, 10);
  }

  function togglePause() {
    isPaused = !isPaused;
    if (!isPaused) {
      isUserScrolling = false; // Reset user scrolling state when resuming
      scrollToBottom();
    }
  }

  async function handleToggleDebug() {
    try {
      const newState = !debugEnabled;
      await toggleDebugMode(newState);
      debugEnabled = newState;

      if (debugEnabled) {
        await loadHistoricalLogs();
        await startLogStream();
      } else {
        stopLogStream();
        logs = [];
      }
    } catch (e) {
      error = `Failed to toggle debug mode: ${e.message}`;
    }
  }

  async function handleClearLogs() {
    if (!confirm('Are you sure you want to clear all logs?')) {
      return;
    }

    try {
      await clearDebugLogs();
      logs = [];
      totalLogs = 0;
      availableComponents = new Set();
    } catch (e) {
      error = `Failed to clear logs: ${e.message}`;
    }
  }

  function exportLogs() {
    const content = filteredLogs.map(formatLogForExport).join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `theo-debug-logs-${new Date().toISOString()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function formatLogForExport(log) {
    const component = log.component ? `[${log.component}]` : '';
    return `${log.timestamp} ${log.level.padEnd(8)} ${component} ${log.message}`;
  }

  function getLevelClass(level) {
    return level.toLowerCase();
  }

  function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  // Computed filtered logs
  $: filteredLogs = logs.filter(log => {
    // Level filter
    if (!selectedLevels[log.level]) {
      return false;
    }

    // Source filter
    if (selectedSource !== 'all' && log.source !== selectedSource) {
      return false;
    }

    // Component filter
    if (selectedComponent !== 'all' && log.component !== selectedComponent) {
      return false;
    }

    // Search filter
    if (searchTerm && !log.message.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }

    return true;
  });
</script>

<div class="tab-panel">
  <h2>Debug Console</h2>
  <p class="subtitle">Real-time application logs and debugging information</p>

  <div class="section">
    <!-- Controls -->
    <div class="debug-controls">
      <div class="control-group">
        <button
          class="btn-toggle"
          class:active={debugEnabled}
          on:click={handleToggleDebug}
        >
          {debugEnabled ? 'Disable' : 'Enable'} Debug Logging
        </button>

        {#if debugEnabled}
          <span class="connection-status status-{connectionStatus}">
            {#if connectionStatus === 'connected'}
              ● Live
            {:else if connectionStatus === 'connecting'}
              ○ Connecting...
            {:else if connectionStatus === 'error'}
              ✕ Error
            {:else}
              ○ Disconnected
            {/if}
          </span>
        {/if}
      </div>

      {#if debugEnabled}
        <div class="control-group">
          <button class="btn-secondary" on:click={togglePause}>
            {isPaused ? '▶ Resume' : '⏸ Pause'}
          </button>
          <button class="btn-secondary" on:click={exportLogs}>
            ⬇ Export
          </button>
          <button class="btn-danger" on:click={handleClearLogs}>
            🗑 Clear
          </button>
          <span class="log-count">{totalLogs} logs</span>
        </div>
      {/if}
    </div>

    {#if error}
      <div class="error-message">
        {error}
      </div>
    {/if}

    {#if debugEnabled}
      <!-- Filters -->
      <div class="filters">
        <div class="filter-section">
          <label>Levels:</label>
          <div class="filter-checkboxes">
            {#each ['DEBUG', 'INFO', 'WARNING', 'ERROR'] as level}
              <label class="checkbox-label level-{level.toLowerCase()}">
                <input
                  type="checkbox"
                  bind:checked={selectedLevels[level]}
                />
                {level}
              </label>
            {/each}
          </div>
        </div>

        <div class="filter-section">
          <label for="source-filter">Source:</label>
          <select id="source-filter" bind:value={selectedSource}>
            <option value="all">All</option>
            <option value="backend">Backend</option>
            <option value="frontend">Frontend</option>
          </select>
        </div>

        <div class="filter-section">
          <label for="component-filter">Component:</label>
          <select id="component-filter" bind:value={selectedComponent}>
            <option value="all">All Components</option>
            {#each Array.from(availableComponents).sort() as component}
              <option value={component}>{component}</option>
            {/each}
          </select>
        </div>

        <div class="filter-section">
          <label for="search">Search:</label>
          <input
            id="search"
            type="text"
            placeholder="Filter messages..."
            bind:value={searchTerm}
          />
        </div>
      </div>

      <!-- Console -->
      <div class="console-container" bind:this={consoleContainer} on:scroll={handleScroll}>
        {#if isLoading}
          <div class="console-loading">Loading logs...</div>
        {:else if filteredLogs.length === 0}
          <div class="console-empty">
            {logs.length === 0 ? 'No logs yet. Waiting for activity...' : 'No logs match the current filters.'}
          </div>
        {:else}
          {#each filteredLogs as log (log.id)}
            <div class="log-entry level-{getLevelClass(log.level)}">
              <span class="log-timestamp">{formatTimestamp(log.timestamp)}</span>
              <span class="log-level">{log.level.padEnd(7)}</span>
              {#if log.component}
                <span class="log-component">[{log.component}]</span>
              {/if}
              <span class="log-message">{log.message}</span>
            </div>
          {/each}
        {/if}
      </div>

      <div class="console-footer">
        Showing {filteredLogs.length} of {logs.length} logs
        {#if isPaused}
          <span class="paused-indicator">● PAUSED</span>
        {/if}
      </div>
    {:else}
      <div class="debug-disabled-message">
        <p>Debug logging is currently disabled.</p>
        <p class="note">Enable debug logging to capture and view application logs in real-time.</p>
      </div>
    {/if}
  </div>
</div>

<style>
  .debug-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    flex-wrap: wrap;
    gap: 1rem;
    background: var(--bg-secondary, #f8f9fa);
    padding: 1rem;
    border: 1px solid var(--border-primary, #e0e0e0);
    border-radius: 6px;
  }

  .control-group {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .btn-toggle {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.2s ease;
    color: white;
  }

  .btn-toggle:not(.active) {
    background: var(--theo-blue, #4a90e2);
    border: 1px solid var(--theo-blue, #4a90e2);
  }

  .btn-toggle:not(.active):hover {
    background: #357abd;
    border-color: #357abd;
  }

  .btn-toggle.active {
    background: var(--color-error);
    border: 1px solid var(--color-error);
  }

  .btn-toggle.active:hover {
    background: #c53030;
    border-color: #c53030;
  }

  .btn-secondary {
    padding: 0.4rem 0.8rem;
    background: var(--color-gray-100);
    border: 1px solid var(--color-gray-300);
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
  }

  .btn-secondary:hover {
    background: var(--color-gray-200);
  }

  .btn-danger {
    padding: 0.4rem 0.8rem;
    background: var(--color-error);
    color: white;
    border: 1px solid var(--color-error);
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
  }

  .btn-danger:hover {
    background: #c53030;
  }

  .connection-status {
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.85rem;
    font-weight: 500;
  }

  .status-connected {
    background: #d4edda;
    color: #155724;
  }

  .status-connecting {
    background: #fff3cd;
    color: #856404;
  }

  .status-error {
    background: #f8d7da;
    color: #721c24;
  }

  .status-disconnected {
    background: var(--color-gray-200);
    color: var(--color-gray-600);
  }

  .log-count {
    font-size: 0.9rem;
    color: var(--color-gray-600);
  }

  .error-message {
    background: #f8d7da;
    color: #721c24;
    padding: 0.75rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .filters {
    background: var(--color-gray-50);
    padding: 1rem;
    border-radius: 6px;
    margin-bottom: 1rem;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
  }

  .filter-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .filter-section label {
    font-weight: 500;
    font-size: 0.9rem;
  }

  .filter-checkboxes {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .checkbox-label input {
    cursor: pointer;
  }

  .console-container {
    background: #1e1e1e;
    color: #d4d4d4;
    font-family: 'Monaco', 'Menlo', 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    padding: 1rem;
    border-radius: 6px;
    height: 600px;
    overflow-y: auto;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .console-loading,
  .console-empty {
    color: #808080;
    text-align: center;
    padding: 2rem;
  }

  .log-entry {
    margin-bottom: 2px;
    padding: 2px 0;
  }

  .log-entry:hover {
    background: rgba(255, 255, 255, 0.05);
  }

  .log-timestamp {
    color: #858585;
    margin-right: 0.5rem;
  }

  .log-level {
    margin-right: 0.5rem;
    font-weight: 600;
  }

  .level-debug .log-level {
    color: #858585;
  }

  .level-info .log-level {
    color: #4fc3f7;
  }

  .level-warning .log-level {
    color: #ffb74d;
  }

  .level-error .log-level {
    color: #e57373;
  }

  .log-component {
    color: #9cdcfe;
    margin-right: 0.5rem;
  }

  .log-message {
    color: #d4d4d4;
  }

  .console-footer {
    margin-top: 0.5rem;
    font-size: 0.85rem;
    color: var(--color-gray-600);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .paused-indicator {
    color: var(--color-warning);
    font-weight: 600;
  }

  .debug-disabled-message {
    text-align: center;
    padding: 3rem;
    color: var(--color-gray-600);
  }

  .debug-disabled-message .note {
    font-size: 0.9rem;
    margin-top: 0.5rem;
  }

  /* Scrollbar styling for dark console */
  .console-container::-webkit-scrollbar {
    width: 8px;
  }

  .console-container::-webkit-scrollbar-track {
    background: #2d2d2d;
  }

  .console-container::-webkit-scrollbar-thumb {
    background: #555;
    border-radius: 4px;
  }

  .console-container::-webkit-scrollbar-thumb:hover {
    background: #666;
  }
</style>
