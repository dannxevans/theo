import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import HealthMonitorSettings from '@/components/settings/HealthMonitorSettings.svelte'
import * as api from '@/lib/api.js'

vi.mock('@/lib/api.js', () => ({
  setDebugFlag: vi.fn()
}))

describe('HealthMonitorSettings Component', () => {
  const mockHealthData = {
    ai_providers: [
      {
        id: 'anthropic',
        name: 'Anthropic Claude',
        type: 'anthropic',
        model: 'claude-3-5-sonnet',
        enabled: true,
        health_status: 'healthy',
        circuit_breaker_open: false,
        total_requests: 150,
        failed_requests: 3,
        success_rate: 98,
        avg_latency_ms: 250,
        last_success_at: new Date(Date.now() - 3600000).toISOString(),
        last_failure_at: new Date(Date.now() - 86400000).toISOString()
      },
      {
        id: 'openai',
        name: 'OpenAI GPT-4',
        type: 'openai',
        model: 'gpt-4',
        enabled: false,
        health_status: 'degraded',
        circuit_breaker_open: false,
        total_requests: 50,
        failed_requests: 10,
        success_rate: 80,
        avg_latency_ms: 800
      }
    ],
    m365_integration: {
      connected: true,
      token_valid: true,
      account: 'user@company.com',
      hours_until_expiry: 48,
      last_refreshed_at: new Date(Date.now() - 7200000).toISOString(),
      scopes: ['Calendars.ReadWrite', 'Mail.Send']
    },
    service_providers: [
      {
        id: 'sp1',
        name: 'Barber Shop',
        category: 'Health & Wellness',
        provider_type: 'manual',
        is_enabled: true,
        booking_url: 'https://example.com/book',
        last_synced_at: new Date().toISOString()
      }
    ]
  }

  beforeEach(() => {
    vi.clearAllMocks()

    global.localStorage = {
      getItem: vi.fn(),
      setItem: vi.fn()
    }

    global.window = {
      ...global.window,
      dispatchEvent: vi.fn(),
      fetch: vi.fn()
    }
  })

  it('should render health monitor settings', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText('System Health Monitor')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /refresh all/i })).toBeInTheDocument()
  })

  it('should display AI provider health cards', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText('Anthropic Claude')).toBeInTheDocument()
    expect(screen.getByText('OpenAI GPT-4')).toBeInTheDocument()
  })

  it('should show health status badges', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/Healthy/i)).toBeInTheDocument()
    expect(screen.getByText(/Degraded/i)).toBeInTheDocument()
  })

  it('should display provider metrics', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/150 total, 3 failed/i)).toBeInTheDocument()
    expect(screen.getByText('Success Rate: 98%')).toBeInTheDocument()
  })

  it('should show latency with color coding', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText('250ms')).toBeInTheDocument()
    expect(screen.getByText('800ms')).toBeInTheDocument()
  })

  it('should display M365 integration status', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/Microsoft 365/i)).toBeInTheDocument()
    expect(screen.getByText('user@company.com')).toBeInTheDocument()
    expect(screen.getByText(/in 48 hours/i)).toBeInTheDocument()
  })

  it('should show M365 not configured when disconnected', () => {
    const disconnectedData = {
      ...mockHealthData,
      m365_integration: { connected: false }
    }

    render(HealthMonitorSettings, {
      props: {
        healthData: disconnectedData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/Not Configured/i)).toBeInTheDocument()
    expect(screen.getByText(/Microsoft 365 account not connected/i)).toBeInTheDocument()
  })

  it('should display M365 capabilities', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/Calendar Access/i)).toBeInTheDocument()
    expect(screen.getByText(/Email Access/i)).toBeInTheDocument()
  })

  it('should test M365 connection', async () => {
    const user = userEvent.setup()

    localStorage.getItem.mockReturnValue('mock-token')
    global.window.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ healthy: true, response_time_ms: 150 })
    })

    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    const testButton = screen.getByRole('button', { name: /test connection/i })
    await user.click(testButton)

    await waitFor(() => {
      expect(screen.getByText(/Connected to Microsoft Graph API/i)).toBeInTheDocument()
      expect(screen.getByText(/150ms/i)).toBeInTheDocument()
    })
  })

  it('should display service providers', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText('Service Providers')).toBeInTheDocument()
    expect(screen.getByText('Barber Shop')).toBeInTheDocument()
    expect(screen.getByText('Health & Wellness')).toBeInTheDocument()
  })

  it('should show service provider booking link', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    const bookingLink = screen.getByText(/Open Booking URL/i)
    expect(bookingLink).toHaveAttribute('href', 'https://example.com/book')
    expect(bookingLink).toHaveAttribute('target', '_blank')
  })

  it('should toggle debug mode', async () => {
    const user = userEvent.setup()

    api.setDebugFlag.mockResolvedValue({ success: true })

    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    const debugCheckbox = screen.getByRole('checkbox', { name: /debug logs/i })
    await user.click(debugCheckbox)

    await waitFor(() => {
      expect(api.setDebugFlag).toHaveBeenCalledWith(true)
    })
  })

  it('should toggle advanced mode', async () => {
    const user = userEvent.setup()

    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    const advancedCheckbox = screen.getByRole('checkbox', { name: /advanced mode/i })
    await user.click(advancedCheckbox)

    expect(localStorage.setItem).toHaveBeenCalledWith('theo.advancedMode', 'true')
    expect(window.dispatchEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'advancedModeChanged'
      })
    )
  })

  it('should emit reload event when clicking refresh', async () => {
    const user = userEvent.setup()

    const { component } = render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    await user.click(screen.getByRole('button', { name: /refresh all/i }))

    expect(reloadFired).toHaveBeenCalled()
  })

  it('should show inactive badge for disabled providers', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/Inactive/i)).toBeInTheDocument()
  })

  it('should display circuit breaker status', () => {
    const dataWithCircuitBreaker = {
      ...mockHealthData,
      ai_providers: [
        {
          ...mockHealthData.ai_providers[0],
          circuit_breaker_open: true
        }
      ]
    }

    render(HealthMonitorSettings, {
      props: {
        healthData: dataWithCircuitBreaker,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/Circuit Breaker/i)).toBeInTheDocument()
  })

  it('should show empty state for no AI providers', () => {
    const emptyData = {
      ...mockHealthData,
      ai_providers: []
    }

    render(HealthMonitorSettings, {
      props: {
        healthData: emptyData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/No AI providers configured yet/i)).toBeInTheDocument()
  })

  it('should show empty state for no service providers', () => {
    const emptyData = {
      ...mockHealthData,
      service_providers: []
    }

    render(HealthMonitorSettings, {
      props: {
        healthData: emptyData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/No service providers configured yet/i)).toBeInTheDocument()
  })

  it('should format relative time correctly', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/hour/i)).toBeInTheDocument()
  })

  it('should show warning for expiring token', () => {
    const expiringData = {
      ...mockHealthData,
      m365_integration: {
        ...mockHealthData.m365_integration,
        hours_until_expiry: 12
      }
    }

    render(HealthMonitorSettings, {
      props: {
        healthData: expiringData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/Token Expiring Soon/i)).toBeInTheDocument()
  })

  it('should show error for invalid token', () => {
    const invalidData = {
      ...mockHealthData,
      m365_integration: {
        ...mockHealthData.m365_integration,
        token_valid: false
      }
    }

    render(HealthMonitorSettings, {
      props: {
        healthData: invalidData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/Disconnected/i)).toBeInTheDocument()
    expect(screen.getByText(/Invalid\/Expired/i)).toBeInTheDocument()
  })

  it('should show no requests message for unused providers', () => {
    const unusedProviderData = {
      ...mockHealthData,
      ai_providers: [
        {
          id: 'unused',
          name: 'Unused Provider',
          type: 'mock',
          enabled: true,
          health_status: 'unknown',
          circuit_breaker_open: false,
          total_requests: 0
        }
      ]
    }

    render(HealthMonitorSettings, {
      props: {
        healthData: unusedProviderData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/No requests yet/i)).toBeInTheDocument()
  })

  it('should handle M365 test connection error', async () => {
    const user = userEvent.setup()

    localStorage.getItem.mockReturnValue('mock-token')
    global.window.fetch.mockRejectedValueOnce(new Error('Connection failed'))

    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    const testButton = screen.getByRole('button', { name: /test connection/i })
    await user.click(testButton)

    await waitFor(() => {
      expect(screen.getByText(/Connection Failed/i)).toBeInTheDocument()
    })
  })

  it('should disable test button while testing', async () => {
    const user = userEvent.setup()

    localStorage.getItem.mockReturnValue('mock-token')

    let resolveTest
    const testPromise = new Promise((resolve) => {
      resolveTest = resolve
    })

    global.window.fetch.mockReturnValue(testPromise)

    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    const testButton = screen.getByRole('button', { name: /test connection/i })
    await user.click(testButton)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /testing/i })).toBeDisabled()
    })

    resolveTest({
      ok: true,
      json: async () => ({ healthy: true, response_time_ms: 100 })
    })
  })

  it('should display debug settings section', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText('Debug Settings')).toBeInTheDocument()
    expect(screen.getByText(/Enable detailed logging/i)).toBeInTheDocument()
    expect(screen.getByText(/Shows Export and Fork features/i)).toBeInTheDocument()
  })

  it('should have debug checkbox checked when enabled', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: true,
        advancedMode: false
      }
    })

    const debugCheckbox = screen.getByRole('checkbox', { name: /debug logs/i })
    expect(debugCheckbox).toBeChecked()
  })

  it('should have advanced mode checkbox checked when enabled', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: true
      }
    })

    const advancedCheckbox = screen.getByRole('checkbox', { name: /advanced mode/i })
    expect(advancedCheckbox).toBeChecked()
  })

  it('should disable debug checkbox while saving', async () => {
    const user = userEvent.setup()

    let resolveSave
    const savePromise = new Promise((resolve) => {
      resolveSave = resolve
    })

    api.setDebugFlag.mockReturnValue(savePromise)

    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    const debugCheckbox = screen.getByRole('checkbox', { name: /debug logs/i })
    await user.click(debugCheckbox)

    await waitFor(() => {
      expect(debugCheckbox).toBeDisabled()
    })

    resolveSave({ success: true })
  })

  it('should display subtitle', () => {
    render(HealthMonitorSettings, {
      props: {
        healthData: mockHealthData,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/Monitor AI provider health, performance metrics/i)).toBeInTheDocument()
  })

  it('should show last error for M365', () => {
    const dataWithError = {
      ...mockHealthData,
      m365_integration: {
        ...mockHealthData.m365_integration,
        last_error: 'Token refresh failed'
      }
    }

    render(HealthMonitorSettings, {
      props: {
        healthData: dataWithError,
        debugEnabled: false,
        advancedMode: false
      }
    })

    expect(screen.getByText(/Token refresh failed/i)).toBeInTheDocument()
  })
})
