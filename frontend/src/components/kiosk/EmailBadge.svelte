<script>
  export let email = null;
</script>

{#if email && email.unread_count > 0}
  <div class="email-badge">
    <svg class="badge-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="2" y="4" width="20" height="16" rx="2"/>
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>
    </svg>
    <span class="badge-count">{email.unread_count}</span>
  </div>
{/if}

<style>
  .email-badge {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.25rem;
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 12px;
    backdrop-filter: blur(10px);
  }

  .badge-icon {
    width: 20px;
    height: 20px;
    color: #ef4444;
  }

  .badge-count {
    font-size: 1.1rem;
    font-weight: 600;
    color: #ef4444;
    font-family: 'Courier New', monospace;
  }
</style>
