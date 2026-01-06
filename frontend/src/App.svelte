<script>
  import { onMount } from "svelte";
  import Chat from "./components/Chat.svelte";
  import Settings from "./components/Settings.svelte";
  import Login from "./components/Login.svelte";
  import {
    getSessions,
    deleteSessionApi,
    verifySession,
    logout,
    getUserMode,
    setUserMode,
    getWorkSubtabConfig,
    getFolders,
    createFolder,
    renameFolder,
    deleteFolder,
    updateFolderCollapsed,
    moveSessionToFolder,
    archiveSession
  } from "./lib/api.js";

  let isAuthenticated = false;
  let currentUser = null;
  let showSettings = false;
  let currentMode = "personal"; // "work" or "personal"
  let activeWorkSubtab = "conversation"; // "conversation" | "email" | "code"

  // Dropdown state
  let modeDropdownOpen = false;
  let settingsDropdownOpen = false;

  // Mobile sidebar toggle state
  let sidebarOpen = false;
  $: {
    if (typeof document !== "undefined") {
      document.body.classList.toggle("no-scroll", sidebarOpen);
    }
  }

  // Sidebar enhancement states (Issue #77)
  let sidebarCollapsed = false;
  let sidebarWidth = 260; // Default width in pixels
  let isResizing = false;
  let sessionModeFilter = "all"; // "all", "personal", or "work"

  const MIN_SIDEBAR_WIDTH = 200;
  const MAX_SIDEBAR_WIDTH = 500;

  // Load sidebar preferences from localStorage
  function loadSidebarPreferences() {
    if (typeof localStorage === "undefined") return;

    const collapsed = localStorage.getItem("theo.sidebarCollapsed");
    const width = localStorage.getItem("theo.sidebarWidth");
    const modeFilter = localStorage.getItem("theo.sessionModeFilter");

    if (collapsed) sidebarCollapsed = collapsed === "true";
    if (width) sidebarWidth = parseInt(width) || 260;
    if (modeFilter) sessionModeFilter = modeFilter;
  }

  // Save sidebar preferences to localStorage
  function saveSidebarPreference(key, value) {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(`theo.${key}`, value);
  }

  // Toggle sidebar collapsed state
  function toggleSidebarCollapse() {
    sidebarCollapsed = !sidebarCollapsed;
    saveSidebarPreference("sidebarCollapsed", sidebarCollapsed);
  }

  // Start resizing sidebar
  function startResize(event) {
    event.preventDefault();
    isResizing = true;
    document.addEventListener("mousemove", handleResize);
    document.addEventListener("mouseup", stopResize);
    document.body.style.cursor = "ew-resize";
    document.body.style.userSelect = "none";
  }

  // Handle resize drag
  function handleResize(event) {
    if (!isResizing) return;

    const newWidth = event.clientX;
    if (newWidth >= MIN_SIDEBAR_WIDTH && newWidth <= MAX_SIDEBAR_WIDTH) {
      sidebarWidth = newWidth;
    }
  }

  // Stop resizing sidebar
  function stopResize() {
    if (isResizing) {
      isResizing = false;
      document.removeEventListener("mousemove", handleResize);
      document.removeEventListener("mouseup", stopResize);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      saveSidebarPreference("sidebarWidth", sidebarWidth);
    }
  }

  // Toggle session mode filter
  function toggleSessionModeFilter(mode) {
    sessionModeFilter = mode;
    saveSidebarPreference("sessionModeFilter", mode);
  }

  // Close dropdowns when clicking outside
  function handleClickOutside(event) {
    const target = event.target;
    if (!target.closest('.dropdown')) {
      modeDropdownOpen = false;
      settingsDropdownOpen = false;
    }
  }

  // Session timeout management
  let sessionTimeoutId = null;
  const DEFAULT_TIMEOUT_HOURS = 8;

  function startSessionTimeout() {
    // Clear any existing timeout
    if (sessionTimeoutId) {
      clearTimeout(sessionTimeoutId);
    }

    // Get timeout setting from localStorage (in hours)
    const timeoutHours = parseInt(localStorage.getItem("theo.sessionTimeout")) || DEFAULT_TIMEOUT_HOURS;
    const timeoutMs = timeoutHours * 60 * 60 * 1000;

    sessionTimeoutId = setTimeout(async () => {
      alert(`Your session has expired after ${timeoutHours} hours of inactivity. Please log in again.`);
      await handleLogout();
    }, timeoutMs);
  }

  function resetSessionTimeout() {
    if (isAuthenticated) {
      startSessionTimeout();
    }
  }

  // Reset timeout on user activity
  function handleUserActivity() {
    resetSessionTimeout();
  }

  onMount(() => {
    document.addEventListener('click', handleClickOutside);
    document.addEventListener('click', handleUserActivity);
    document.addEventListener('keydown', handleUserActivity);

    // Load sidebar preferences
    loadSidebarPreferences();

    // Start timeout if authenticated
    if (isAuthenticated) {
      startSessionTimeout();
    }

    return () => {
      document.removeEventListener('click', handleClickOutside);
      document.removeEventListener('click', handleUserActivity);
      document.removeEventListener('keydown', handleUserActivity);
      if (sessionTimeoutId) {
        clearTimeout(sessionTimeoutId);
      }
    };
  });
  function openSidebar() {
    sidebarOpen = true;
  }
  function closeSidebar() {
    sidebarOpen = false;
  }

  // Theme loading function (for new multi-theme system)
  function loadTheme() {
    if (typeof document === "undefined") return;

    // Get theme from localStorage (set by ThemeSettings.svelte)
    const savedTheme = localStorage.getItem("theme") || "light";

    // Apply theme using the new system
    if (savedTheme === "dark") {
      document.documentElement.classList.add("dark");
      document.documentElement.removeAttribute("data-theme");
    } else if (savedTheme === "light") {
      document.documentElement.classList.remove("dark");
      document.documentElement.removeAttribute("data-theme");
    } else {
      // Custom themes (cyberpunk, nature, corporate)
      document.documentElement.classList.remove("dark");
      document.documentElement.setAttribute("data-theme", savedTheme);
    }
  }

  let sessions = [];
  let activeSessionId = null;
  const MAX_SESSIONS = 20;

  const SESSION_STORAGE_KEY = "theo.activeSessionId";

  let confirmDeleteId = null;

  let sessionQuery = "";

  // Folder state
  let folders = [];
  let showArchive = false;
  let newFolderName = "";
  let showNewFolderInput = false;
  let editingFolderId = null;
  let editingFolderName = "";
  let draggedSessionId = null;

  // Reactive filtered sessions based on mode filter and search query
  $: filteredSessions = sessions
    .filter(s => (s.title && s.title.trim()) || (s.summary && s.summary.trim())) // hasContent
    .filter(s => {
      // sessionMatches
      if (!sessionQuery.trim()) return true;
      const q = sessionQuery.toLowerCase();
      const label = s.title?.slice(0, 60) || s.summary?.slice(0, 60) || "New chat";
      return label.toLowerCase().includes(q);
    })
    .filter(s => {
      // sessionModeMatches
      if (sessionModeFilter === "all") return true;
      const mode = s.mode || "personal";
      return mode === sessionModeFilter;
    })
    .sort((a, b) => {
      // Sort by updated_at: NULL/missing dates first (new chats at top), then by most recent
      const aTime = a.updated_at ? new Date(a.updated_at).getTime() : Infinity;
      const bTime = b.updated_at ? new Date(b.updated_at).getTime() : Infinity;
      return bTime - aTime; // Descending order (newest/NULL first)
    });

  // Group sessions by folder
  $: sessionsByFolder = (() => {
    const result = {
      archive: [],
      unfiled: [],
      folders: {}
    };

    // Get archive folder
    const archiveFolder = folders.find(f => f.is_system && f.name === "Archive");

    // Initialize folder buckets
    folders.forEach(folder => {
      if (!folder.is_system) {
        result.folders[folder.id] = {
          folder: folder,
          sessions: []
        };
      }
    });

    // Categorize sessions
    filteredSessions.forEach(session => {
      if (!session.folder_id) {
        result.unfiled.push(session);
      } else if (archiveFolder && session.folder_id === archiveFolder.id) {
        result.archive.push(session);
      } else if (result.folders[session.folder_id]) {
        result.folders[session.folder_id].sessions.push(session);
      } else {
        // Folder not found, treat as unfiled
        result.unfiled.push(session);
      }
    });

    return result;
  })();

  async function loadFolders() {
    try {
      folders = await getFolders();
      // Load collapsed states from localStorage
      const savedStates = localStorage.getItem('folderCollapsedStates');
      if (savedStates) {
        const states = JSON.parse(savedStates);
        folders = folders.map(f => ({
          ...f,
          collapsed: states[f.id] !== undefined ? states[f.id] : f.collapsed
        }));
      }
    } catch (err) {
      console.error("Failed to load folders", err);
      folders = [];
    }
  }

  async function handleCreateFolder() {
    if (!newFolderName.trim()) return;

    try {
      await createFolder(newFolderName.trim());
      newFolderName = "";
      showNewFolderInput = false;
      await loadFolders();
    } catch (err) {
      console.error("Failed to create folder", err);
      alert("Failed to create folder: " + err.message);
    }
  }

  async function handleRenameFolder(folderId) {
    if (!editingFolderName.trim()) return;

    try {
      await renameFolder(folderId, editingFolderName.trim());
      editingFolderId = null;
      editingFolderName = "";
      await loadFolders();
    } catch (err) {
      console.error("Failed to rename folder", err);
      alert("Failed to rename folder: " + err.message);
    }
  }

  async function handleDeleteFolder(folderId) {
    if (!confirm("Delete this folder? Sessions will be moved to Unfiled.")) return;

    try {
      await deleteFolder(folderId);
      await loadFolders();
    } catch (err) {
      console.error("Failed to delete folder", err);
      alert("Failed to delete folder: " + err.message);
    }
  }

  async function toggleFolderCollapse(folderId) {
    const folder = folders.find(f => f.id === folderId);
    if (!folder) return;

    const newCollapsed = !folder.collapsed;

    try {
      await updateFolderCollapsed(folderId, newCollapsed);
      // Update local state
      folders = folders.map(f =>
        f.id === folderId ? { ...f, collapsed: newCollapsed } : f
      );
      // Save to localStorage
      const states = {};
      folders.forEach(f => states[f.id] = f.collapsed);
      localStorage.setItem('folderCollapsedStates', JSON.stringify(states));
    } catch (err) {
      console.error("Failed to toggle folder collapse", err);
    }
  }

  function handleDragStart(event, sessionId) {
    draggedSessionId = sessionId;
    event.dataTransfer.effectAllowed = "move";
  }

  function handleDragOver(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }

  async function handleDrop(event, targetFolderId) {
    event.preventDefault();

    if (!draggedSessionId) return;

    try {
      await moveSessionToFolder(draggedSessionId, targetFolderId);
      await loadSessions();
      draggedSessionId = null;
    } catch (err) {
      console.error("Failed to move session", err);
      alert("Failed to move session: " + err.message);
    }
  }

  async function handleArchiveSession(sessionId) {
    try {
      await archiveSession(sessionId);
      await loadSessions();
    } catch (err) {
      console.error("Failed to archive session", err);
      alert("Failed to archive session: " + err.message);
    }
  }

  function generateUUID() {
    if (crypto && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    // Fallback RFC4122 v4
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
      const r = Math.random() * 16 | 0;
      const v = c === "x" ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

onMount(async () => {
  // Load theme preference (new multi-theme system)
  loadTheme();

  // Check authentication first
  try {
    const result = await verifySession();
    if (result.valid) {
      isAuthenticated = true;
      currentUser = result.user;
      await loadSessions();
      await loadFolders();
      await loadUserMode();
    }
  } catch (err) {
    console.error("Session verification failed", err);
    isAuthenticated = false;
  }

  // Listen for session title generation events
  window.addEventListener("sessionTitleGenerated", async (e) => {
    const { sessionId, title } = e.detail;
    // Refresh sessions list to show new title
    try {
      const updatedSessions = await getSessions();
      sessions = updatedSessions.filter(hasContent);
    } catch (err) {
      console.error("Failed to refresh sessions after title generation:", err);
    }
  });

  // Listen for work subtab changes from Chat component
  window.addEventListener("workSubtabChanged", (e) => {
    activeWorkSubtab = e.detail.subtab;
  });
});

async function loadSessions() {
  try {
    const stored = localStorage.getItem(SESSION_STORAGE_KEY);
    if (stored) {
      activeSessionId = stored;
    }

    sessions = await getSessions();
    sessions = sessions.filter(hasContent);

    if (!activeSessionId || !sessions.find(s => s.id === activeSessionId)) {
      activeSessionId = sessions.length
        ? sessions[0].id
        : generateUUID();
    }

    localStorage.setItem(SESSION_STORAGE_KEY, activeSessionId);
  } catch (err) {
    console.error("Failed to load sessions", err);
    sessions = [];
  }
}

async function loadUserMode() {
  try {
    const modeConfig = await getUserMode();
    currentMode = modeConfig.active_mode || "personal";
  } catch (err) {
    console.error("Failed to load user mode", err);
    currentMode = "personal";
  }
}

async function setMode(mode) {
  if (mode === currentMode) return; // Already in this mode

  const previousMode = currentMode;

  try {
    // Notify old chat BEFORE switching
    window.dispatchEvent(new CustomEvent("modeSwitching", {
      detail: { fromMode: previousMode, toMode: mode }
    }));

    await setUserMode(mode);
    currentMode = mode;

    // Brief delay for notification to render
    await new Promise(resolve => setTimeout(resolve, 500));

    // Reload sessions (backend auto-filters by new mode)
    loadSessions();

    // Load last active subtab from localStorage when switching to work mode
    if (mode === "work") {
      const savedSubtab = localStorage.getItem("theo.activeWorkSubtab");
      if (savedSubtab && ["conversation", "email", "code"].includes(savedSubtab)) {
        activeWorkSubtab = savedSubtab;
      }
    }
  } catch (err) {
    console.error("Failed to switch mode", err);
  }
}

function handleLogin(token, user) {
  isAuthenticated = true;
  currentUser = user;
  loadSessions();
  loadUserMode();

  // Start session timeout
  startSessionTimeout();

  // Load last active work subtab
  const savedSubtab = localStorage.getItem("theo.activeWorkSubtab");
  if (savedSubtab && ["conversation", "email", "code"].includes(savedSubtab)) {
    activeWorkSubtab = savedSubtab;
  }
}

async function handleLogout() {
  try {
    await logout();
  } catch (err) {
    console.error("Logout failed", err);
  } finally {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("user");
    isAuthenticated = false;
    currentUser = null;
    sessions = [];
  }
}

  function selectSession(id) {
    const session = sessions.find(s => s.id === id);

    // Check mode mismatch - select the session but it will be locked
    if (session && session.mode && session.mode !== currentMode) {
      // Still select it, but Chat.svelte will show it as locked
      activeSessionId = id;
      localStorage.setItem(SESSION_STORAGE_KEY, id);
      sidebarOpen = false;
      showSettings = false; // Navigate to chat view
      // Chat will detect mode mismatch and disable input
      return;
    }

    // Normal selection
    activeSessionId = id;
    localStorage.setItem(SESSION_STORAGE_KEY, id);
    sidebarOpen = false;
    showSettings = false; // Navigate to chat view
  }

  function newSession() {
    const id = generateUUID();
    activeSessionId = id;
    localStorage.setItem(SESSION_STORAGE_KEY, id);
    // Optimistically add to top of list with current timestamp
    sessions = [{ id, title: "New chat", summary: "", mode: currentMode, updated_at: new Date().toISOString() }, ...sessions].slice(0, MAX_SESSIONS);
  }

  async function deleteSession(id) {
    try {
      await deleteSessionApi(id);

      sessions = sessions.filter(s => s.id !== id);

      if (activeSessionId === id) {
        if (sessions.length) {
          activeSessionId = sessions[0].id;
        } else {
          activeSessionId = generateUUID();
          sessions = [{ id: activeSessionId, title: "New chat", summary: "", mode: currentMode }];
        }
        localStorage.setItem(SESSION_STORAGE_KEY, activeSessionId);
      }

      confirmDeleteId = null;
    } catch (err) {
      console.error("Failed to delete session", err);
      confirmDeleteId = null;
    }
  }

  function sessionModePrefix(session) {
    return session.mode === "work" ? "Work:" : "Personal:";
  }

  function sessionLabel(session) {
    if (session.title && session.title.trim()) {
      return session.title.slice(0, 60);
    } else if (session.summary && session.summary.trim()) {
      return session.summary.slice(0, 60);
    } else {
      return "New chat";
    }
  }

  function formatSessionTime(dateStr) {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    const hours = d.getHours();
    const minutes = d.getMinutes().toString().padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    return `${displayHours}:${minutes} ${ampm}`;
  }

  function sessionMatches(session) {
    if (!sessionQuery.trim()) return true;
    const q = sessionQuery.toLowerCase();
    return sessionLabel(session).toLowerCase().includes(q);
  }

  function sessionModeMatches(session) {
    if (sessionModeFilter === "all") return true;
    // Default to "personal" if mode is not set
    const mode = session.mode || "personal";
    return mode === sessionModeFilter;
  }

  function hasContent(session) {
    return (
      (session.title && session.title.trim()) ||
      (session.summary && session.summary.trim())
    );
  }

  function dayGroup(dateStr) {
    const d = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    const sameDay = (a, b) =>
      a.getFullYear() === b.getFullYear() &&
      a.getMonth() === b.getMonth() &&
      a.getDate() === b.getDate();

    if (sameDay(d, today)) return "Today";
    if (sameDay(d, yesterday)) return "Yesterday";
    return "Earlier";
  }
</script>

<main class="app-layout app-root">
  {#if !isAuthenticated}
    <Login onLogin={handleLogin} />
  {:else}
  <header class="header">
    <div class="header-left">
      <button class="hamburger" on:click={openSidebar}>☰</button>
      <button
        class="logo-button"
        on:click={() => { showSettings = false; }}
        title="Go to Chat"
        aria-label="Go to Chat"
      >
        <img
          src="/logo.svg"
          alt="THEO"
          class="logo"
        />
      </button>
    </div>

    <div class="header-right">
      <div class="dropdown" class:open={modeDropdownOpen}>
        <button
          class="btn-pill btn-mode"
          class:mode-work={currentMode === "work"}
          class:mode-personal={currentMode === "personal"}
          on:click={() => { modeDropdownOpen = !modeDropdownOpen; }}
        >
          {currentMode === "work" ? "Work Mode" : "Personal Mode"}
        </button>
        {#if modeDropdownOpen}
          <div class="dropdown-content">
            <button
              class="dropdown-item"
              class:active={currentMode === "personal"}
              on:click={() => { setMode("personal"); modeDropdownOpen = false; }}
            >
             Personal
            </button>
            <button
              class="dropdown-item"
              class:active={currentMode === "work"}
              on:click={() => { setMode("work"); modeDropdownOpen = false; }}
            >
              Work
            </button>
          </div>
        {/if}
      </div>

      <div class="dropdown" class:open={settingsDropdownOpen}>
        <button class="btn-pill" on:click={() => { settingsDropdownOpen = !settingsDropdownOpen; }}>
          Menu
        </button>
        {#if settingsDropdownOpen}
          <div class="dropdown-content">
            <button
              class="dropdown-item"
              on:click={() => { showSettings = true; settingsDropdownOpen = false; }}
            >
              Settings
            </button>
            <button
              class="dropdown-item"
              on:click={() => { handleLogout(); settingsDropdownOpen = false; }}
            >
              Logout
            </button>
          </div>
        {/if}
      </div>
    </div>
  </header>

<div class="app-body">

  <div class="shell layout-shell" style="grid-template-columns: {sidebarCollapsed ? '50px' : `${sidebarWidth}px`} minmax(0, 1fr);">
    <!-- Sidebar placeholder (sessions will move here later) -->
    <aside
      class="sidebar"
      class:open={sidebarOpen}
      class:collapsed={sidebarCollapsed}
      style="width: {sidebarCollapsed ? '50px' : `${sidebarWidth}px`};"
    >
      <!-- Sidebar Header with Controls -->
      <div class="sidebar-header">
        {#if !sidebarCollapsed}
          <div class="sidebar-title">Sessions</div>
        {/if}
        <button
          class="sidebar-control-btn"
          on:click={toggleSidebarCollapse}
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? '☰' : '×'}
        </button>
      </div>

      {#if !sidebarCollapsed}
        <div class="sidebar-content">
          <button class="btn-pill new-session" on:click={newSession}>
            + New chat
          </button>

          <!-- Mode Filter Toggle -->
          <div class="mode-filter">
          <button
            class="mode-filter-btn"
            class:active={sessionModeFilter === "all"}
            on:click={() => toggleSessionModeFilter("all")}
          >
            All
          </button>
          <button
            class="mode-filter-btn"
            class:active={sessionModeFilter === "personal"}
            on:click={() => toggleSessionModeFilter("personal")}
          >
            Personal
          </button>
          <button
            class="mode-filter-btn"
            class:active={sessionModeFilter === "work"}
            on:click={() => toggleSessionModeFilter("work")}
          >
            Work
          </button>
        </div>

        <input
          class="session-search"
          type="text"
          placeholder="Search chats"
          bind:value={sessionQuery}
        />

      <!-- Chats (Unfiled Sessions) -->
      {#if sessionsByFolder.unfiled.length > 0}
        <div class="folder-section">
          <div
            class="folder-header unfiled-header"
            on:dragover={handleDragOver}
            on:drop={(e) => handleDrop(e, null)}
          >
            <span class="folder-name">Chats</span>
            <span class="folder-count">({sessionsByFolder.unfiled.length})</span>
          </div>

          {#each ["Today", "Yesterday", "Earlier"] as group}
            {#if sessionsByFolder.unfiled.some(s => dayGroup(s.updated_at) === group)}
              <div class="session-group">{group}</div>
            {/if}

            {#each sessionsByFolder.unfiled
              .filter(s => dayGroup(s.updated_at) === group && sessionMatches(s) && sessionModeMatches(s))
              .slice(0, MAX_SESSIONS) as s}

              <div
                class="session-row"
                class:active={s.id === activeSessionId}
                draggable="true"
                on:dragstart={(e) => handleDragStart(e, s.id)}
              >
                <button
                  class="session-item"
                  on:click={() => selectSession(s.id)}
                >
                  <div class="session-label">
                    <span class="session-mode">{sessionModePrefix(s)}</span> {sessionLabel(s)}
                  </div>
                  <div class="session-time">{formatSessionTime(s.updated_at)}</div>
                </button>

                {#if confirmDeleteId === s.id}
                  <div class="confirm">
                    <button class="danger" on:click={() => deleteSession(s.id)}>Delete</button>
                    <button on:click={() => confirmDeleteId = null}>Cancel</button>
                  </div>
                {:else}
                  <div class="session-actions">
                    <button
                      class="action-btn archive-btn"
                      title="Archive chat"
                      on:click={() => handleArchiveSession(s.id)}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="21 8 21 21 3 21 3 8"/>
                        <rect x="1" y="3" width="22" height="5"/>
                        <line x1="10" y1="12" x2="14" y2="12"/>
                      </svg>
                    </button>
                    <button
                      class="action-btn delete-btn"
                      title="Delete chat"
                      on:click={() => confirmDeleteId = s.id}
                    >
                      ×
                    </button>
                  </div>
                {/if}
              </div>
            {/each}
          {/each}
        </div>
      {/if}

      <!-- Custom Folders -->
      {#each folders.filter(f => !f.is_system) as folder}
        <div class="folder-section">
          <button
            class="folder-header"
            on:click={() => toggleFolderCollapse(folder.id)}
            on:dragover={handleDragOver}
            on:drop={(e) => handleDrop(e, folder.id)}
          >
            <span class="folder-icon">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                {#if folder.collapsed}
                  <polyline points="9 18 15 12 9 6"/>
                {:else}
                  <polyline points="6 9 12 15 18 9"/>
                {/if}
              </svg>
            </span>
            {#if editingFolderId === folder.id}
              <input
                class="folder-name-input"
                type="text"
                bind:value={editingFolderName}
                on:blur={() => handleRenameFolder(folder.id)}
                on:keydown={(e) => e.key === 'Enter' && handleRenameFolder(folder.id)}
                on:click|stopPropagation
                autofocus
              />
            {:else}
              <span class="folder-name">{folder.name}</span>
            {/if}
            <div class="folder-actions">
              <button
                class="folder-action-btn"
                title="Rename folder"
                on:click|stopPropagation={() => {
                  editingFolderId = folder.id;
                  editingFolderName = folder.name;
                }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </button>
              <button
                class="folder-action-btn"
                title="Delete folder"
                on:click|stopPropagation={() => handleDeleteFolder(folder.id)}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  <line x1="10" y1="11" x2="10" y2="17"/>
                  <line x1="14" y1="11" x2="14" y2="17"/>
                </svg>
              </button>
            </div>
            <span class="folder-count">({sessionsByFolder.folders[folder.id]?.sessions.length || 0})</span>
          </button>

          {#if !folder.collapsed && sessionsByFolder.folders[folder.id]?.sessions.length > 0}
            {#each ["Today", "Yesterday", "Earlier"] as group}
              {#if sessionsByFolder.folders[folder.id].sessions.some(s => dayGroup(s.updated_at) === group)}
                <div class="session-group">{group}</div>
              {/if}

              {#each sessionsByFolder.folders[folder.id].sessions
                .filter(s => dayGroup(s.updated_at) === group && sessionMatches(s) && sessionModeMatches(s))
                .slice(0, MAX_SESSIONS) as s}

                <div
                  class="session-row"
                  class:active={s.id === activeSessionId}
                  draggable="true"
                  on:dragstart={(e) => handleDragStart(e, s.id)}
                >
                  <button
                    class="session-item"
                    on:click={() => selectSession(s.id)}
                  >
                    <div class="session-label">
                      <span class="session-mode">{sessionModePrefix(s)}</span> {sessionLabel(s)}
                    </div>
                    <div class="session-time">{formatSessionTime(s.updated_at)}</div>
                  </button>

                  {#if confirmDeleteId === s.id}
                    <div class="confirm">
                      <button class="danger" on:click={() => deleteSession(s.id)}>Delete</button>
                      <button on:click={() => confirmDeleteId = null}>Cancel</button>
                    </div>
                  {:else}
                    <div class="session-actions">
                      <button
                        class="action-btn archive-btn"
                        title="Archive chat"
                        on:click={() => handleArchiveSession(s.id)}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <polyline points="21 8 21 21 3 21 3 8"/>
                          <rect x="1" y="3" width="22" height="5"/>
                          <line x1="10" y1="12" x2="14" y2="12"/>
                        </svg>
                      </button>
                      <button
                        class="action-btn delete-btn"
                        title="Delete chat"
                        on:click={() => confirmDeleteId = s.id}
                      >
                        ×
                      </button>
                    </div>
                  {/if}
                </div>
              {/each}
            {/each}
          {/if}
        </div>
      {/each}

      <!-- Archive Folder -->
      <div class="folder-section">
        <button
          class="folder-header"
          on:click={() => showArchive = !showArchive}
          on:dragover={handleDragOver}
          on:drop={(e) => handleDrop(e, folders.find(f => f.is_system)?.id)}
        >
          <span class="folder-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              {#if showArchive}
                <polyline points="6 9 12 15 18 9"/>
              {:else}
                <polyline points="9 18 15 12 9 6"/>
              {/if}
            </svg>
          </span>
          <span class="folder-name">Archive</span>
          <span class="folder-count">({sessionsByFolder.archive.length})</span>
        </button>

        {#if showArchive && sessionsByFolder.archive.length > 0}
          {#each ["Today", "Yesterday", "Earlier"] as group}
            {#if sessionsByFolder.archive.some(s => dayGroup(s.updated_at) === group)}
              <div class="session-group">{group}</div>
            {/if}

            {#each sessionsByFolder.archive
              .filter(s => dayGroup(s.updated_at) === group && sessionMatches(s) && sessionModeMatches(s))
              .slice(0, MAX_SESSIONS) as s}

              <div
                class="session-row"
                class:active={s.id === activeSessionId}
                draggable="true"
                on:dragstart={(e) => handleDragStart(e, s.id)}
              >
                <button
                  class="session-item"
                  on:click={() => selectSession(s.id)}
                >
                  <div class="session-label">
                    <span class="session-mode">{sessionModePrefix(s)}</span> {sessionLabel(s)}
                  </div>
                  <div class="session-time">{formatSessionTime(s.updated_at)}</div>
                </button>

                {#if confirmDeleteId === s.id}
                  <div class="confirm">
                    <button class="danger" on:click={() => deleteSession(s.id)}>Delete</button>
                    <button on:click={() => confirmDeleteId = null}>Cancel</button>
                  </div>
                {:else}
                  <button
                    class="delete-btn"
                    title="Delete chat"
                    on:click={() => confirmDeleteId = s.id}
                  >
                    ×
                  </button>
                {/if}
              </div>
            {/each}
          {/each}
        {/if}
      </div>
        </div>

        <!-- New Folder Button (Pinned to bottom) -->
        <div class="sidebar-footer">
          <div class="new-folder-section">
            {#if showNewFolderInput}
              <div class="new-folder-input-wrapper">
                <input
                  class="new-folder-input"
                  type="text"
                  placeholder="Folder name..."
                  bind:value={newFolderName}
                  on:keydown={(e) => {
                    if (e.key === 'Enter') handleCreateFolder();
                    if (e.key === 'Escape') { showNewFolderInput = false; newFolderName = ""; }
                  }}
                  autofocus
                />
                <button
                  class="btn-pill"
                  on:mousedown={(e) => { e.preventDefault(); handleCreateFolder(); }}
                >
                  Create
                </button>
              </div>
            {:else}
              <button
                class="btn-pill new-folder-btn"
                on:click={() => showNewFolderInput = true}
              >
                + New folder
              </button>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Resize Handle -->
      {#if !sidebarCollapsed}
        <button
          class="resize-handle"
          on:mousedown={startResize}
          aria-label="Resize sidebar"
          aria-orientation="vertical"
          title="Drag to resize sidebar"
        ></button>
      {/if}
    </aside>
    {#if sidebarOpen}
      <div
        class="sidebar-backdrop"
        on:click={closeSidebar}
        on:keydown={(e) => e.key === 'Escape' && closeSidebar()}
        role="button"
        tabindex="0"
        aria-label="Close sidebar"
      ></div>
    {/if}

    <section class="main">
      <div class="chat-main">
        {#if showSettings}
          <Settings />
        {:else}
          <Chat
            sessionId={activeSessionId}
            currentMode={currentMode}
            sessionMode={sessions.find(s => s.id === activeSessionId)?.mode}
            activeWorkSubtab={activeWorkSubtab}
          />
        {/if}
      </div>
    </section>
  </div>
  </div>
  {/if}
</main>
