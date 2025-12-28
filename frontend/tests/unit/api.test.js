import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import * as api from '@/lib/api.js'

describe('API Layer Tests', () => {
  let fetchMock

  beforeEach(() => {
    // Mock fetch globally
    fetchMock = vi.fn()
    global.fetch = fetchMock

    // Mock localStorage
    global.localStorage = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn()
    }

    // Mock EventSource for SSE streaming
    global.EventSource = vi.fn()

    // Mock window methods
    global.window = {
      URL: {
        createObjectURL: vi.fn(() => 'blob:mock-url'),
        revokeObjectURL: vi.fn()
      }
    }

    // Mock document for export functionality
    global.document = {
      createElement: vi.fn(() => ({
        setAttribute: vi.fn(),
        click: vi.fn()
      })),
      body: {
        appendChild: vi.fn(),
        removeChild: vi.fn()
      }
    }
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Chat API', () => {
    describe('sendMessage', () => {
      it('should send a message successfully', async () => {
        const mockResponse = {
          session_id: 'test-session',
          response: 'Hello!'
        }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockResponse
        })

        const result = await api.sendMessage({
          text: 'Hello',
          sessionId: 'test-session'
        })

        expect(fetchMock).toHaveBeenCalledWith('/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            session_id: 'test-session',
            text: 'Hello'
          })
        })
        expect(result).toEqual(mockResponse)
      })

      it('should handle API errors', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: false,
          text: async () => 'Server error'
        })

        await expect(api.sendMessage({
          text: 'Hello',
          sessionId: 'test-session'
        })).rejects.toThrow('Server error')
      })

      it('should handle network errors', async () => {
        fetchMock.mockRejectedValueOnce(new Error('Network error'))

        await expect(api.sendMessage({
          text: 'Hello',
          sessionId: 'test-session'
        })).rejects.toThrow('Network error')
      })
    })

    describe('fetchSessionSummary', () => {
      it('should fetch session summary', async () => {
        const mockSummary = { summary: 'Test summary' }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockSummary
        })

        const result = await api.fetchSessionSummary('test-session')

        expect(fetchMock).toHaveBeenCalledWith('/api/session/test-session')
        expect(result).toEqual(mockSummary)
      })

      it('should handle 404 errors', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: false,
          status: 404,
          text: async () => 'Session not found'
        })

        await expect(api.fetchSessionSummary('invalid-session'))
          .rejects.toThrow('Session not found')
      })
    })

    describe('getSessions', () => {
      it('should get sessions list', async () => {
        const mockSessions = [
          { id: '1', title: 'Session 1' },
          { id: '2', title: 'Session 2' }
        ]

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockSessions
        })

        const result = await api.getSessions()

        expect(fetchMock).toHaveBeenCalledWith('/api/sessions')
        expect(result).toEqual(mockSessions)
      })

      it('should return empty array on error', async () => {
        fetchMock.mockRejectedValueOnce(new Error('Network error'))

        const result = await api.getSessions()

        expect(result).toEqual([])
      })

      it('should return empty array for non-array response', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ sessions: [] })
        })

        const result = await api.getSessions()

        expect(result).toEqual([])
      })
    })

    describe('getSessionMessages', () => {
      it('should fetch session messages with cache-busting', async () => {
        const mockMessages = [
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hi there!' }
        ]

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockMessages
        })

        const result = await api.getSessionMessages('test-session')

        const callUrl = fetchMock.mock.calls[0][0]
        expect(callUrl).toMatch(/^\/api\/sessions\/test-session\/messages\?_=\d+$/)
        expect(fetchMock.mock.calls[0][1]).toMatchObject({
          headers: {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
          }
        })
        expect(result).toEqual(mockMessages)
      })

      it('should return empty array for non-array response', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => null
        })

        const result = await api.getSessionMessages('test-session')

        expect(result).toEqual([])
      })
    })

    describe('deleteSessionApi', () => {
      it('should delete a session', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.deleteSessionApi('test-session')

        expect(fetchMock).toHaveBeenCalledWith('/api/sessions/test-session', {
          method: 'DELETE'
        })
        expect(result).toEqual({ success: true })
      })
    })

    describe('exportSession', () => {
      it('should export session as JSON', async () => {
        const mockBlob = new Blob(['test'])

        fetchMock.mockResolvedValueOnce({
          ok: true,
          blob: async () => mockBlob
        })

        await api.exportSession('test-session', 'json')

        expect(fetchMock).toHaveBeenCalledWith('/api/sessions/test-session/export?format=json')
        expect(document.createElement).toHaveBeenCalledWith('a')
      })

      it('should export session as markdown', async () => {
        const mockBlob = new Blob(['test'])

        fetchMock.mockResolvedValueOnce({
          ok: true,
          blob: async () => mockBlob
        })

        await api.exportSession('test-session', 'markdown')

        expect(fetchMock).toHaveBeenCalledWith('/api/sessions/test-session/export?format=markdown')
      })
    })

    describe('forkSession', () => {
      it('should fork a session', async () => {
        const mockResult = { session_id: 'new-session' }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockResult
        })

        const result = await api.forkSession('test-session', 5, 'Forked conversation')

        expect(fetchMock).toHaveBeenCalledWith('/api/sessions/test-session/fork', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            turn_index: 5,
            title: 'Forked conversation'
          })
        })
        expect(result).toEqual(mockResult)
      })
    })

    describe('generateSessionTitle', () => {
      it('should generate session title', async () => {
        const mockResult = { title: 'Auto-generated title' }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockResult
        })

        const result = await api.generateSessionTitle('test-session')

        expect(fetchMock).toHaveBeenCalledWith('/api/sessions/test-session/generate-title', {
          method: 'POST'
        })
        expect(result).toEqual(mockResult)
      })
    })
  })

  describe('Memory API', () => {
    describe('rememberMemory', () => {
      it('should store a memory', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.rememberMemory('project', 'Atlas')

        expect(fetchMock).toHaveBeenCalledWith('/api/memory/remember', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            key: 'project',
            value: 'Atlas'
          })
        })
        expect(result).toEqual({ success: true })
      })
    })

    describe('forgetMemory', () => {
      it('should delete a memory', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.forgetMemory('project')

        expect(fetchMock).toHaveBeenCalledWith('/api/memory/forget', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            key: 'project'
          })
        })
        expect(result).toEqual({ success: true })
      })
    })

    describe('getMemories', () => {
      it('should fetch all memories', async () => {
        const mockMemories = [
          { id: 1, type: 'fact', key: 'project', value: 'Atlas' }
        ]

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockMemories
        })

        const result = await api.getMemories()

        expect(fetchMock).toHaveBeenCalledWith('/api/memories')
        expect(result).toEqual(mockMemories)
      })

      it('should filter memories by type', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => []
        })

        await api.getMemories({ type: 'fact', limit: 10 })

        expect(fetchMock).toHaveBeenCalledWith('/api/memories?type=fact&limit=10')
      })
    })

    describe('createMemory', () => {
      it('should create a new memory', async () => {
        const mockMemory = { id: 1, type: 'fact', key: 'name', value: 'John' }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockMemory
        })

        const result = await api.createMemory({
          type: 'fact',
          key: 'name',
          value: 'John',
          pinned: false
        })

        expect(result).toEqual(mockMemory)
      })
    })

    describe('deleteMemory', () => {
      it('should delete a memory by ID', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.deleteMemory(123)

        expect(fetchMock).toHaveBeenCalledWith('/api/memories/123', {
          method: 'DELETE'
        })
        expect(result).toEqual({ success: true })
      })
    })

    describe('pinMemory', () => {
      it('should pin a memory', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.pinMemory(123, true)

        expect(fetchMock).toHaveBeenCalledWith('/api/memories/123/pin', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            pinned: true
          })
        })
        expect(result).toEqual({ success: true })
      })
    })

    describe('getRelevantMemories', () => {
      it('should fetch relevant memories', async () => {
        const mockMemories = [
          { id: 1, key: 'project', value: 'Atlas', relevance: 0.9 }
        ]

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockMemories
        })

        const result = await api.getRelevantMemories('project status')

        expect(fetchMock).toHaveBeenCalledWith('/api/memories/relevant?q=project%20status')
        expect(result).toEqual(mockMemories)
      })
    })
  })

  describe('Provider API', () => {
    describe('listProviders', () => {
      it('should list all providers', async () => {
        const mockProviders = [
          { id: 'anthropic', name: 'Anthropic', enabled: true }
        ]

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockProviders
        })

        const result = await api.listProviders()

        expect(fetchMock).toHaveBeenCalledWith('/api/providers')
        expect(result).toEqual(mockProviders)
      })
    })

    describe('upsertProvider', () => {
      it('should create/update a provider', async () => {
        const provider = {
          id: 'test-provider',
          name: 'Test Provider',
          type: 'openai',
          model: 'gpt-4',
          enabled: true
        }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => provider
        })

        const result = await api.upsertProvider(provider)

        expect(fetchMock).toHaveBeenCalledWith('/api/providers', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(provider)
        })
        expect(result).toEqual(provider)
      })
    })

    describe('deleteProvider', () => {
      it('should delete a provider', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.deleteProvider('test-provider')

        expect(fetchMock).toHaveBeenCalledWith('/api/providers/test-provider', {
          method: 'DELETE'
        })
        expect(result).toEqual({ success: true })
      })
    })

    describe('getProviderHealth', () => {
      it('should fetch provider health metrics', async () => {
        const mockHealth = {
          'anthropic': { status: 'healthy', latency: 150 }
        }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockHealth
        })

        const result = await api.getProviderHealth()

        expect(fetchMock).toHaveBeenCalledWith('/api/providers/health')
        expect(result).toEqual(mockHealth)
      })
    })
  })

  describe('Intent API', () => {
    describe('getIntents', () => {
      it('should fetch all intents', async () => {
        const mockIntents = [
          { id: 'coding', name: 'Coding', enabled: true }
        ]

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockIntents
        })

        const result = await api.getIntents()

        expect(result).toEqual(mockIntents)
      })
    })

    describe('createIntent', () => {
      it('should create a new intent', async () => {
        const intent = {
          id: 'data-analysis',
          name: 'Data Analysis',
          keywords: 'analyze,data,chart',
          enabled: true
        }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => intent
        })

        const result = await api.createIntent(intent)

        expect(fetchMock).toHaveBeenCalledWith('/api/intents', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(intent)
        })
        expect(result).toEqual(intent)
      })
    })

    describe('updateIntent', () => {
      it('should update an intent', async () => {
        const updates = { enabled: false }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ ...updates, id: 'test' })
        })

        const result = await api.updateIntent('test', updates)

        expect(fetchMock).toHaveBeenCalledWith('/api/intents/test', {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(updates)
        })
      })
    })

    describe('deleteIntent', () => {
      it('should delete an intent', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.deleteIntent('test')

        expect(fetchMock).toHaveBeenCalledWith('/api/intents/test', {
          method: 'DELETE'
        })
        expect(result).toEqual({ success: true })
      })
    })
  })

  describe('Authentication API', () => {
    describe('login', () => {
      it('should authenticate user and return token', async () => {
        const mockResponse = {
          token: 'mock-jwt-token',
          user: { username: 'testuser' }
        }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockResponse
        })

        const result = await api.login('testuser', 'password123')

        expect(fetchMock).toHaveBeenCalledWith('/api/auth/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            username: 'testuser',
            password: 'password123'
          })
        })
        expect(result).toEqual(mockResponse)
      })

      it('should handle invalid credentials', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: false,
          json: async () => ({ error: 'Invalid credentials' })
        })

        await expect(api.login('baduser', 'badpass'))
          .rejects.toThrow('Invalid credentials')
      })
    })

    describe('logout', () => {
      it('should logout with auth token', async () => {
        localStorage.getItem.mockReturnValue('mock-token')

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.logout()

        expect(fetchMock).toHaveBeenCalledWith('/api/auth/logout', {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer mock-token'
          }
        })
        expect(result).toEqual({ success: true })
      })
    })

    describe('verifySession', () => {
      it('should verify valid session', async () => {
        localStorage.getItem.mockReturnValue('mock-token')

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ valid: true, user: { username: 'testuser' } })
        })

        const result = await api.verifySession()

        expect(result).toEqual({ valid: true, user: { username: 'testuser' } })
      })

      it('should return invalid for expired token', async () => {
        localStorage.getItem.mockReturnValue('expired-token')

        fetchMock.mockResolvedValueOnce({
          ok: false,
          status: 401
        })

        const result = await api.verifySession()

        expect(result).toEqual({ valid: false })
      })
    })

    describe('changePassword', () => {
      it('should change password', async () => {
        localStorage.getItem.mockReturnValue('mock-token')

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.changePassword('oldpass', 'newpass')

        expect(fetchMock).toHaveBeenCalledWith('/api/auth/change-password', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer mock-token'
          },
          body: JSON.stringify({
            current_password: 'oldpass',
            new_password: 'newpass'
          })
        })
        expect(result).toEqual({ success: true })
      })
    })
  })

  describe('System Settings API', () => {
    describe('getSystemPromptConfig', () => {
      it('should fetch system prompt configuration', async () => {
        const mockConfig = {
          persona_name: 'THEO',
          tone: 'professional',
          style_rules: 'Be concise'
        }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockConfig
        })

        const result = await api.getSystemPromptConfig()

        expect(result).toEqual(mockConfig)
      })
    })

    describe('updateSystemPromptConfig', () => {
      it('should update system prompt configuration', async () => {
        const config = {
          persona_name: 'THEO',
          tone: 'friendly'
        }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => config
        })

        const result = await api.updateSystemPromptConfig(config)

        expect(fetchMock).toHaveBeenCalledWith('/api/settings/system-prompt', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(config)
        })
        expect(result).toEqual(config)
      })
    })

    describe('getDebugFlag', () => {
      it('should fetch debug flag status', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ enabled: true })
        })

        const result = await api.getDebugFlag()

        expect(result).toBe(true)
      })
    })

    describe('setDebugFlag', () => {
      it('should enable debug mode', async () => {
        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ enabled: true })
        })

        const result = await api.setDebugFlag(true)

        expect(fetchMock).toHaveBeenCalledWith('/api/settings/debug', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            enabled: true
          })
        })
      })
    })
  })

  describe('M365 Integration API', () => {
    describe('startM365Auth', () => {
      it('should start M365 authentication flow', async () => {
        localStorage.getItem.mockReturnValue('mock-token')

        const mockResponse = {
          device_code: 'ABC123',
          user_code: 'XYZ789',
          verification_uri: 'https://microsoft.com/devicelogin'
        }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockResponse
        })

        const result = await api.startM365Auth()

        expect(result).toEqual(mockResponse)
      })
    })

    describe('getM365Status', () => {
      it('should fetch M365 connection status', async () => {
        localStorage.getItem.mockReturnValue('mock-token')

        const mockStatus = {
          connected: true,
          account: 'user@company.com'
        }

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatus
        })

        const result = await api.getM365Status()

        expect(result).toEqual(mockStatus)
      })
    })

    describe('disconnectM365', () => {
      it('should disconnect M365 account', async () => {
        localStorage.getItem.mockReturnValue('mock-token')

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.disconnectM365()

        expect(result).toEqual({ success: true })
      })
    })
  })

  describe('Confirmation Workflow API', () => {
    describe('approveConfirmation', () => {
      it('should approve a confirmation request', async () => {
        localStorage.getItem.mockReturnValue('mock-token')

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.approveConfirmation('conf-123')

        expect(fetchMock).toHaveBeenCalledWith('/api/confirmations/conf-123/approve', {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer mock-token'
          }
        })
        expect(result).toEqual({ success: true })
      })
    })

    describe('rejectConfirmation', () => {
      it('should reject a confirmation request', async () => {
        localStorage.getItem.mockReturnValue('mock-token')

        fetchMock.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true })
        })

        const result = await api.rejectConfirmation('conf-123', 'Not needed')

        expect(fetchMock).toHaveBeenCalledWith('/api/confirmations/conf-123/reject', {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer mock-token',
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ reason: 'Not needed' })
        })
        expect(result).toEqual({ success: true })
      })
    })
  })

  describe('Error Handling', () => {
    it('should handle 401 unauthorized errors', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: async () => 'Unauthorized'
      })

      await expect(api.fetchSessionSummary('test'))
        .rejects.toThrow('Unauthorized')
    })

    it('should handle 500 server errors', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: async () => 'Internal server error'
      })

      await expect(api.createIntent({ id: 'test' }))
        .rejects.toThrow('Internal server error')
    })

    it('should handle empty error messages', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        text: async () => ''
      })

      await expect(api.listProviders())
        .rejects.toThrow('Failed to load providers')
    })
  })
})
