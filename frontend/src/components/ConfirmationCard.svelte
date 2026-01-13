<script>
  /**
   * ConfirmationCard - Reusable component for displaying action confirmations
   *
   * Used by orchestration system to display proposed actions that require user approval.
   * Matches existing M365 confirmation widget styling for consistency.
   */

  export let confirmation = null;
  export let onApprove = null;
  export let onReject = null;

  // Action type to icon mapping
  const actionIcons = {
    'create_calendar_event': '📅',
    'update_calendar_event': '📅',
    'delete_calendar_event': '🗑️',
    'create_task': '✓',
    'update_task': '✓',
    'complete_task': '✓',
    'delete_task': '🗑️',
    'send_email': '✉️',
    'reply_email': '✉️',
    'draft_email': '✉️',
  };

  // Get icon for action type
  function getActionIcon(type) {
    return actionIcons[type] || '📋';
  }

  // Format expiration time
  function formatExpiresAt(isoString) {
    if (!isoString) return "";

    try {
      const date = new Date(isoString);
      const now = new Date();
      const diff = date - now;

      if (diff < 0) return "Expired";

      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

      if (hours > 24) {
        return `${Math.floor(hours / 24)}d ${hours % 24}h`;
      } else if (hours > 0) {
        return `${hours}h ${minutes}m`;
      } else {
        return `${minutes}m`;
      }
    } catch (e) {
      console.error("Error formatting expiration:", e);
      return "Invalid date";
    }
  }

  // Handle approve click
  async function handleApproveClick() {
    if (onApprove && confirmation) {
      await onApprove(confirmation.confirmation_id);
    }
  }

  // Handle reject click
  async function handleRejectClick() {
    if (onReject && confirmation) {
      await onReject(confirmation.confirmation_id);
    }
  }

  // Reactive: Check if confirmation is approved or rejected
  $: isApproved = confirmation?.approved === true;
  $: isRejected = confirmation?.rejected === true;
  $: isCompleted = isApproved || isRejected;
  $: actionIcon = confirmation ? getActionIcon(confirmation.action_type || 'unknown') : '📋';
  $: expiresText = confirmation?.expires_at ? formatExpiresAt(confirmation.expires_at) : '';
</script>

{#if confirmation}
  <div class="confirmation-widget {isApproved ? 'approved' : ''} {isRejected ? 'rejected' : ''}">
    {#if isCompleted}
      <!-- Completed state (approved or rejected) -->
      <div class="confirmation-header">
        <span class="confirmation-icon">
          {#if isApproved}
            ✓ Approved
          {:else}
            ✗ Rejected
          {/if}
        </span>
      </div>

      <div class="confirmation-result">
        {#if isApproved}
          {confirmation.confirmation_message.replace('?', '.').replace('Create ', '')}
        {:else}
          Action rejected
        {/if}
      </div>

      <div class="confirmation-status-final {isApproved ? 'approved' : 'rejected'}">
        {#if isApproved}
          ✓ Completed
        {:else}
          ✗ Rejected
        {/if}
      </div>

    {:else}
      <!-- Pending state -->
      <div class="confirmation-header">
        <span class="confirmation-icon">
          {actionIcon} Action Required
        </span>
        <span class="confirmation-expires">
          Expires in {expiresText}
        </span>
      </div>

      <div class="confirmation-message">
        {confirmation.confirmation_message}
      </div>

      <div class="confirmation-actions">
        <button
          class="btn-approve"
          on:click={handleApproveClick}
          disabled={isCompleted}
        >
          ✓ Approve
        </button>
        <button
          class="btn-reject"
          on:click={handleRejectClick}
          disabled={isCompleted}
        >
          × Reject
        </button>
      </div>
    {/if}
  </div>
{/if}

<style>
  /* Import styles from parent Chat.svelte */
  /* These styles match the existing confirmation widget */

  .confirmation-widget {
    margin-top: 1rem;
    padding: 1rem;
    background: var(--bg-tertiary);
    border: 2px solid var(--theo-blue);
    border-radius: 8px;
  }

  .confirmation-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
  }

  .confirmation-icon {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--theo-blue);
  }

  .confirmation-expires {
    font-size: 0.85rem;
    color: var(--text-secondary);
  }

  .confirmation-message {
    margin-bottom: 1rem;
    font-size: 0.95rem;
    color: var(--text-primary);
  }

  .confirmation-actions {
    display: flex;
    gap: 0.75rem;
  }

  .btn-approve,
  .btn-reject {
    flex: 1;
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-approve {
    background: #28a745;
    color: white;
  }

  .btn-approve:hover:not(:disabled) {
    background: #218838;
  }

  .btn-reject {
    background: #dc3545;
    color: white;
  }

  .btn-reject:hover:not(:disabled) {
    background: #c82333;
  }

  .btn-approve:disabled,
  .btn-reject:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Completed state styling */
  .confirmation-widget.approved {
    border-color: var(--success-500);
    background: var(--success-50);
  }

  .confirmation-widget.approved .confirmation-icon {
    color: var(--success-600);
  }

  .confirmation-widget.approved .confirmation-result {
    color: var(--success-600);
  }

  .confirmation-widget.rejected {
    border-color: var(--error-500);
    background: var(--error-50);
  }

  .confirmation-widget.rejected .confirmation-icon {
    color: var(--error-600);
  }

  .confirmation-widget.rejected .confirmation-result {
    color: var(--error-600);
  }

  .confirmation-result {
    margin-bottom: 0.75rem;
    font-size: 0.95rem;
    color: var(--text-primary);
    line-height: 1.5;
  }

  .confirmation-status-final {
    padding: 0.5rem;
    border-radius: 4px;
    text-align: center;
    font-weight: 600;
    font-size: 0.9rem;
  }

  .confirmation-status-final.approved {
    background: var(--success-500);
    color: white;
  }

  .confirmation-status-final.rejected {
    background: var(--error-500);
    color: white;
  }
</style>
