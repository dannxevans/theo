<script>
  export let time = null;
</script>

<div class="time-widget">
  {#if time}
    <div class="time">{time.formatted}</div>
    <div class="date">{time.date}</div>
  {:else}
    <div class="time loading">--:--</div>
    <div class="date loading">Loading...</div>
  {/if}
</div>

<style>
  .time-widget {
    text-align: center;
    padding: 0;
  }

  .time {
    font-size: 5.5rem;
    font-weight: 300;
    font-family: 'Aptos Display', 'Aptos', sans-serif;
    background: linear-gradient(135deg, var(--kiosk-accent-cyan, #00ffff), var(--kiosk-accent-purple, #a855f7));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
    text-shadow: 0 0 30px rgba(0, 255, 255, 0.5);
    line-height: 1;
  }

  .date {
    font-size: 1.4rem;
    color: var(--kiosk-text-secondary, #9ca3af);
    font-weight: 400;
    font-family: 'Aptos', sans-serif;
    letter-spacing: 0.08em;
    opacity: 0.9;
  }

  .loading {
    opacity: 0.5;
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 0.3; }
  }

  /* Responsive scaling for small screens */
  @media (max-width: 1024px) {
    .time {
      font-size: 4rem;
    }

    .date {
      font-size: 1.1rem;
    }
  }

  @media (max-width: 768px) {
    .time {
      font-size: 3rem;
    }

    .date {
      font-size: 0.95rem;
    }
  }

  /* Responsive scaling for short screens (vertical constraint) */
  @media (max-height: 700px) {
    .time {
      font-size: 3.5rem;
    }

    .date {
      font-size: 1rem;
    }
  }

  @media (max-height: 600px) {
    .time {
      font-size: 2.5rem;
    }

    .date {
      font-size: 0.85rem;
    }
  }
</style>
