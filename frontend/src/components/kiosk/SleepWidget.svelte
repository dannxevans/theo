<script>
  export let sleep = null;

  function getQualityLabel(quality) {
    if (quality >= 85) return "Excellent";
    if (quality >= 70) return "Good";
    if (quality >= 50) return "Fair";
    return "Poor";
  }

  function getQualityColor(quality) {
    if (quality >= 85) return "#10b981"; // Green
    if (quality >= 70) return "#3b82f6"; // Blue
    if (quality >= 50) return "#f59e0b"; // Amber
    return "#ef4444"; // Red
  }
</script>

<div class="sleep-widget widget-card">
  <div class="widget-header">
    <svg class="widget-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
    </svg>
    <span class="widget-title">Sleep</span>
  </div>
  {#if sleep}
    <div class="widget-content">
      <div class="main-stat">{sleep.hours}<span class="unit">hrs</span></div>
      <div class="quality-label" style="color: {getQualityColor(sleep.quality)}">
        {getQualityLabel(sleep.quality)}
      </div>
    </div>
  {:else}
    <div class="widget-content not-connected">
      <div class="not-connected-text">Not Connected</div>
    </div>
  {/if}
</div>

<style>
  .sleep-widget {
    min-height: 120px;
  }

  .main-stat {
    font-size: 3.5rem;
    font-weight: 300;
    font-family: 'Aptos Display', 'Aptos', sans-serif;
    color: var(--kiosk-accent-cyan, #00ffff);
    line-height: 1;
    margin-bottom: 0.5rem;
  }

  .unit {
    font-size: 1.5rem;
    opacity: 0.6;
    margin-left: 0.25rem;
  }

  .quality-label {
    font-size: 1.1rem;
    font-weight: 500;
  }

  /* Responsive scaling */
  @media (max-width: 1024px) {
    .sleep-widget {
      min-height: 100px;
    }

    .main-stat {
      font-size: 2.75rem;
    }

    .unit {
      font-size: 1.2rem;
    }

    .quality-label {
      font-size: 0.95rem;
    }
  }

  @media (max-width: 768px) {
    .sleep-widget {
      min-height: 80px;
    }

    .main-stat {
      font-size: 2.25rem;
    }

    .unit {
      font-size: 1rem;
    }

    .quality-label {
      font-size: 0.85rem;
    }
  }
</style>
