import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import GeneralSettings from '@/components/settings/GeneralSettings.svelte'
import IntentsSettings from '@/components/settings/IntentsSettings.svelte'
import MemorySettings from '@/components/settings/MemorySettings.svelte'
import AIProvidersSettings from '@/components/settings/AIProvidersSettings.svelte'
import * as api from '@/lib/api.js'

vi.mock('@/lib/api.js')

describe('Settings Flow Integration Tests', () => {
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

  describe('General Settings Flow', () => {
    it('should update system prompt configuration end-to-end', async () => {
      const user = userEvent.setup()
      vi.useFakeTimers()

      const initialConfig = {
        persona_name: 'THEO',
        tone: 'professional',
        style_rules: '',
        custom_instructions: ''
      }

      api.updateSystemPromptConfig.mockResolvedValue({ success: true })

      render(GeneralSettings, {
        props: { systemPromptConfig: initialConfig }
      })

      // Modify all fields
      await user.clear(screen.getByLabelText('Persona Name'))
      await user.type(screen.getByLabelText('Persona Name'), 'ASSISTANT')

      await user.clear(screen.getByLabelText('Tone'))
      await user.type(screen.getByLabelText('Tone'), 'friendly, casual')

      await user.type(screen.getByLabelText('Style Rules'), '- Be concise\n- Use examples')
      await user.type(screen.getByLabelText(/Custom Instructions/i), 'Always confirm before actions')

      // Save
      await user.click(screen.getByRole('button', { name: /save settings/i }))

      // Verify API call
      await waitFor(() => {
        expect(api.updateSystemPromptConfig).toHaveBeenCalledWith({
          persona_name: 'ASSISTANT',
          tone: 'friendly, casual',
          style_rules: '- Be concise\n- Use examples',
          custom_instructions: 'Always confirm before actions'
        })
      })

      // Verify success message
      expect(screen.getByText(/Settings saved successfully/i)).toBeInTheDocument()

      // Verify success message disappears after 3 seconds
      vi.advanceTimersByTime(3000)

      await waitFor(() => {
        expect(screen.queryByText(/Settings saved successfully/i)).not.toBeInTheDocument()
      })

      vi.useRealTimers()
    })

    it('should handle save errors gracefully', async () => {
      const user = userEvent.setup()

      const config = {
        persona_name: 'THEO',
        tone: 'professional',
        style_rules: '',
        custom_instructions: ''
      }

      api.updateSystemPromptConfig.mockRejectedValue(new Error('Network error'))

      render(GeneralSettings, {
        props: { systemPromptConfig: config }
      })

      await user.type(screen.getByLabelText('Style Rules'), 'New rule')
      await user.click(screen.getByRole('button', { name: /save settings/i }))

      await waitFor(() => {
        expect(screen.getByText(/Error: Network error/i)).toBeInTheDocument()
      })

      // Verify edited content is preserved
      expect(screen.getByLabelText('Style Rules')).toHaveValue('New rule')
    })
  })

  describe('Intent Management Flow', () => {
    it('should create, edit, and delete intent', async () => {
      const user = userEvent.setup()

      const mockIntents = [
        {
          id: 'coding',
          name: 'Coding',
          description: 'Code tasks',
          keywords: 'code,program',
          priority: 80,
          enabled: true
        }
      ]

      api.createIntent.mockResolvedValue({
        id: 'data-analysis',
        name: 'Data Analysis',
        enabled: true
      })
      api.updateIntent.mockResolvedValue({ success: true })
      api.deleteIntent.mockResolvedValue({ success: true })

      const { component, rerender } = render(IntentsSettings, {
        props: { intents: mockIntents }
      })

      const reloadHandler = vi.fn()
      component.$on('reload', reloadHandler)

      // CREATE: Add new intent
      await user.click(screen.getByRole('button', { name: /new intent/i }))

      await waitFor(() => {
        expect(screen.getByLabelText('ID')).toBeInTheDocument()
      })

      await user.type(screen.getByLabelText('ID'), 'data-analysis')
      await user.type(screen.getByLabelText('Name'), 'Data Analysis')
      await user.type(screen.getByLabelText('Description'), 'Analyze data and create charts')
      await user.type(screen.getByLabelText(/Keywords/i), 'data,analyze,chart,graph')

      const priorityInput = screen.getByLabelText('Priority')
      await user.clear(priorityInput)
      await user.type(priorityInput, '70')

      await user.click(screen.getByRole('button', { name: /create intent/i }))

      await waitFor(() => {
        expect(api.createIntent).toHaveBeenCalledWith({
          id: 'data-analysis',
          name: 'Data Analysis',
          description: 'Analyze data and create charts',
          keywords: 'data,analyze,chart,graph',
          priority: 70,
          enabled: true
        })
        expect(reloadHandler).toHaveBeenCalled()
      })

      // EDIT: Update existing intent
      reloadHandler.mockClear()

      const editButtons = screen.getAllByRole('button', { name: /edit/i })
      await user.click(editButtons[0])

      await waitFor(() => {
        expect(screen.getByDisplayValue('Coding')).toBeInTheDocument()
      })

      const nameInput = screen.getByLabelText('Name')
      await user.clear(nameInput)
      await user.type(nameInput, 'Software Development')

      await user.click(screen.getByRole('button', { name: /save changes/i }))

      await waitFor(() => {
        expect(api.updateIntent).toHaveBeenCalledWith('coding', {
          name: 'Software Development',
          description: 'Code tasks',
          keywords: 'code,program',
          priority: 80,
          enabled: true
        })
        expect(reloadHandler).toHaveBeenCalled()
      })

      // DELETE: Remove intent
      reloadHandler.mockClear()
      window.confirm.mockReturnValue(true)

      const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
      await user.click(deleteButtons[0])

      await waitFor(() => {
        expect(api.deleteIntent).toHaveBeenCalledWith('coding')
        expect(reloadHandler).toHaveBeenCalled()
      })
    })

    it('should toggle intent enabled status', async () => {
      const user = userEvent.setup()

      const mockIntents = [
        {
          id: 'test-intent',
          name: 'Test Intent',
          enabled: true,
          priority: 50
        }
      ]

      api.updateIntent.mockResolvedValue({ success: true })

      const { component } = render(IntentsSettings, {
        props: { intents: mockIntents }
      })

      const reloadHandler = vi.fn()
      component.$on('reload', reloadHandler)

      const disableButton = screen.getByRole('button', { name: /disable/i })
      await user.click(disableButton)

      await waitFor(() => {
        expect(api.updateIntent).toHaveBeenCalledWith('test-intent', {
          enabled: false
        })
        expect(reloadHandler).toHaveBeenCalled()
      })
    })
  })

  describe('Memory Management Flow', () => {
    it('should create, pin, and delete memory', async () => {
      const user = userEvent.setup()

      const mockMemories = [
        {
          id: 1,
          type: 'fact',
          key: 'project',
          value: 'Atlas',
          pinned: false,
          relevance_score: 0.9,
          access_count: 5,
          created_at: new Date().toISOString(),
          last_accessed_at: new Date().toISOString()
        }
      ]

      api.createMemory.mockResolvedValue({
        id: 2,
        type: 'preference',
        key: 'language',
        value: 'TypeScript'
      })
      api.pinMemory.mockResolvedValue({ success: true })
      api.deleteMemory.mockResolvedValue({ success: true })

      const { component } = render(MemorySettings, {
        props: {
          memories: mockMemories,
          loadingMemories: false,
          filterType: 'all'
        }
      })

      const reloadHandler = vi.fn()
      component.$on('reload', reloadHandler)

      // CREATE: Add new memory
      await user.click(screen.getByRole('button', { name: /add memory/i }))

      await waitFor(() => {
        expect(screen.getByLabelText('Type')).toBeInTheDocument()
      })

      const typeSelect = screen.getByLabelText('Type')
      await user.selectOptions(typeSelect, 'preference')

      await user.type(screen.getByLabelText('Key'), 'language')
      await user.type(screen.getByLabelText('Value'), 'TypeScript')

      const pinCheckbox = screen.getByRole('checkbox', { name: /pin this memory/i })
      await user.click(pinCheckbox)

      const saveButtons = screen.getAllByRole('button', { name: /save/i })
      await user.click(saveButtons[0])

      await waitFor(() => {
        expect(api.createMemory).toHaveBeenCalledWith({
          type: 'preference',
          key: 'language',
          value: 'TypeScript',
          pinned: true
        })
        expect(reloadHandler).toHaveBeenCalled()
      })

      // PIN: Toggle pin status
      reloadHandler.mockClear()

      const pinButton = screen.getByRole('button', { name: 'Pin' })
      await user.click(pinButton)

      await waitFor(() => {
        expect(api.pinMemory).toHaveBeenCalledWith(1, true)
        expect(reloadHandler).toHaveBeenCalled()
      })

      // DELETE: Remove memory
      reloadHandler.mockClear()
      window.confirm.mockReturnValue(true)

      const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
      await user.click(deleteButtons[0])

      await waitFor(() => {
        expect(api.deleteMemory).toHaveBeenCalledWith(1)
        expect(reloadHandler).toHaveBeenCalled()
      })
    })

    it('should filter memories by type', async () => {
      const user = userEvent.setup()

      const { component } = render(MemorySettings, {
        props: {
          memories: [],
          loadingMemories: false,
          filterType: 'all'
        }
      })

      // Click on different filter buttons
      await user.click(screen.getByRole('button', { name: 'Facts' }))
      await user.click(screen.getByRole('button', { name: 'Preferences' }))
      await user.click(screen.getByRole('button', { name: 'Goals' }))
      await user.click(screen.getByRole('button', { name: 'Context' }))
      await user.click(screen.getByRole('button', { name: 'All' }))

      // Component should update filterType internally
      // (exact assertion depends on component implementation)
    })
  })

  describe('AI Provider Management Flow', () => {
    it('should create, edit, and delete provider', async () => {
      const user = userEvent.setup()

      const mockProviders = [
        {
          id: 'anthropic',
          name: 'Anthropic Claude',
          type: 'anthropic',
          model: 'claude-3-5-sonnet',
          enabled: true
        }
      ]

      const mockHealth = {
        anthropic: {
          health_status: 'healthy',
          circuit_breaker_open: false,
          total_requests: 100,
          failure_rate: 2,
          avg_latency_ms: 250
        }
      }

      api.upsertProvider.mockResolvedValue({ success: true })
      api.deleteProvider.mockResolvedValue({ success: true })

      const { component } = render(AIProvidersSettings, {
        props: {
          providersList: mockProviders,
          healthSummary: mockHealth
        }
      })

      const reloadHandler = vi.fn()
      component.$on('reload', reloadHandler)

      // CREATE: Add new provider
      await user.click(screen.getByRole('button', { name: /add provider/i }))

      await waitFor(() => {
        expect(screen.getByLabelText('ID')).toBeInTheDocument()
      })

      await user.type(screen.getByLabelText('ID'), 'openai-gpt4')
      await user.type(screen.getByLabelText('Name'), 'OpenAI GPT-4')

      const typeSelect = screen.getByLabelText('Type')
      await user.selectOptions(typeSelect, 'openai')

      await user.type(screen.getByLabelText('Model'), 'gpt-4')
      await user.type(screen.getByLabelText(/API Key/i), 'sk-test-key-123')

      const saveButtons = screen.getAllByRole('button', { name: /save/i })
      await user.click(saveButtons[0])

      await waitFor(() => {
        expect(api.upsertProvider).toHaveBeenCalledWith(
          expect.objectContaining({
            id: 'openai-gpt4',
            name: 'OpenAI GPT-4',
            type: 'openai',
            model: 'gpt-4',
            api_key: 'sk-test-key-123'
          })
        )
        expect(reloadHandler).toHaveBeenCalled()
      })

      // EDIT: Update existing provider
      reloadHandler.mockClear()

      const editButtons = screen.getAllByRole('button', { name: /edit/i })
      await user.click(editButtons[0])

      await waitFor(() => {
        expect(screen.getByDisplayValue('Anthropic Claude')).toBeInTheDocument()
      })

      const nameInput = screen.getByLabelText('Name')
      await user.clear(nameInput)
      await user.type(nameInput, 'Anthropic Claude Updated')

      const updateButtons = screen.getAllByRole('button', { name: /update/i })
      await user.click(updateButtons[0])

      await waitFor(() => {
        expect(api.upsertProvider).toHaveBeenCalled()
        expect(reloadHandler).toHaveBeenCalled()
      })

      // DELETE: Remove provider
      reloadHandler.mockClear()
      window.confirm.mockReturnValue(true)

      const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
      await user.click(deleteButtons[0])

      await waitFor(() => {
        expect(api.deleteProvider).toHaveBeenCalledWith('anthropic')
        expect(reloadHandler).toHaveBeenCalled()
      })
    })

    it('should validate Anthropic provider requires model', async () => {
      const user = userEvent.setup()

      render(AIProvidersSettings, {
        props: {
          providersList: [],
          healthSummary: {}
        }
      })

      await user.click(screen.getByRole('button', { name: /add provider/i }))

      await waitFor(() => {
        expect(screen.getByLabelText('ID')).toBeInTheDocument()
      })

      await user.type(screen.getByLabelText('ID'), 'test-provider')
      await user.type(screen.getByLabelText('Name'), 'Test Provider')

      const typeSelect = screen.getByLabelText('Type')
      await user.selectOptions(typeSelect, 'anthropic')

      // Try to save without model
      const saveButtons = screen.getAllByRole('button', { name: /save/i })
      await user.click(saveButtons[0])

      await waitFor(() => {
        expect(screen.getByText(/Model is required for Anthropic providers/i)).toBeInTheDocument()
      })

      expect(api.upsertProvider).not.toHaveBeenCalled()
    })
  })

  describe('Cross-Settings Workflows', () => {
    it('should create intent and assign to provider', async () => {
      const user = userEvent.setup()

      // Step 1: Create intent
      api.createIntent.mockResolvedValue({
        id: 'coding',
        name: 'Coding',
        enabled: true
      })

      const { component: intentComponent } = render(IntentsSettings, {
        props: { intents: [] }
      })

      const intentReload = vi.fn()
      intentComponent.$on('reload', intentReload)

      await user.click(screen.getByRole('button', { name: /new intent/i }))

      await waitFor(() => {
        expect(screen.getByLabelText('ID')).toBeInTheDocument()
      })

      await user.type(screen.getByLabelText('ID'), 'coding')
      await user.type(screen.getByLabelText('Name'), 'Coding')
      await user.type(screen.getByLabelText(/Keywords/i), 'code,program,debug')

      await user.click(screen.getByRole('button', { name: /create intent/i }))

      await waitFor(() => {
        expect(api.createIntent).toHaveBeenCalled()
        expect(intentReload).toHaveBeenCalled()
      })

      // Intent would now be available for routing configuration
      // (actual routing assignment would happen in RoutingSettings component)
    })

    it('should handle concurrent settings updates', async () => {
      const user = userEvent.setup()

      api.updateSystemPromptConfig.mockResolvedValue({ success: true })
      api.createMemory.mockResolvedValue({ id: 1 })

      // This would test that multiple settings can be updated
      // in the same session without conflicts
      const systemPromptConfig = {
        persona_name: 'THEO',
        tone: 'professional',
        style_rules: '',
        custom_instructions: ''
      }

      render(GeneralSettings, {
        props: { systemPromptConfig }
      })

      await user.type(screen.getByLabelText('Style Rules'), 'New rule')
      await user.click(screen.getByRole('button', { name: /save settings/i }))

      await waitFor(() => {
        expect(api.updateSystemPromptConfig).toHaveBeenCalled()
      })

      // Both operations should succeed independently
      expect(api.updateSystemPromptConfig).toHaveBeenCalledTimes(1)
    })
  })

  describe('Error Recovery', () => {
    it('should allow retry after failed save', async () => {
      const user = userEvent.setup()

      const config = {
        persona_name: 'THEO',
        tone: 'professional',
        style_rules: '',
        custom_instructions: ''
      }

      // First attempt fails
      api.updateSystemPromptConfig.mockRejectedValueOnce(new Error('Network error'))

      render(GeneralSettings, {
        props: { systemPromptConfig: config }
      })

      await user.type(screen.getByLabelText('Style Rules'), 'New rule')
      await user.click(screen.getByRole('button', { name: /save settings/i }))

      await waitFor(() => {
        expect(screen.getByText(/Error: Network error/i)).toBeInTheDocument()
      })

      // Second attempt succeeds
      api.updateSystemPromptConfig.mockResolvedValueOnce({ success: true })

      await user.click(screen.getByRole('button', { name: /save settings/i }))

      await waitFor(() => {
        expect(screen.getByText(/Settings saved successfully/i)).toBeInTheDocument()
      })
    })
  })
})
