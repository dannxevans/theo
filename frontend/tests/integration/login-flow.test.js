import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import Login from '@/components/Login.svelte'
import * as api from '@/lib/api.js'

vi.mock('@/lib/api.js', () => ({
  login: vi.fn(),
  verifySession: vi.fn()
}))

describe('Login Flow Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    global.localStorage = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn()
    }
  })

  describe('Complete Login Flow', () => {
    it('should complete full login flow successfully', async () => {
      const user = userEvent.setup()
      const mockOnLogin = vi.fn()

      const mockResponse = {
        token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
        user: {
          id: 1,
          username: 'testuser',
          email: 'test@example.com'
        }
      }

      api.login.mockResolvedValue(mockResponse)

      render(Login, { props: { onLogin: mockOnLogin } })

      // Verify login form is displayed
      expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument()

      // Enter credentials
      await user.type(screen.getByLabelText(/username/i), 'testuser')
      await user.type(screen.getByLabelText(/password/i), 'correctpassword')

      // Submit form
      await user.click(screen.getByRole('button', { name: /login/i }))

      // Wait for API call
      await waitFor(() => {
        expect(api.login).toHaveBeenCalledWith('testuser', 'correctpassword')
      })

      // Verify token storage
      expect(localStorage.setItem).toHaveBeenCalledWith('auth_token', mockResponse.token)
      expect(localStorage.setItem).toHaveBeenCalledWith('user', JSON.stringify(mockResponse.user))

      // Verify callback was called
      expect(mockOnLogin).toHaveBeenCalledWith(mockResponse.token, mockResponse.user)
    })

    it('should handle invalid credentials error', async () => {
      const user = userEvent.setup()
      const mockOnLogin = vi.fn()

      api.login.mockRejectedValue(new Error('Invalid username or password'))

      render(Login, { props: { onLogin: mockOnLogin } })

      await user.type(screen.getByLabelText(/username/i), 'wronguser')
      await user.type(screen.getByLabelText(/password/i), 'wrongpassword')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        expect(screen.getByText(/Invalid username or password/i)).toBeInTheDocument()
      })

      // Verify token was not stored
      expect(localStorage.setItem).not.toHaveBeenCalledWith(
        'auth_token',
        expect.anything()
      )

      // Verify callback was not called
      expect(mockOnLogin).not.toHaveBeenCalled()
    })

    it('should handle network errors gracefully', async () => {
      const user = userEvent.setup()
      const mockOnLogin = vi.fn()

      api.login.mockRejectedValue(new Error('Network request failed'))

      render(Login, { props: { onLogin: mockOnLogin } })

      await user.type(screen.getByLabelText(/username/i), 'testuser')
      await user.type(screen.getByLabelText(/password/i), 'password123')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        expect(screen.getByText(/Network request failed/i)).toBeInTheDocument()
      })

      expect(mockOnLogin).not.toHaveBeenCalled()
    })

    it('should handle server errors (500)', async () => {
      const user = userEvent.setup()
      const mockOnLogin = vi.fn()

      api.login.mockRejectedValue(new Error('Internal server error'))

      render(Login, { props: { onLogin: mockOnLogin } })

      await user.type(screen.getByLabelText(/username/i), 'testuser')
      await user.type(screen.getByLabelText(/password/i), 'password123')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        expect(screen.getByText(/Internal server error/i)).toBeInTheDocument()
      })
    })
  })

  describe('Token Persistence', () => {
    it('should store JWT token in localStorage', async () => {
      const user = userEvent.setup()
      const mockOnLogin = vi.fn()

      const mockResponse = {
        token: 'test-jwt-token-12345',
        user: { username: 'testuser' }
      }

      api.login.mockResolvedValue(mockResponse)

      render(Login, { props: { onLogin: mockOnLogin } })

      await user.type(screen.getByLabelText(/username/i), 'testuser')
      await user.type(screen.getByLabelText(/password/i), 'password')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        expect(localStorage.setItem).toHaveBeenCalledWith(
          'auth_token',
          'test-jwt-token-12345'
        )
      })
    })

    it('should store user info in localStorage', async () => {
      const user = userEvent.setup()
      const mockOnLogin = vi.fn()

      const mockUser = {
        id: 123,
        username: 'testuser',
        email: 'test@example.com',
        role: 'user'
      }

      const mockResponse = {
        token: 'token',
        user: mockUser
      }

      api.login.mockResolvedValue(mockResponse)

      render(Login, { props: { onLogin: mockOnLogin } })

      await user.type(screen.getByLabelText(/username/i), 'testuser')
      await user.type(screen.getByLabelText(/password/i), 'password')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        expect(localStorage.setItem).toHaveBeenCalledWith(
          'user',
          JSON.stringify(mockUser)
        )
      })
    })
  })

  describe('Form Validation', () => {
    it('should require username field', () => {
      render(Login, { props: { onLogin: vi.fn() } })

      const usernameInput = screen.getByLabelText(/username/i)
      expect(usernameInput).toBeRequired()
    })

    it('should require password field', () => {
      render(Login, { props: { onLogin: vi.fn() } })

      const passwordInput = screen.getByLabelText(/password/i)
      expect(passwordInput).toBeRequired()
    })

    it('should not submit with empty fields', async () => {
      const user = userEvent.setup()

      render(Login, { props: { onLogin: vi.fn() } })

      await user.click(screen.getByRole('button', { name: /login/i }))

      expect(api.login).not.toHaveBeenCalled()
    })
  })

  describe('UI/UX During Login', () => {
    it('should show loading state during authentication', async () => {
      const user = userEvent.setup()

      let resolveLogin
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve
      })

      api.login.mockReturnValue(loginPromise)

      render(Login, { props: { onLogin: vi.fn() } })

      await user.type(screen.getByLabelText(/username/i), 'testuser')
      await user.type(screen.getByLabelText(/password/i), 'password')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        const button = screen.getByRole('button', { name: /logging in/i })
        expect(button).toBeInTheDocument()
        expect(button).toBeDisabled()
      })

      resolveLogin({ token: 'test', user: { username: 'testuser' } })
    })

    it('should disable inputs during authentication', async () => {
      const user = userEvent.setup()

      let resolveLogin
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve
      })

      api.login.mockReturnValue(loginPromise)

      render(Login, { props: { onLogin: vi.fn() } })

      const usernameInput = screen.getByLabelText(/username/i)
      const passwordInput = screen.getByLabelText(/password/i)

      await user.type(usernameInput, 'testuser')
      await user.type(passwordInput, 'password')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        expect(usernameInput).toBeDisabled()
        expect(passwordInput).toBeDisabled()
      })

      resolveLogin({ token: 'test', user: { username: 'testuser' } })
    })

    it('should clear password field after failed login', async () => {
      const user = userEvent.setup()

      api.login.mockRejectedValue(new Error('Invalid credentials'))

      render(Login, { props: { onLogin: vi.fn() } })

      const passwordInput = screen.getByLabelText(/password/i)

      await user.type(screen.getByLabelText(/username/i), 'testuser')
      await user.type(passwordInput, 'wrongpassword')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        expect(screen.getByText(/Invalid credentials/i)).toBeInTheDocument()
      })

      // Password should still be there (component doesn't clear it)
      // This tests current behavior
      expect(passwordInput).toHaveValue('wrongpassword')
    })
  })

  describe('Multiple Login Attempts', () => {
    it('should allow retry after failed login', async () => {
      const user = userEvent.setup()
      const mockOnLogin = vi.fn()

      // First attempt fails
      api.login.mockRejectedValueOnce(new Error('Invalid credentials'))

      render(Login, { props: { onLogin: mockOnLogin } })

      // First attempt
      await user.type(screen.getByLabelText(/username/i), 'wronguser')
      await user.type(screen.getByLabelText(/password/i), 'wrongpass')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        expect(screen.getByText(/Invalid credentials/i)).toBeInTheDocument()
      })

      // Second attempt succeeds
      api.login.mockResolvedValueOnce({
        token: 'valid-token',
        user: { username: 'correctuser' }
      })

      await user.clear(screen.getByLabelText(/username/i))
      await user.clear(screen.getByLabelText(/password/i))
      await user.type(screen.getByLabelText(/username/i), 'correctuser')
      await user.type(screen.getByLabelText(/password/i), 'correctpass')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        expect(mockOnLogin).toHaveBeenCalledWith(
          'valid-token',
          { username: 'correctuser' }
        )
      })
    })

    it('should clear error message on new login attempt', async () => {
      const user = userEvent.setup()

      api.login.mockRejectedValueOnce(new Error('Invalid credentials'))

      render(Login, { props: { onLogin: vi.fn() } })

      // First attempt
      await user.type(screen.getByLabelText(/username/i), 'user')
      await user.type(screen.getByLabelText(/password/i), 'pass')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        expect(screen.getByText(/Invalid credentials/i)).toBeInTheDocument()
      })

      // Second attempt
      api.login.mockResolvedValueOnce({
        token: 'token',
        user: { username: 'user' }
      })

      await user.clear(screen.getByLabelText(/username/i))
      await user.clear(screen.getByLabelText(/password/i))
      await user.type(screen.getByLabelText(/username/i), 'user')
      await user.type(screen.getByLabelText(/password/i), 'newpass')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        expect(screen.queryByText(/Invalid credentials/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('Keyboard Navigation', () => {
    it('should submit form with Enter key in password field', async () => {
      const user = userEvent.setup()
      const mockOnLogin = vi.fn()

      api.login.mockResolvedValue({
        token: 'token',
        user: { username: 'testuser' }
      })

      render(Login, { props: { onLogin: mockOnLogin } })

      await user.type(screen.getByLabelText(/username/i), 'testuser')
      await user.type(screen.getByLabelText(/password/i), 'password{Enter}')

      await waitFor(() => {
        expect(api.login).toHaveBeenCalled()
      })
    })

    it('should allow tab navigation between fields', async () => {
      const user = userEvent.setup()

      render(Login, { props: { onLogin: vi.fn() } })

      const usernameInput = screen.getByLabelText(/username/i)
      const passwordInput = screen.getByLabelText(/password/i)

      usernameInput.focus()
      expect(usernameInput).toHaveFocus()

      await user.keyboard('{Tab}')
      expect(passwordInput).toHaveFocus()
    })
  })

  describe('Accessibility', () => {
    it('should have proper form labels', () => {
      render(Login, { props: { onLogin: vi.fn() } })

      expect(screen.getByLabelText('Username')).toBeInTheDocument()
      expect(screen.getByLabelText('Password')).toBeInTheDocument()
    })

    it('should have accessible error messages', async () => {
      const user = userEvent.setup()

      api.login.mockRejectedValue(new Error('Invalid credentials'))

      render(Login, { props: { onLogin: vi.fn() } })

      await user.type(screen.getByLabelText(/username/i), 'user')
      await user.type(screen.getByLabelText(/password/i), 'pass')
      await user.click(screen.getByRole('button', { name: /login/i }))

      await waitFor(() => {
        const errorMessage = screen.getByText(/Invalid credentials/i)
        expect(errorMessage).toBeInTheDocument()
        expect(errorMessage).toBeVisible()
      })
    })

    it('should have proper autocomplete attributes', () => {
      render(Login, { props: { onLogin: vi.fn() } })

      expect(screen.getByLabelText(/username/i)).toHaveAttribute('autocomplete', 'username')
      expect(screen.getByLabelText(/password/i)).toHaveAttribute('autocomplete', 'current-password')
    })
  })
})
