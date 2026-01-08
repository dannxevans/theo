<script>
    export let password = '';

    $: requirements = [
        { label: 'At least 8 characters', met: password.length >= 8 },
        { label: 'One uppercase letter', met: /[A-Z]/.test(password) },
        { label: 'One lowercase letter', met: /[a-z]/.test(password) },
        { label: 'One number', met: /\d/.test(password) },
        { label: 'One special character (!@#$...)', met: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password) }
    ];

    $: metCount = requirements.filter(r => r.met).length;
    $: strength = metCount <= 2 ? 'weak' : metCount <= 4 ? 'medium' : 'strong';
    $: strengthColor = strength === 'weak' ? '#ef4444' : strength === 'medium' ? '#f59e0b' : '#10b981';
    $: strengthLabel = strength === 'weak' ? 'Weak' : strength === 'medium' ? 'Medium' : 'Strong';
</script>

<div class="password-strength-meter">
    <div class="strength-header">
        <span class="strength-label" style="color: {strengthColor}">{strengthLabel}</span>
        <div class="strength-bar-container">
            <div class="strength-bar" style="width: {(metCount / 5) * 100}%; background-color: {strengthColor}"></div>
        </div>
    </div>

    <div class="requirements">
        {#each requirements as req}
            <div class="requirement" class:met={req.met}>
                <span class="icon">{req.met ? '✓' : '○'}</span>
                <span class="label">{req.label}</span>
            </div>
        {/each}
    </div>
</div>

<style>
    .password-strength-meter {
        margin-top: 0.75rem;
        padding: 0.75rem;
        background-color: #f9fafb;
        border-radius: 6px;
        border: 1px solid #e5e7eb;
    }

    .strength-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.75rem;
    }

    .strength-label {
        font-size: 0.875rem;
        font-weight: 600;
        min-width: 4rem;
    }

    .strength-bar-container {
        flex: 1;
        height: 6px;
        background-color: #e5e7eb;
        border-radius: 3px;
        overflow: hidden;
    }

    .strength-bar {
        height: 100%;
        transition: width 0.3s ease, background-color 0.3s ease;
        border-radius: 3px;
    }

    .requirements {
        display: flex;
        flex-direction: column;
        gap: 0.375rem;
        font-size: 0.8125rem;
    }

    .requirement {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: #9ca3af;
        transition: color 0.2s ease;
    }

    .requirement.met {
        color: #10b981;
        font-weight: 500;
    }

    .icon {
        font-weight: bold;
        min-width: 1rem;
        font-size: 0.875rem;
    }

    .label {
        line-height: 1.4;
    }
</style>
