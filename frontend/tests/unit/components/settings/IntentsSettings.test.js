import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import IntentsSettings from '@/components/settings/IntentsSettings.svelte'
import * as api from '@/lib/api.js'

vi.mock('@/lib/api.js', () => ({
  createIntent: vi.fn(),
  updateIntent: vi.fn(),
  deleteIntent: vi.fn()
}))

describe('IntentsSettings Component', () => {
  const mockIntents = [
    {
      id: 'coding',
      name: 'Coding',
      description: 'Code-related tasks',
      keywords: 'code,program,debug',
      priority: 80,
      enabled: true
    },
    {
      id: 'data-analysis',
      name: 'Data Analysis',
      description: 'Data and analytics',
      keywords: 'data,analyze,chart',
      priority: 60,
      enabled: false
    }
  ]

  beforeEach(() => {
    vi.clearAllMocks()

    global.window = {
      ...global.window,
      confirm: vi.fn(() => true)
    }
  })

  it('should render intents list', () => {
    render(IntentsSettings, { props: { intents: mockIntents } })

    expect(screen.getByText('Intents')).toBeInTheDocument()
    expect(screen.getByText('Coding')).toBeInTheDocument()
    expect(screen.getByText('Data Analysis')).toBeInTheDocument()
  })

  it('should display subtitle', () => {
    render(IntentsSettings, { props: { intents: mockIntents } })

    expect(screen.getByText(/Define custom intents to classify and route/i)).toBeInTheDocument()
  })

  it('should show New Intent button', () => {
    render(IntentsSettings, { props: { intents: mockIntents } })

    expect(screen.getByRole('button', { name: /new intent/i })).toBeInTheDocument()
  })

  it('should display intent details', () => {
    render(IntentsSettings, { props: { intents: mockIntents } })

    expect(screen.getByText('(coding)')).toBeInTheDocument()
    expect(screen.getByText('Code-related tasks')).toBeInTheDocument()
    expect(screen.getByText(/code,program,debug/i)).toBeInTheDocument()
    expect(screen.getByText('Priority: 80')).toBeInTheDocument()
  })

  it('should show disabled badge for disabled intents', () => {
    render(IntentsSettings, { props: { intents: mockIntents } })

    const disabledBadges = screen.getAllByText('Disabled')
    expect(disabledBadges.length).toBeGreaterThan(0)
  })

  it('should show intent form when clicking New Intent', async () => {
    const user = userEvent.setup()

    render(IntentsSettings, { props: { intents: mockIntents } })

    await user.click(screen.getByRole('button', { name: /new intent/i }))

    await waitFor(() => {
      expect(screen.getByText('New Intent')).toBeInTheDocument()
      expect(screen.getByLabelText('ID')).toBeInTheDocument()
      expect(screen.getByLabelText('Name')).toBeInTheDocument()
    })
  })

  it('should create new intent', async () => {
    const user = userEvent.setup()

    api.createIntent.mockResolvedValue({
      id: 'test-intent',
      name: 'Test Intent',
      enabled: true
    })

    const { component } = render(IntentsSettings, { props: { intents: mockIntents } })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    await user.click(screen.getByRole('button', { name: /new intent/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('ID')).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('ID'), 'test-intent')
    await user.type(screen.getByLabelText('Name'), 'Test Intent')
    await user.type(screen.getByLabelText('Description'), 'Test description')
    await user.type(screen.getByLabelText(/Keywords/i), 'test,keyword')

    await user.click(screen.getByRole('button', { name: /create intent/i }))

    await waitFor(() => {
      expect(api.createIntent).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'test-intent',
          name: 'Test Intent',
          description: 'Test description',
          keywords: 'test,keyword'
        })
      )
      expect(reloadFired).toHaveBeenCalled()
    })
  })

  it('should edit existing intent', async () => {
    const user = userEvent.setup()

    api.updateIntent.mockResolvedValue({ success: true })

    const { component } = render(IntentsSettings, { props: { intents: mockIntents } })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    const editButtons = screen.getAllByRole('button', { name: /edit/i })
    await user.click(editButtons[0])

    await waitFor(() => {
      expect(screen.getByText('Edit Intent')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Coding')).toBeInTheDocument()
    })

    const nameInput = screen.getByLabelText('Name')
    await user.clear(nameInput)
    await user.type(nameInput, 'Updated Coding')

    await user.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => {
      expect(api.updateIntent).toHaveBeenCalledWith(
        'coding',
        expect.objectContaining({
          name: 'Updated Coding'
        })
      )
      expect(reloadFired).toHaveBeenCalled()
    })
  })

  it('should disable ID field when editing', async () => {
    const user = userEvent.setup()

    render(IntentsSettings, { props: { intents: mockIntents } })

    const editButtons = screen.getAllByRole('button', { name: /edit/i })
    await user.click(editButtons[0])

    await waitFor(() => {
      const idInput = screen.getByLabelText('ID')
      expect(idInput).toBeDisabled()
    })
  })

  it('should delete intent after confirmation', async () => {
    const user = userEvent.setup()

    window.confirm.mockReturnValue(true)
    api.deleteIntent.mockResolvedValue({ success: true })

    const { component } = render(IntentsSettings, { props: { intents: mockIntents } })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteButtons[0])

    await waitFor(() => {
      expect(api.deleteIntent).toHaveBeenCalledWith('coding')
      expect(reloadFired).toHaveBeenCalled()
    })
  })

  it('should not delete intent when cancelled', async () => {
    const user = userEvent.setup()

    window.confirm.mockReturnValue(false)

    render(IntentsSettings, { props: { intents: mockIntents } })

    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteButtons[0])

    expect(api.deleteIntent).not.toHaveBeenCalled()
  })

  it('should toggle intent enabled/disabled', async () => {
    const user = userEvent.setup()

    api.updateIntent.mockResolvedValue({ success: true })

    const { component } = render(IntentsSettings, { props: { intents: mockIntents } })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    const disableButtons = screen.getAllByRole('button', { name: /disable/i })
    await user.click(disableButtons[0])

    await waitFor(() => {
      expect(api.updateIntent).toHaveBeenCalledWith('coding', {
        enabled: false
      })
      expect(reloadFired).toHaveBeenCalled()
    })
  })

  it('should show Enable button for disabled intents', async () => {
    render(IntentsSettings, { props: { intents: mockIntents } })

    const enableButtons = screen.getAllByRole('button', { name: /enable/i })
    expect(enableButtons.length).toBeGreaterThan(0)
  })

  it('should cancel intent form', async () => {
    const user = userEvent.setup()

    render(IntentsSettings, { props: { intents: mockIntents } })

    await user.click(screen.getByRole('button', { name: /new intent/i }))

    await waitFor(() => {
      expect(screen.getByText('New Intent')).toBeInTheDocument()
    })

    const cancelButtons = screen.getAllByRole('button', { name: /cancel/i })
    await user.click(cancelButtons[0])

    await waitFor(() => {
      expect(screen.queryByText('New Intent')).not.toBeInTheDocument()
    })
  })

  it('should set default priority to 50', async () => {
    const user = userEvent.setup()

    render(IntentsSettings, { props: { intents: mockIntents } })

    await user.click(screen.getByRole('button', { name: /new intent/i }))

    await waitFor(() => {
      const priorityInput = screen.getByLabelText('Priority')
      expect(priorityInput).toHaveValue(50)
    })
  })

  it('should validate priority range', () => {
    const user = userEvent.setup()

    render(IntentsSettings, { props: { intents: mockIntents } })

    user.click(screen.getByRole('button', { name: /new intent/i }))

    waitFor(() => {
      const priorityInput = screen.getByLabelText('Priority')
      expect(priorityInput).toHaveAttribute('min', '0')
      expect(priorityInput).toHaveAttribute('max', '100')
    })
  })

  it('should have Enabled checkbox checked by default', async () => {
    const user = userEvent.setup()

    render(IntentsSettings, { props: { intents: mockIntents } })

    await user.click(screen.getByRole('button', { name: /new intent/i }))

    await waitFor(() => {
      const checkbox = screen.getByRole('checkbox', { name: /enabled/i })
      expect(checkbox).toBeChecked()
    })
  })

  it('should display empty state for fallback intents', () => {
    const intentWithoutKeywords = [
      {
        id: 'fallback',
        name: 'Fallback',
        description: 'Fallback intent',
        keywords: '',
        priority: 10,
        enabled: true
      }
    ]

    render(IntentsSettings, { props: { intents: intentWithoutKeywords } })

    expect(screen.getByText(/No keywords \(fallback intent\)/i)).toBeInTheDocument()
  })

  it('should show alert on create error', async () => {
    const user = userEvent.setup()

    global.window.alert = vi.fn()
    api.createIntent.mockRejectedValue(new Error('Creation failed'))

    render(IntentsSettings, { props: { intents: mockIntents } })

    await user.click(screen.getByRole('button', { name: /new intent/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('ID')).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('ID'), 'test')
    await user.type(screen.getByLabelText('Name'), 'Test')

    await user.click(screen.getByRole('button', { name: /create intent/i }))

    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith('Failed to save intent: Creation failed')
    })
  })

  it('should show alert on delete error', async () => {
    const user = userEvent.setup()

    global.window.alert = vi.fn()
    window.confirm.mockReturnValue(true)
    api.deleteIntent.mockRejectedValue(new Error('Delete failed'))

    render(IntentsSettings, { props: { intents: mockIntents } })

    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteButtons[0])

    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith('Failed to delete intent: Delete failed')
    })
  })

  it('should show alert on toggle error', async () => {
    const user = userEvent.setup()

    global.window.alert = vi.fn()
    api.updateIntent.mockRejectedValue(new Error('Toggle failed'))

    render(IntentsSettings, { props: { intents: mockIntents } })

    const disableButtons = screen.getAllByRole('button', { name: /disable/i })
    await user.click(disableButtons[0])

    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith('Failed to toggle intent: Toggle failed')
    })
  })

  it('should have proper field labels and placeholders', async () => {
    const user = userEvent.setup()

    render(IntentsSettings, { props: { intents: mockIntents } })

    await user.click(screen.getByRole('button', { name: /new intent/i }))

    await waitFor(() => {
      expect(screen.getByPlaceholderText('e.g., data-analysis')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('e.g., Data Analysis')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('What is this intent used for?')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('e.g., analyze,data,chart,graph,statistics')).toBeInTheDocument()
    })
  })

  it('should show helper text for fields', async () => {
    const user = userEvent.setup()

    render(IntentsSettings, { props: { intents: mockIntents } })

    await user.click(screen.getByRole('button', { name: /new intent/i }))

    await waitFor(() => {
      expect(screen.getByText(/Unique identifier \(lowercase, hyphens allowed\)/i)).toBeInTheDocument()
      expect(screen.getByText(/Messages matching any keyword will use this intent/i)).toBeInTheDocument()
      expect(screen.getByText(/Higher priority intents are checked first/i)).toBeInTheDocument()
    })
  })

  it('should handle empty intents list', () => {
    render(IntentsSettings, { props: { intents: [] } })

    expect(screen.getByRole('button', { name: /new intent/i })).toBeInTheDocument()
    expect(screen.queryByText('Coding')).not.toBeInTheDocument()
  })
})
