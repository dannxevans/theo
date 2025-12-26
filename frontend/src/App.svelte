<svelte:head>
  <link rel="stylesheet" href="/style.css" />
</svelte:head>

<script>
  import { onMount } from "svelte";
  import Chat from "./components/Chat.svelte";
  import Settings from "./components/Settings.svelte";
  import { getSessions, deleteSessionApi } from "./lib/api.js";

  let showSettings = false;

  // Mobile sidebar toggle state
  let sidebarOpen = false;
  $: {
    if (typeof document !== "undefined") {
      document.body.classList.toggle("no-scroll", sidebarOpen);
    }
  }
  function openSidebar() {
    sidebarOpen = true;
  }
  function closeSidebar() {
    sidebarOpen = false;
  }

  let sessions = [];
  let activeSessionId = null;
  const MAX_SESSIONS = 20;

  const SESSION_STORAGE_KEY = "theo.activeSessionId";

  let confirmDeleteId = null;

  let sessionQuery = "";

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
});

  function selectSession(id) {
    activeSessionId = id;
    localStorage.setItem(SESSION_STORAGE_KEY, id);
    sidebarOpen = false;
  }

  function newSession() {
    const id = generateUUID();
    activeSessionId = id;
    localStorage.setItem(SESSION_STORAGE_KEY, id);
    // Optimistically add to top of list
    sessions = [{ id, title: "New chat", summary: "" }, ...sessions].slice(0, MAX_SESSIONS);
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
          sessions = [{ id: activeSessionId, title: "New chat", summary: "" }];
        }
        localStorage.setItem(SESSION_STORAGE_KEY, activeSessionId);
      }

      confirmDeleteId = null;
    } catch (err) {
      console.error("Failed to delete session", err);
      confirmDeleteId = null;
    }
  }

  function sessionLabel(session) {
    if (session.title && session.title.trim()) {
      return session.title.slice(0, 60);
    }
    if (session.summary && session.summary.trim()) {
      return session.summary.slice(0, 60);
    }
    return "New chat";
  }

  function sessionMatches(session) {
    if (!sessionQuery.trim()) return true;
    const q = sessionQuery.toLowerCase();
    return sessionLabel(session).toLowerCase().includes(q);
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
  <header class="header">
    <div class="header-left">
      <button class="hamburger" on:click={openSidebar}>☰</button>
      <img
        src="/logo.svg"
        alt="THEO"
        class="logo"
        on:click={() => { showSettings = false; }}
        style="cursor: pointer;"
        title="Go to Chat"
      />
    </div>

    <div class="header-right">
      <button
        class="btn-pill"
        class:active={!showSettings}
        on:click={() => { showSettings = false; }}
      >
        Chat
      </button>

      <button
        class="btn-pill"
        class:active={showSettings}
        on:click={() => { showSettings = true; }}
      >
        Settings
      </button>
    </div>
  </header>
<div class="app-body">

  <div class="shell layout-shell">
    <!-- Sidebar placeholder (sessions will move here later) -->
    <aside class="sidebar" class:open={sidebarOpen}>
      <div class="sidebar-title">Sessions</div>
      <button class="btn-pill new-session" on:click={newSession}>
        + New chat
      </button>

      <input
        class="session-search"
        type="text"
        placeholder="Search chats"
        bind:value={sessionQuery}
      />

      {#each ["Today", "Yesterday", "Earlier"] as group}
        {#if sessions.some(s => dayGroup(s.updated_at) === group && sessionMatches(s))}
          <div class="session-group">{group}</div>
        {/if}

        {#each sessions
          .filter(hasContent)
          .filter(s => dayGroup(s.updated_at) === group)
          .filter(sessionMatches)
          .slice(0, MAX_SESSIONS) as s}

          <div class="session-row" class:active={s.id === activeSessionId}>
            <button
              class="session-item"
              on:click={() => selectSession(s.id)}
            >
              {sessionLabel(s)}
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
    </aside>
    {#if sidebarOpen}
      <div class="sidebar-backdrop" on:click={closeSidebar}></div>
    {/if}

    <section class="main">
      <div class="chat-main">
        {#if showSettings}
          <Settings />
        {:else}
          <Chat sessionId={activeSessionId} />
        {/if}
      </div>
    </section>
  </div>
  </div>
</main>
