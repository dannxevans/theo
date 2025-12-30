import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import AIProvidersSettings from '@/components/settings/AIProvidersSettings.svelte'
import * as api from '@/lib/api.js'

vi.mock('@/lib/api.js', () => ({
  upsertProvider: vi.fn(),
  deleteProvider: vi.fn()
}))

describe('AIProvidersSettings Component', () => {
  const mockProviders = [
    {
      id: 'anthropic',
      name: 'Anthropic Claude',
      type: 'anthropic',
      model: 'claude-3-5-sonnet',
      enabled: true
    },
    {
      id: 'openai',
      name: 'OpenAI GPT-4',
      type: 'openai',
      model: 'gpt-4',
      enabled: false
    }
  ]

  const mockHealth = {
    anthropic: {
      health_status: 'healthy',
      circuit_breaker_open: false,
      total_requests: 100,
      failure_rate: 2,
      avg_latency_ms: 250
    },
    openai: {
      health_status: 'degraded',
      circuit_breaker_open: false,
      total_requests: 50,
      failure_rate: 15,
      avg_latency_ms: 800
    }
  }

  beforeEach(() => {
    vi.clearAllMocks()

    global.window = {
      ...global.window,
      confirm: vi.fn(() => true),
      alert: vi.fn()
    }
  })

  afterEach(() => {
    cleanup()
  })

  it('should render providers settings', () => {
    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    expect(screen.getByText('Providers')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add provider/i })).toBeInTheDocument()
  })

  it('should display provider list', () => {
    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    expect(screen.getByText('Anthropic Claude')).toBeInTheDocument()
    expect(screen.getByText('OpenAI GPT-4')).toBeInTheDocument()
  })

  it('should show health status badges', () => {
    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    expect(screen.getByText('Healthy')).toBeInTheDocument()
    expect(screen.getByText('Degraded')).toBeInTheDocument()
  })

  it('should display health statistics', () => {
    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    expect(screen.getByText('Requests: 100')).toBeInTheDocument()
    expect(screen.getByText('Failures: 2%')).toBeInTheDocument()
    expect(screen.getByText('Latency: 250ms')).toBeInTheDocument()
  })

  it('should show add provider form when clicking Add Provider', async () => {
    const user = userEvent.setup()

    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    await user.click(screen.getByRole('button', { name: /add provider/i }))

    await waitFor(() => {
      expect(screen.getByText('New Provider')).toBeInTheDocument()
      expect(screen.getByLabelText('ID')).toBeInTheDocument()
      expect(screen.getByLabelText('Name')).toBeInTheDocument()
    })
  })

  it('should create new provider', async () => {
    const user = userEvent.setup()

    api.upsertProvider.mockResolvedValue({
      id: 'test-provider',
      name: 'Test Provider'
    })

    const { component } = render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    await user.click(screen.getByRole('button', { name: /add provider/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('ID')).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('ID'), 'test-provider')
    await user.type(screen.getByLabelText('Name'), 'Test Provider')

    const typeSelect = screen.getByLabelText('Type')
    await user.selectOptions(typeSelect, 'anthropic')

    await user.type(screen.getByLabelText('Model'), 'claude-3-opus')

    const saveButtons = screen.getAllByRole('button', { name: /save/i })
    await user.click(saveButtons[0])

    await waitFor(() => {
      expect(api.upsertProvider).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'test-provider',
          name: 'Test Provider',
          type: 'anthropic',
          model: 'claude-3-opus'
        })
      )
      expect(reloadFired).toHaveBeenCalled()
    })
  })

  it('should validate required fields', async () => {
    const user = userEvent.setup()

    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    await user.click(screen.getByRole('button', { name: /add provider/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('ID')).toBeInTheDocument()
    })

    const saveButtons = screen.getAllByRole('button', { name: /save/i })
    await user.click(saveButtons[0])

    await waitFor(() => {
      expect(screen.getByText(/id, name and type are required/i)).toBeInTheDocument()
    })

    expect(api.upsertProvider).not.toHaveBeenCalled()
  })

  it('should validate model required for Anthropic', async () => {
    const user = userEvent.setup()

    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    await user.click(screen.getByRole('button', { name: /add provider/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('ID')).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('ID'), 'test')
    await user.type(screen.getByLabelText('Name'), 'Test')

    const typeSelect = screen.getByLabelText('Type')
    await user.selectOptions(typeSelect, 'anthropic')

    const saveButtons = screen.getAllByRole('button', { name: /save/i })
    await user.click(saveButtons[0])

    await waitFor(() => {
      expect(screen.getByText(/Model is required for Anthropic providers/i)).toBeInTheDocument()
    })
  })

  it('should edit existing provider', async () => {
    const user = userEvent.setup()

    api.upsertProvider.mockResolvedValue({ success: true })

    const { component } = render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    const editButtons = screen.getAllByRole('button', { name: /edit/i })
    await user.click(editButtons[0])

    await waitFor(() => {
      expect(screen.getByText('Edit Provider')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Anthropic Claude')).toBeInTheDocument()
    })

    const nameInput = screen.getByLabelText('Name')
    await user.clear(nameInput)
    await user.type(nameInput, 'Updated Anthropic')

    const updateButtons = screen.getAllByRole('button', { name: /update/i })
    await user.click(updateButtons[0])

    await waitFor(() => {
      expect(api.upsertProvider).toHaveBeenCalled()
      expect(reloadFired).toHaveBeenCalled()
    })
  })

  it('should disable ID field when editing', async () => {
    const user = userEvent.setup()

    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    const editButtons = screen.getAllByRole('button', { name: /edit/i })
    await user.click(editButtons[0])

    await waitFor(() => {
      const idInput = screen.getByLabelText('ID')
      expect(idInput).toBeDisabled()
    })
  })

  it('should not prefill API key when editing', async () => {
    const user = userEvent.setup()

    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    const editButtons = screen.getAllByRole('button', { name: /edit/i })
    await user.click(editButtons[0])

    await waitFor(() => {
      const apiKeyInput = screen.getByLabelText(/API Key/i)
      expect(apiKeyInput).toHaveValue('')
    })
  })

  it('should delete provider after confirmation', async () => {
    const user = userEvent.setup()

    window.confirm.mockReturnValue(true)
    api.deleteProvider.mockResolvedValue({ success: true })

    const { component } = render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteButtons[0])

    await waitFor(() => {
      expect(api.deleteProvider).toHaveBeenCalledWith('anthropic')
      expect(reloadFired).toHaveBeenCalled()
    })
  })

  it('should not delete provider when cancelled', async () => {
    const user = userEvent.setup()

    window.confirm.mockReturnValue(false)

    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteButtons[0])

    expect(api.deleteProvider).not.toHaveBeenCalled()
  })

  it('should show alert on delete error', async () => {
    const user = userEvent.setup()

    window.confirm.mockReturnValue(true)
    window.alert.mockImplementation(() => {})
    api.deleteProvider.mockRejectedValue(new Error('Delete failed'))

    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteButtons[0])

    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith('Failed to delete provider: Delete failed')
    })
  })

  it('should have provider type options', async () => {
    const user = userEvent.setup()

    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    await user.click(screen.getByRole('button', { name: /add provider/i }))

    await waitFor(() => {
      const typeSelect = screen.getByLabelText('Type')
      const options = Array.from(typeSelect.querySelectorAll('option'))
      const typeValues = options.map(opt => opt.value)

      expect(typeValues).toContain('anthropic')
      expect(typeValues).toContain('openai')
      expect(typeValues).toContain('openrouter')
      expect(typeValues).toContain('mock')
    })
  })

  it('should cancel provider form', async () => {
    const user = userEvent.setup()

    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    await user.click(screen.getByRole('button', { name: /add provider/i }))

    await waitFor(() => {
      expect(screen.getByText('New Provider')).toBeInTheDocument()
    })

    const cancelButtons = screen.getAllByRole('button', { name: /cancel/i })
    await user.click(cancelButtons[0])

    await waitFor(() => {
      expect(screen.queryByText('New Provider')).not.toBeInTheDocument()
    })
  })

  it('should show empty state when no providers', () => {
    render(AIProvidersSettings, {
      props: {
        providersList: [],
        healthSummary: {}
      }
    })

    expect(screen.getByText(/No providers configured yet/i)).toBeInTheDocument()
    expect(screen.getByText(/Add a provider to get started/i)).toBeInTheDocument()
  })

  it('should display provider status', () => {
    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    expect(screen.getByText('Status: Enabled')).toBeInTheDocument()
    expect(screen.getByText('Status: Disabled')).toBeInTheDocument()
  })

  it('should show Unknown status for providers without health data', () => {
    const providersWithoutHealth = [
      {
        id: 'new-provider',
        name: 'New Provider',
        type: 'openai',
        enabled: true
      }
    ]

    render(AIProvidersSettings, {
      props: {
        providersList: providersWithoutHealth,
        healthSummary: {}
      }
    })

    expect(screen.getByText('Unknown')).toBeInTheDocument()
  })

  it('should show circuit breaker status', () => {
    const healthWithCircuitBreaker = {
      test: {
        health_status: 'healthy',
        circuit_breaker_open: true,
        total_requests: 10,
        failure_rate: 50,
        avg_latency_ms: 1000
      }
    }

    const providers = [
      {
        id: 'test',
        name: 'Test Provider',
        type: 'mock',
        enabled: true
      }
    ]

    render(AIProvidersSettings, {
      props: {
        providersList: providers,
        healthSummary: healthWithCircuitBreaker
      }
    })

    expect(screen.getByText('Circuit Open')).toBeInTheDocument()
  })

  it('should handle empty health stats gracefully', () => {
    const providersWithZeroRequests = [
      {
        id: 'unused',
        name: 'Unused Provider',
        type: 'mock',
        enabled: true
      }
    ]

    const healthWithZeroRequests = {
      unused: {
        health_status: 'unknown',
        circuit_breaker_open: false,
        total_requests: 0,
        failure_rate: 0,
        avg_latency_ms: 0
      }
    }

    render(AIProvidersSettings, {
      props: {
        providersList: providersWithZeroRequests,
        healthSummary: healthWithZeroRequests
      }
    })

    expect(screen.queryByText(/Requests:/)).not.toBeInTheDocument()
  })

  it('should show enabled checkbox checked by default', async () => {
    const user = userEvent.setup()

    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    await user.click(screen.getByRole('button', { name: /add provider/i }))

    await waitFor(() => {
      const enabledCheckbox = screen.getByRole('checkbox', { name: /enabled/i })
      expect(enabledCheckbox).toBeChecked()
    })
  })

  it('should have proper field placeholders and labels', async () => {
    const user = userEvent.setup()

    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    await user.click(screen.getByRole('button', { name: /add provider/i }))

    await waitFor(() => {
      expect(screen.getByPlaceholderText('e.g., anthropic-claude')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('e.g., Anthropic Claude')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('e.g., claude-3-5-sonnet-20241022')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('Custom API endpoint')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('sk-...')).toBeInTheDocument()
    })
  })

  it('should display subtitle', () => {
    render(AIProvidersSettings, {
      props: {
        providersList: mockProviders,
        healthSummary: mockHealth
      }
    })

    expect(screen.getByText(/Manage AI provider configurations and health status/i)).toBeInTheDocument()
  })
})
