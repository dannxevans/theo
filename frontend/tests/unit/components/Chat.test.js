import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import Chat from '@/components/Chat.svelte'
import * as api from '@/lib/api.js'

// Mock the API module
vi.mock('@/lib/api.js', () => ({
  streamMessage: vi.fn(),
  getProviders: vi.fn(),
  getSessionMessages: vi.fn(),
  fetchSessionSummary: vi.fn(),
  deleteSessionApi: vi.fn(),
  exportSession: vi.fn(),
  forkSession: vi.fn(),
  generateSessionTitle: vi.fn(),
  approveConfirmation: vi.fn(),
  rejectConfirmation: vi.fn()
}))

describe('Chat Component', () => {
  let mockSessionId

  beforeEach(() => {
    mockSessionId = 'test-session-123'
    vi.clearAllMocks()

    // Mock localStorage
    global.localStorage = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn()
    }

    // Mock window methods
    global.window = {
      ...global.window,
      dispatchEvent: vi.fn(),
      addEventListener: vi.fn(),
      confirm: vi.fn(() => true),
      alert: vi.fn(),
      location: {
        reload: vi.fn()
      }
    }

    // Mock document.querySelector for scrolling
    global.document.querySelector = vi.fn(() => ({
      scrollTop: 0,
      scrollHeight: 1000
    }))

    // Mock Prism for code highlighting
    global.Prism = {
      languages: { python: {} },
      highlightElement: vi.fn()
    }

    // Default mock responses
    api.getProviders.mockResolvedValue([
      { id: 'anthropic', name: 'Anthropic', enabled: true, type: 'anthropic' },
      { id: 'openai', name: 'OpenAI', enabled: true, type: 'openai' }
    ])

    api.getSessionMessages.mockResolvedValue([])
    api.fetchSessionSummary.mockResolvedValue({ summary: '' })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render chat interface', async () => {
      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument()
      })
    })

    it('should display welcome message when no messages', async () => {
      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByText(/Hello, what do you want to do today/i)).toBeInTheDocument()
      })
    })

    it('should load existing messages for session', async () => {
      const mockMessages = [
        {
          role: 'user',
          content: 'Hello',
          created_at: new Date().toISOString()
        },
        {
          role: 'assistant',
          content: 'Hi there!',
          provider: 'anthropic',
          model: 'claude-3-5-sonnet',
          created_at: new Date().toISOString()
        }
      ]

      api.getSessionMessages.mockResolvedValue(mockMessages)

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByText('Hello')).toBeInTheDocument()
        expect(screen.getByText('Hi there!')).toBeInTheDocument()
      })
    })

    it('should display session actions bar', async () => {
      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
      })
    })

    it('should show provider selector with Auto option', async () => {
      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        const select = screen.getByTitle('Model')
        expect(select).toBeInTheDocument()
        expect(select.querySelector('option[value=""]')).toHaveTextContent('Auto')
      })
    })

    it('should load and display available providers', async () => {
      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        const select = screen.getByTitle('Model')
        const options = Array.from(select.querySelectorAll('option'))
        const providerNames = options.map(opt => opt.textContent)

        expect(providerNames).toContain('Anthropic')
        expect(providerNames).toContain('OpenAI')
      })
    })
  })

  describe('Message Sending', () => {
    it('should send a message', async () => {
      const user = userEvent.setup()

      let onTokenCallback
      api.streamMessage.mockImplementation(({ onToken, onEnd }) => {
        onTokenCallback = onToken
        setTimeout(() => {
          onToken('Hello ')
          onToken('there!')
          onEnd({ provider: 'anthropic' })
        }, 10)
        return () => {}
      })

      api.getSessionMessages.mockResolvedValue([])

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Talk to THEO')
      await user.type(input, 'Test message')
      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(api.streamMessage).toHaveBeenCalledWith(
          expect.objectContaining({
            sessionId: mockSessionId,
            text: 'Test message'
          })
        )
      })
    })

    it('should clear input after sending', async () => {
      const user = userEvent.setup()

      api.streamMessage.mockImplementation(({ onEnd }) => {
        setTimeout(() => onEnd({}), 10)
        return () => {}
      })

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Talk to THEO')
      await user.type(input, 'Test message')

      expect(input.value).toBe('Test message')

      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(input.value).toBe('')
      })
    })

    it('should send message on Enter key', async () => {
      const user = userEvent.setup()

      api.streamMessage.mockImplementation(({ onEnd }) => {
        setTimeout(() => onEnd({}), 10)
        return () => {}
      })

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Talk to THEO')
      await user.type(input, 'Test message{Enter}')

      await waitFor(() => {
        expect(api.streamMessage).toHaveBeenCalled()
      })
    })

    it('should not send empty messages', async () => {
      const user = userEvent.setup()

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /send/i }))

      expect(api.streamMessage).not.toHaveBeenCalled()
    })

    it('should disable send button while loading', async () => {
      const user = userEvent.setup()

      let resolveStream
      const streamPromise = new Promise((resolve) => {
        resolveStream = resolve
      })

      api.streamMessage.mockImplementation(({ onEnd }) => {
        streamPromise.then(() => onEnd({}))
        return () => {}
      })

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Talk to THEO')
      await user.type(input, 'Test')
      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        const button = screen.getByRole('button', { name: /thinking/i })
        expect(button).toBeDisabled()
      })

      resolveStream()
    })

    it('should display streaming message', async () => {
      const user = userEvent.setup()

      api.streamMessage.mockImplementation(({ onToken, onEnd }) => {
        setTimeout(() => {
          onToken('Streaming ')
          onToken('response ')
          onToken('here!')
        }, 10)
        setTimeout(() => onEnd({}), 50)
        return () => {}
      })

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Talk to THEO')
      await user.type(input, 'Test')
      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(screen.getByText(/streaming/i)).toBeInTheDocument()
      })
    })

    it('should use forced provider when selected', async () => {
      const user = userEvent.setup()

      api.streamMessage.mockImplementation(({ onEnd }) => {
        setTimeout(() => onEnd({}), 10)
        return () => {}
      })

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      // Select a specific provider
      const select = screen.getByTitle('Model')
      await user.selectOptions(select, 'anthropic')

      const input = screen.getByPlaceholderText('Talk to THEO')
      await user.type(input, 'Test')
      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(api.streamMessage).toHaveBeenCalledWith(
          expect.objectContaining({
            forcedProvider: 'anthropic'
          })
        )
      })
    })
  })

  describe('Session Management', () => {
    it('should delete session when confirmed', async () => {
      const user = userEvent.setup()

      window.confirm.mockReturnValue(true)
      api.deleteSessionApi.mockResolvedValue({ success: true })

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /delete/i }))

      await waitFor(() => {
        expect(api.deleteSessionApi).toHaveBeenCalledWith(mockSessionId)
        expect(window.location.reload).toHaveBeenCalled()
      })
    })

    it('should not delete session when cancelled', async () => {
      const user = userEvent.setup()

      window.confirm.mockReturnValue(false)

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /delete/i }))

      expect(api.deleteSessionApi).not.toHaveBeenCalled()
    })

    it('should handle delete errors', async () => {
      const user = userEvent.setup()

      window.confirm.mockReturnValue(true)
      window.alert.mockImplementation(() => {})
      api.deleteSessionApi.mockRejectedValue(new Error('Delete failed'))

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /delete/i }))

      await waitFor(() => {
        expect(window.alert).toHaveBeenCalledWith('Failed to delete session')
      })
    })

    it('should reload messages when sessionId changes', async () => {
      const { rerender } = render(Chat, { props: { sessionId: 'session-1' } })

      await waitFor(() => {
        expect(api.getSessionMessages).toHaveBeenCalledWith('session-1')
      })

      vi.clearAllMocks()

      rerender({ sessionId: 'session-2' })

      await waitFor(() => {
        expect(api.getSessionMessages).toHaveBeenCalledWith('session-2')
      })
    })

    it('should generate session title after first response', async () => {
      const user = userEvent.setup()

      api.getSessionMessages.mockResolvedValue([])
      api.generateSessionTitle.mockResolvedValue({ title: 'Generated Title' })

      api.streamMessage.mockImplementation(({ onEnd }) => {
        setTimeout(() => {
          onEnd({ provider: 'anthropic' })
        }, 10)
        return () => {}
      })

      // Mock getSessionMessages to return one assistant message after streaming
      api.getSessionMessages.mockResolvedValueOnce([])
        .mockResolvedValueOnce([
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hi!', provider: 'anthropic' }
        ])

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Talk to THEO')
      await user.type(input, 'Test message')
      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(api.generateSessionTitle).toHaveBeenCalledWith(mockSessionId)
      }, { timeout: 2000 })
    })
  })

  describe('Advanced Features', () => {
    beforeEach(() => {
      localStorage.getItem.mockReturnValue('true') // advancedMode enabled
    })

    it('should show export buttons when advanced mode enabled', async () => {
      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /export json/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /export md/i })).toBeInTheDocument()
      })
    })

    it('should export session as JSON', async () => {
      const user = userEvent.setup()

      api.exportSession.mockResolvedValue(undefined)

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /export json/i })).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /export json/i }))

      await waitFor(() => {
        expect(api.exportSession).toHaveBeenCalledWith(mockSessionId, 'json')
      })
    })

    it('should export session as markdown', async () => {
      const user = userEvent.setup()

      api.exportSession.mockResolvedValue(undefined)

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /export md/i })).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /export md/i }))

      await waitFor(() => {
        expect(api.exportSession).toHaveBeenCalledWith(mockSessionId, 'markdown')
      })
    })

    it('should fork session', async () => {
      const user = userEvent.setup()

      window.alert.mockImplementation(() => {})
      api.forkSession.mockResolvedValue({ session_id: 'new-session' })

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /fork/i })).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /fork/i }))

      await waitFor(() => {
        expect(api.forkSession).toHaveBeenCalledWith(mockSessionId)
        expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('new-session'))
      })
    })
  })

  describe('Work Mode', () => {
    it('should show work mode subtabs when currentMode is work', async () => {
      render(Chat, {
        props: {
          sessionId: mockSessionId,
          currentMode: 'work'
        }
      })

      await waitFor(() => {
        expect(screen.getByText(/Conversation/i)).toBeInTheDocument()
        expect(screen.getByText(/Email Rewrites/i)).toBeInTheDocument()
        expect(screen.getByText(/Code Development/i)).toBeInTheDocument()
      })
    })

    it('should not show work subtabs in personal mode', async () => {
      render(Chat, {
        props: {
          sessionId: mockSessionId,
          currentMode: 'personal'
        }
      })

      await waitFor(() => {
        expect(screen.queryByText(/Email Rewrites/i)).not.toBeInTheDocument()
      })
    })

    it('should switch work subtabs', async () => {
      const user = userEvent.setup()

      render(Chat, {
        props: {
          sessionId: mockSessionId,
          currentMode: 'work'
        }
      })

      await waitFor(() => {
        expect(screen.getByText(/Email Rewrites/i)).toBeInTheDocument()
      })

      await user.click(screen.getByText(/Email Rewrites/i))

      expect(localStorage.setItem).toHaveBeenCalledWith('theo.activeWorkSubtab', 'email')
    })

    it('should display OFFICIAL badge in work mode', async () => {
      render(Chat, {
        props: {
          sessionId: mockSessionId,
          currentMode: 'work'
        }
      })

      await waitFor(() => {
        expect(screen.getByText(/OFFICIAL/i)).toBeInTheDocument()
      })
    })
  })

  describe('Confirmation Workflow', () => {
    it('should display confirmation widget for pending confirmations', async () => {
      const mockMessages = [
        {
          role: 'assistant',
          content: 'I can add that to your calendar.',
          metadata: {
            requires_confirmation: true,
            confirmation_id: 'conf-123',
            confirmation_message: 'Add "Team Meeting" to your calendar?',
            action_category: 'calendar',
            approved: false,
            rejected: false,
            expires_at: new Date(Date.now() + 3600000).toISOString()
          }
        }
      ]

      api.getSessionMessages.mockResolvedValue(mockMessages)

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByText(/Add "Team Meeting" to your calendar/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument()
      })
    })

    it('should approve confirmation', async () => {
      const user = userEvent.setup()

      const mockMessages = [
        {
          role: 'assistant',
          content: 'I can add that to your calendar.',
          metadata: {
            requires_confirmation: true,
            confirmation_id: 'conf-123',
            confirmation_message: 'Add "Team Meeting" to your calendar?',
            action_category: 'calendar',
            approved: false,
            rejected: false
          }
        }
      ]

      api.getSessionMessages.mockResolvedValue(mockMessages)
      api.approveConfirmation.mockResolvedValue({ success: true })

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /approve/i }))

      await waitFor(() => {
        expect(api.approveConfirmation).toHaveBeenCalledWith('conf-123')
      })
    })

    it('should reject confirmation', async () => {
      const user = userEvent.setup()

      const mockMessages = [
        {
          role: 'assistant',
          content: 'I can add that to your calendar.',
          metadata: {
            requires_confirmation: true,
            confirmation_id: 'conf-123',
            confirmation_message: 'Add "Team Meeting" to your calendar?',
            action_category: 'calendar',
            approved: false,
            rejected: false
          }
        }
      ]

      api.getSessionMessages.mockResolvedValue(mockMessages)
      api.rejectConfirmation.mockResolvedValue({ success: true })

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /reject/i }))

      await waitFor(() => {
        expect(api.rejectConfirmation).toHaveBeenCalledWith('conf-123')
      })
    })
  })

  describe('Error Handling', () => {
    it('should display error on stream failure', async () => {
      const user = userEvent.setup()

      api.streamMessage.mockImplementation(({ onError }) => {
        setTimeout(() => onError(new Error('Stream failed')), 10)
        return () => {}
      })

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Talk to THEO')
      await user.type(input, 'Test')
      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(screen.getByText(/Stream failed|Streaming failed/i)).toBeInTheDocument()
      })
    })

    it('should handle message loading errors', async () => {
      api.getSessionMessages.mockRejectedValue(new Error('Load failed'))

      render(Chat, { props: { sessionId: mockSessionId } })

      await waitFor(() => {
        expect(screen.getByText(/Failed to load messages/i)).toBeInTheDocument()
      })
    })
  })
})
