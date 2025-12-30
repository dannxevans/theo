import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import MemorySettings from '@/components/settings/MemorySettings.svelte'
import * as api from '@/lib/api.js'

vi.mock('@/lib/api.js', () => ({
  createMemory: vi.fn(),
  deleteMemory: vi.fn(),
  pinMemory: vi.fn()
}))

describe('MemorySettings Component', () => {
  const mockMemories = [
    {
      id: 1,
      type: 'fact',
      key: 'project',
      value: 'Atlas',
      pinned: true,
      relevance_score: 0.95,
      access_count: 15,
      created_at: new Date('2024-01-01').toISOString(),
      last_accessed_at: new Date('2024-01-10').toISOString()
    },
    {
      id: 2,
      type: 'preference',
      key: 'language',
      value: 'TypeScript',
      pinned: false,
      relevance_score: 0.87,
      access_count: 8,
      created_at: new Date('2024-01-05').toISOString(),
      last_accessed_at: new Date('2024-01-08').toISOString()
    }
  ]

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

  it('should render memory settings', () => {
    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    expect(screen.getByText('Memory')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add memory/i })).toBeInTheDocument()
  })

  it('should display filter buttons', () => {
    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Facts' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Preferences' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Goals' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Context' })).toBeInTheDocument()
  })

  it('should display memory list', () => {
    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    expect(screen.getByText(/project:/i)).toBeInTheDocument()
    expect(screen.getByText(/Atlas/i)).toBeInTheDocument()
    expect(screen.getByText(/language:/i)).toBeInTheDocument()
    expect(screen.getByText(/TypeScript/i)).toBeInTheDocument()
  })

  it('should show pinned badge for pinned memories', () => {
    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    expect(screen.getByText(/Pinned/i)).toBeInTheDocument()
  })

  it('should display memory metadata', () => {
    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    expect(screen.getByText('Score: 0.95')).toBeInTheDocument()
    expect(screen.getByText('Used 15 times')).toBeInTheDocument()
  })

  it('should show add memory form when clicking Add Memory', async () => {
    const user = userEvent.setup()

    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    await user.click(screen.getByRole('button', { name: /add memory/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('Type')).toBeInTheDocument()
      expect(screen.getByLabelText('Key')).toBeInTheDocument()
      expect(screen.getByLabelText('Value')).toBeInTheDocument()
    })
  })

  it('should create new memory', async () => {
    const user = userEvent.setup()

    api.createMemory.mockResolvedValue({
      id: 3,
      type: 'fact',
      key: 'company',
      value: 'Acme Corp'
    })

    const { component } = render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    await user.click(screen.getByRole('button', { name: /add memory/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('Key')).toBeInTheDocument()
    })

    const typeSelect = screen.getByLabelText('Type')
    await user.selectOptions(typeSelect, 'fact')

    await user.type(screen.getByLabelText('Key'), 'company')
    await user.type(screen.getByLabelText('Value'), 'Acme Corp')

    const saveButtons = screen.getAllByRole('button', { name: /save/i })
    await user.click(saveButtons[0])

    await waitFor(() => {
      expect(api.createMemory).toHaveBeenCalledWith({
        type: 'fact',
        key: 'company',
        value: 'Acme Corp',
        pinned: false
      })
      expect(reloadFired).toHaveBeenCalled()
    })
  })

  it('should validate required fields', async () => {
    const user = userEvent.setup()

    window.alert.mockImplementation(() => {})

    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    await user.click(screen.getByRole('button', { name: /add memory/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('Key')).toBeInTheDocument()
    })

    const saveButtons = screen.getAllByRole('button', { name: /save/i })
    await user.click(saveButtons[0])

    expect(window.alert).toHaveBeenCalledWith('Key and value are required')
    expect(api.createMemory).not.toHaveBeenCalled()
  })

  it('should delete memory after confirmation', async () => {
    const user = userEvent.setup()

    window.confirm.mockReturnValue(true)
    api.deleteMemory.mockResolvedValue({ success: true })

    const { component } = render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteButtons[0])

    await waitFor(() => {
      expect(api.deleteMemory).toHaveBeenCalledWith(1)
      expect(reloadFired).toHaveBeenCalled()
    })
  })

  it('should not delete memory when cancelled', async () => {
    const user = userEvent.setup()

    window.confirm.mockReturnValue(false)

    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteButtons[0])

    expect(api.deleteMemory).not.toHaveBeenCalled()
  })

  it('should toggle pin status', async () => {
    const user = userEvent.setup()

    api.pinMemory.mockResolvedValue({ success: true })

    const { component } = render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    const unpinButton = screen.getByRole('button', { name: 'Unpin' })
    await user.click(unpinButton)

    await waitFor(() => {
      expect(api.pinMemory).toHaveBeenCalledWith(1, false)
      expect(reloadFired).toHaveBeenCalled()
    })
  })

  it('should pin unpinned memory', async () => {
    const user = userEvent.setup()

    api.pinMemory.mockResolvedValue({ success: true })

    const { component } = render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    const reloadFired = vi.fn()
    component.$on('reload', reloadFired)

    const pinButton = screen.getByRole('button', { name: 'Pin' })
    await user.click(pinButton)

    await waitFor(() => {
      expect(api.pinMemory).toHaveBeenCalledWith(2, true)
      expect(reloadFired).toHaveBeenCalled()
    })
  })

  it('should have memory type options', async () => {
    const user = userEvent.setup()

    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    await user.click(screen.getByRole('button', { name: /add memory/i }))

    await waitFor(() => {
      const typeSelect = screen.getByLabelText('Type')
      const options = Array.from(typeSelect.querySelectorAll('option'))
      const typeNames = options.map(opt => opt.value)

      expect(typeNames).toContain('fact')
      expect(typeNames).toContain('preference')
      expect(typeNames).toContain('goal')
      expect(typeNames).toContain('context')
    })
  })

  it('should allow pinning new memory', async () => {
    const user = userEvent.setup()

    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    await user.click(screen.getByRole('button', { name: /add memory/i }))

    await waitFor(() => {
      const pinCheckbox = screen.getByRole('checkbox', { name: /pin this memory/i })
      expect(pinCheckbox).toBeInTheDocument()
      expect(pinCheckbox).not.toBeChecked()
    })
  })

  it('should cancel adding memory', async () => {
    const user = userEvent.setup()

    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    await user.click(screen.getByRole('button', { name: /add memory/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('Key')).toBeInTheDocument()
    })

    const cancelButtons = screen.getAllByRole('button', { name: /cancel/i })
    await user.click(cancelButtons[1]) // Second cancel button (first is filter button text)

    await waitFor(() => {
      expect(screen.queryByLabelText('Key')).not.toBeInTheDocument()
    })
  })

  it('should show loading state', () => {
    render(MemorySettings, {
      props: {
        memories: [],
        loadingMemories: true,
        filterType: 'all'
      }
    })

    expect(screen.getByText(/Loading memories/i)).toBeInTheDocument()
  })

  it('should show empty state when no memories', () => {
    render(MemorySettings, {
      props: {
        memories: [],
        loadingMemories: false,
        filterType: 'all'
      }
    })

    expect(screen.getByText(/No memories stored yet/i)).toBeInTheDocument()
    expect(screen.getByText(/Use the form above to add a memory/i)).toBeInTheDocument()
  })

  it('should format relative dates correctly', () => {
    const recentMemory = [
      {
        id: 1,
        type: 'fact',
        key: 'test',
        value: 'value',
        pinned: false,
        relevance_score: 0.9,
        access_count: 1,
        created_at: new Date(Date.now() - 86400000).toISOString(), // Yesterday
        last_accessed_at: new Date().toISOString() // Today
      }
    ]

    render(MemorySettings, {
      props: {
        memories: recentMemory,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    expect(screen.getByText(/day/i)).toBeInTheDocument()
  })

  it('should handle create errors', async () => {
    const user = userEvent.setup()

    window.alert.mockImplementation(() => {})
    api.createMemory.mockRejectedValue(new Error('Creation failed'))

    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    await user.click(screen.getByRole('button', { name: /add memory/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('Key')).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Key'), 'test')
    await user.type(screen.getByLabelText('Value'), 'value')

    const saveButtons = screen.getAllByRole('button', { name: /save/i })
    await user.click(saveButtons[0])

    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith('Failed to create memory')
    })
  })

  it('should have proper placeholders', async () => {
    const user = userEvent.setup()

    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    await user.click(screen.getByRole('button', { name: /add memory/i }))

    await waitFor(() => {
      expect(screen.getByPlaceholderText('e.g., project')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('e.g., Atlas')).toBeInTheDocument()
    })
  })

  it('should display memory types with colored badges', () => {
    render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    expect(screen.getByText('fact')).toBeInTheDocument()
    expect(screen.getByText('preference')).toBeInTheDocument()
  })

  it('should reset form after successful creation', async () => {
    const user = userEvent.setup()

    api.createMemory.mockResolvedValue({ id: 3 })

    const { component } = render(MemorySettings, {
      props: {
        memories: mockMemories,
        loadingMemories: false,
        filterType: 'all'
      }
    })

    component.$on('reload', () => {})

    await user.click(screen.getByRole('button', { name: /add memory/i }))

    await waitFor(() => {
      expect(screen.getByLabelText('Key')).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Key'), 'test')
    await user.type(screen.getByLabelText('Value'), 'value')

    const saveButtons = screen.getAllByRole('button', { name: /save/i })
    await user.click(saveButtons[0])

    await waitFor(() => {
      expect(screen.queryByLabelText('Key')).not.toBeInTheDocument()
    })
  })
})
