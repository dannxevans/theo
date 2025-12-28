import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import Chat from '@/components/Chat.svelte'
import * as api from '@/lib/api.js'

vi.mock('@/lib/api.js')

describe('Chat Flow Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    global.localStorage = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn()
    }

    global.window = {
      ...global.window,
      dispatchEvent: vi.fn(),
      addEventListener: vi.fn(),
      confirm: vi.fn(() => true),
      alert: vi.fn(),
      location: { reload: vi.fn() }
    }

    global.document.querySelector = vi.fn(() => ({
      scrollTop: 0,
      scrollHeight: 1000
    }))

    global.Prism = {
      languages: { python: {} },
      highlightElement: vi.fn()
    }

    // Default mocks
    api.getProviders.mockResolvedValue([
      { id: 'anthropic', name: 'Anthropic', enabled: true, type: 'anthropic' },
      { id: 'openai', name: 'OpenAI', enabled: true, type: 'openai' }
    ])
    api.getSessionMessages.mockResolvedValue([])
    api.fetchSessionSummary.mockResolvedValue({ summary: '' })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Create New Session and Send Message', () => {
    it('should complete full chat flow from new session to response', async () => {
      const user = userEvent.setup()
      const sessionId = 'new-session-123'

      // Mock streaming response
      api.streamMessage.mockImplementation(({ onToken, onEnd }) => {
        setTimeout(() => {
          onToken('Hello! ')
          onToken('How can ')
          onToken('I help you ')
          onToken('today?')
          onEnd({ provider: 'anthropic', model: 'claude-3-5-sonnet' })
        }, 10)
        return () => {}
      })

      // Mock session reload after streaming
      api.getSessionMessages.mockResolvedValueOnce([])
        .mockResolvedValueOnce([
          {
            role: 'user',
            content: 'Hello THEO',
            created_at: new Date().toISOString()
          },
          {
            role: 'assistant',
            content: 'Hello! How can I help you today?',
            provider: 'anthropic',
            model: 'claude-3-5-sonnet',
            task_type: 'general',
            created_at: new Date().toISOString()
          }
        ])

      api.generateSessionTitle.mockResolvedValue({ title: 'Greeting' })

      render(Chat, { props: { sessionId } })

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      // Verify welcome message
      expect(screen.getByText(/Hello, what do you want to do today/i)).toBeInTheDocument()

      // Send message
      const input = screen.getByPlaceholderText('Talk to THEO')
      await user.type(input, 'Hello THEO')
      await user.click(screen.getByRole('button', { name: /send/i }))

      // Verify user message appears
      await waitFor(() => {
        expect(screen.getByText('Hello THEO')).toBeInTheDocument()
      })

      // Verify streaming happens
      await waitFor(() => {
        expect(screen.getByText(/streaming/i)).toBeInTheDocument()
      })

      // Wait for complete response
      await waitFor(() => {
        expect(screen.getByText('Hello! How can I help you today?')).toBeInTheDocument()
      }, { timeout: 2000 })

      // Verify API calls
      expect(api.streamMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          sessionId,
          text: 'Hello THEO'
        })
      )

      // Verify title generation for first message
      await waitFor(() => {
        expect(api.generateSessionTitle).toHaveBeenCalledWith(sessionId)
      })
    })

    it('should handle multiple messages in conversation', async () => {
      const user = userEvent.setup()
      const sessionId = 'session-multi-123'

      let callCount = 0

      api.streamMessage.mockImplementation(({ text, onToken, onEnd }) => {
        callCount++
        setTimeout(() => {
          if (callCount === 1) {
            onToken('Hi there!')
          } else {
            onToken('Svelte is great!')
          }
          onEnd({ provider: 'anthropic' })
        }, 10)
        return () => {}
      })

      api.getSessionMessages
        .mockResolvedValueOnce([]) // Initial load
        .mockResolvedValueOnce([ // After first message
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hi there!', provider: 'anthropic' }
        ])
        .mockResolvedValueOnce([ // After second message
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hi there!', provider: 'anthropic' },
          { role: 'user', content: 'Tell me about Svelte' },
          { role: 'assistant', content: 'Svelte is great!', provider: 'anthropic' }
        ])

      api.generateSessionTitle.mockResolvedValue({ title: 'Svelte Discussion' })

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      // First message
      await user.type(screen.getByPlaceholderText('Talk to THEO'), 'Hello')
      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(screen.getByText('Hi there!')).toBeInTheDocument()
      })

      // Second message
      await user.type(screen.getByPlaceholderText('Talk to THEO'), 'Tell me about Svelte')
      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(screen.getByText('Svelte is great!')).toBeInTheDocument()
      })

      expect(api.streamMessage).toHaveBeenCalledTimes(2)
    })
  })

  describe('Session Loading and Switching', () => {
    it('should load existing session messages', async () => {
      const sessionId = 'existing-session-456'

      const existingMessages = [
        {
          role: 'user',
          content: 'Previous question',
          created_at: new Date(Date.now() - 3600000).toISOString()
        },
        {
          role: 'assistant',
          content: 'Previous answer',
          provider: 'openai',
          model: 'gpt-4',
          created_at: new Date(Date.now() - 3500000).toISOString()
        }
      ]

      api.getSessionMessages.mockResolvedValue(existingMessages)

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByText('Previous question')).toBeInTheDocument()
        expect(screen.getByText('Previous answer')).toBeInTheDocument()
      })

      expect(api.getSessionMessages).toHaveBeenCalledWith(sessionId)
    })

    it('should reload messages when switching sessions', async () => {
      const { rerender } = render(Chat, { props: { sessionId: 'session-1' } })

      await waitFor(() => {
        expect(api.getSessionMessages).toHaveBeenCalledWith('session-1')
      })

      vi.clearAllMocks()

      // Switch to different session
      rerender({ sessionId: 'session-2' })

      await waitFor(() => {
        expect(api.getSessionMessages).toHaveBeenCalledWith('session-2')
      })
    })
  })

  describe('Provider Selection and Routing', () => {
    it('should use automatic routing by default', async () => {
      const user = userEvent.setup()
      const sessionId = 'auto-route-session'

      api.streamMessage.mockImplementation(({ onEnd }) => {
        setTimeout(() => onEnd({}), 10)
        return () => {}
      })

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      await user.type(screen.getByPlaceholderText('Talk to THEO'), 'Test message')
      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(api.streamMessage).toHaveBeenCalledWith(
          expect.objectContaining({
            forcedProvider: ''
          })
        )
      })
    })

    it('should use forced provider when selected', async () => {
      const user = userEvent.setup()
      const sessionId = 'forced-route-session'

      api.streamMessage.mockImplementation(({ onEnd }) => {
        setTimeout(() => onEnd({}), 10)
        return () => {}
      })

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      // Select specific provider
      const providerSelect = screen.getByTitle('Model')
      await user.selectOptions(providerSelect, 'anthropic')

      await user.type(screen.getByPlaceholderText('Talk to THEO'), 'Test message')
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
    it('should delete session successfully', async () => {
      const user = userEvent.setup()
      const sessionId = 'delete-session-789'

      window.confirm.mockReturnValue(true)
      api.deleteSessionApi.mockResolvedValue({ success: true })

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /delete/i }))

      expect(window.confirm).toHaveBeenCalledWith(
        expect.stringContaining('Delete this chat')
      )

      await waitFor(() => {
        expect(api.deleteSessionApi).toHaveBeenCalledWith(sessionId)
        expect(window.location.reload).toHaveBeenCalled()
      })
    })

    it('should cancel deletion if user declines', async () => {
      const user = userEvent.setup()
      const sessionId = 'cancel-delete-session'

      window.confirm.mockReturnValue(false)

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /delete/i }))

      expect(api.deleteSessionApi).not.toHaveBeenCalled()
      expect(window.location.reload).not.toHaveBeenCalled()
    })
  })

  describe('Error Handling', () => {
    it('should handle streaming errors gracefully', async () => {
      const user = userEvent.setup()
      const sessionId = 'error-session'

      api.streamMessage.mockImplementation(({ onError }) => {
        setTimeout(() => {
          onError(new Error('Connection lost'))
        }, 10)
        return () => {}
      })

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      await user.type(screen.getByPlaceholderText('Talk to THEO'), 'Test')
      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(screen.getByText(/Connection lost|Streaming failed/i)).toBeInTheDocument()
      })
    })

    it('should handle message loading errors', async () => {
      const sessionId = 'load-error-session'

      api.getSessionMessages.mockRejectedValue(new Error('Failed to load messages'))

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByText(/Failed to load messages/i)).toBeInTheDocument()
      })
    })
  })

  describe('Work Mode Features', () => {
    it('should show work mode subtabs', async () => {
      const sessionId = 'work-session'

      render(Chat, {
        props: {
          sessionId,
          currentMode: 'work'
        }
      })

      await waitFor(() => {
        expect(screen.getByText(/Conversation/i)).toBeInTheDocument()
        expect(screen.getByText(/Email Rewrites/i)).toBeInTheDocument()
        expect(screen.getByText(/Code Development/i)).toBeInTheDocument()
      })
    })

    it('should switch between work subtabs', async () => {
      const user = userEvent.setup()
      const sessionId = 'work-subtab-session'

      render(Chat, {
        props: {
          sessionId,
          currentMode: 'work',
          activeWorkSubtab: 'conversation'
        }
      })

      await waitFor(() => {
        expect(screen.getByText(/Email Rewrites/i)).toBeInTheDocument()
      })

      await user.click(screen.getByText(/Email Rewrites/i))

      expect(localStorage.setItem).toHaveBeenCalledWith(
        'theo.activeWorkSubtab',
        'email'
      )
    })

    it('should pass work subtab to streaming API', async () => {
      const user = userEvent.setup()
      const sessionId = 'work-api-session'

      api.streamMessage.mockImplementation(({ onEnd }) => {
        setTimeout(() => onEnd({}), 10)
        return () => {}
      })

      render(Chat, {
        props: {
          sessionId,
          currentMode: 'work',
          activeWorkSubtab: 'email'
        }
      })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      await user.type(screen.getByPlaceholderText('Talk to THEO'), 'Draft an email')
      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(api.streamMessage).toHaveBeenCalledWith(
          expect.objectContaining({
            workSubtab: 'email'
          })
        )
      })
    })
  })

  describe('Real-time Updates', () => {
    it('should stream tokens in real-time', async () => {
      const user = userEvent.setup()
      const sessionId = 'stream-session'

      let tokenCallback
      api.streamMessage.mockImplementation(({ onToken, onEnd }) => {
        tokenCallback = onToken
        setTimeout(() => {
          onToken('First ')
          setTimeout(() => {
            onToken('Second ')
            setTimeout(() => {
              onToken('Third')
              onEnd({})
            }, 50)
          }, 50)
        }, 50)
        return () => {}
      })

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      await user.type(screen.getByPlaceholderText('Talk to THEO'), 'Test')
      await user.click(screen.getByRole('button', { name: /send/i }))

      // Check for streaming indicator
      await waitFor(() => {
        expect(screen.getByText(/streaming/i)).toBeInTheDocument()
      })

      // Wait for complete message
      await waitFor(() => {
        expect(screen.getByText(/First Second Third/i)).toBeInTheDocument()
      }, { timeout: 500 })
    })
  })

  describe('Input Handling', () => {
    it('should clear input after sending', async () => {
      const user = userEvent.setup()
      const sessionId = 'clear-input-session'

      api.streamMessage.mockImplementation(({ onEnd }) => {
        setTimeout(() => onEnd({}), 10)
        return () => {}
      })

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Talk to THEO')
      await user.type(input, 'Test message')

      expect(input).toHaveValue('Test message')

      await user.click(screen.getByRole('button', { name: /send/i }))

      await waitFor(() => {
        expect(input).toHaveValue('')
      })
    })

    it('should not send empty messages', async () => {
      const user = userEvent.setup()
      const sessionId = 'empty-message-session'

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      await user.click(screen.getByRole('button', { name: /send/i }))

      expect(api.streamMessage).not.toHaveBeenCalled()
    })

    it('should send message on Enter key', async () => {
      const user = userEvent.setup()
      const sessionId = 'enter-key-session'

      api.streamMessage.mockImplementation(({ onEnd }) => {
        setTimeout(() => onEnd({}), 10)
        return () => {}
      })

      render(Chat, { props: { sessionId } })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Talk to THEO')).toBeInTheDocument()
      })

      await user.type(screen.getByPlaceholderText('Talk to THEO'), 'Test{Enter}')

      await waitFor(() => {
        expect(api.streamMessage).toHaveBeenCalled()
      })
    })
  })
})
