import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import Login from '@/components/Login.svelte'
import * as api from '@/lib/api.js'

// Mock the API module
vi.mock('@/lib/api.js', () => ({
  login: vi.fn()
}))

describe('Login Component', () => {
  let mockOnLogin

  beforeEach(() => {
    mockOnLogin = vi.fn()
    vi.clearAllMocks()

    // Mock localStorage
    global.localStorage = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn()
    }
  })

  it('should render login form', () => {
    render(Login, { props: { onLogin: mockOnLogin } })

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument()
  })

  it('should display logo', () => {
    render(Login, { props: { onLogin: mockOnLogin } })

    const logo = screen.getByAltText('THEO')
    expect(logo).toBeInTheDocument()
    expect(logo).toHaveAttribute('src', '/logo.svg')
  })

  it('should display GitHub link', () => {
    render(Login, { props: { onLogin: mockOnLogin } })

    const githubLink = screen.getByLabelText('View THEO on GitHub')
    expect(githubLink).toBeInTheDocument()
    expect(githubLink).toHaveAttribute('href', 'https://github.com/dannxevans/theo')
    expect(githubLink).toHaveAttribute('target', '_blank')
  })

  it('should have username and password fields with correct attributes', () => {
    render(Login, { props: { onLogin: mockOnLogin } })

    const usernameInput = screen.getByLabelText(/username/i)
    expect(usernameInput).toHaveAttribute('type', 'text')
    expect(usernameInput).toHaveAttribute('id', 'username')
    expect(usernameInput).toHaveAttribute('placeholder', 'Enter username')
    expect(usernameInput).toHaveAttribute('autocomplete', 'username')

    const passwordInput = screen.getByLabelText(/password/i)
    expect(passwordInput).toHaveAttribute('type', 'password')
    expect(passwordInput).toHaveAttribute('id', 'password')
    expect(passwordInput).toHaveAttribute('placeholder', 'Enter password')
    expect(passwordInput).toHaveAttribute('autocomplete', 'current-password')
  })

  it('should handle successful login', async () => {
    const user = userEvent.setup()
    const mockResponse = {
      token: 'mock-jwt-token',
      user: { username: 'testuser', id: 1 }
    }

    api.login.mockResolvedValueOnce(mockResponse)

    render(Login, { props: { onLogin: mockOnLogin } })

    const usernameInput = screen.getByLabelText(/username/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const loginButton = screen.getByRole('button', { name: /login/i })

    await user.type(usernameInput, 'testuser')
    await user.type(passwordInput, 'password123')
    await user.click(loginButton)

    await waitFor(() => {
      expect(api.login).toHaveBeenCalledWith('testuser', 'password123')
    })

    expect(localStorage.setItem).toHaveBeenCalledWith('auth_token', 'mock-jwt-token')
    expect(localStorage.setItem).toHaveBeenCalledWith('user', JSON.stringify(mockResponse.user))
    expect(mockOnLogin).toHaveBeenCalledWith('mock-jwt-token', mockResponse.user)
  })

  it('should display error message on failed login', async () => {
    const user = userEvent.setup()

    api.login.mockRejectedValueOnce(new Error('Invalid credentials'))

    render(Login, { props: { onLogin: mockOnLogin } })

    const usernameInput = screen.getByLabelText(/username/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const loginButton = screen.getByRole('button', { name: /login/i })

    await user.type(usernameInput, 'baduser')
    await user.type(passwordInput, 'badpass')
    await user.click(loginButton)

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
    })

    expect(mockOnLogin).not.toHaveBeenCalled()
  })

  it('should show loading state during login', async () => {
    const user = userEvent.setup()

    // Create a promise we can control
    let resolveLogin
    const loginPromise = new Promise((resolve) => {
      resolveLogin = resolve
    })

    api.login.mockReturnValueOnce(loginPromise)

    render(Login, { props: { onLogin: mockOnLogin } })

    const usernameInput = screen.getByLabelText(/username/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const loginButton = screen.getByRole('button', { name: /login/i })

    await user.type(usernameInput, 'testuser')
    await user.type(passwordInput, 'password123')
    await user.click(loginButton)

    // Check loading state
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /logging in/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /logging in/i })).toBeDisabled()
    })

    // Resolve the login
    resolveLogin({ token: 'test', user: { username: 'testuser' } })

    await waitFor(() => {
      expect(mockOnLogin).toHaveBeenCalled()
    })
  })

  it('should disable inputs during login', async () => {
    const user = userEvent.setup()

    let resolveLogin
    const loginPromise = new Promise((resolve) => {
      resolveLogin = resolve
    })

    api.login.mockReturnValueOnce(loginPromise)

    render(Login, { props: { onLogin: mockOnLogin } })

    const usernameInput = screen.getByLabelText(/username/i)
    const passwordInput = screen.getByLabelText(/password/i)
    const loginButton = screen.getByRole('button', { name: /login/i })

    await user.type(usernameInput, 'testuser')
    await user.type(passwordInput, 'password123')
    await user.click(loginButton)

    await waitFor(() => {
      expect(usernameInput).toBeDisabled()
      expect(passwordInput).toBeDisabled()
    })

    resolveLogin({ token: 'test', user: { username: 'testuser' } })
  })

  it('should submit form on Enter key in password field', async () => {
    const user = userEvent.setup()
    const mockResponse = {
      token: 'mock-jwt-token',
      user: { username: 'testuser' }
    }

    api.login.mockResolvedValueOnce(mockResponse)

    render(Login, { props: { onLogin: mockOnLogin } })

    const usernameInput = screen.getByLabelText(/username/i)
    const passwordInput = screen.getByLabelText(/password/i)

    await user.type(usernameInput, 'testuser')
    await user.type(passwordInput, 'password123')
    await user.keyboard('{Enter}')

    await waitFor(() => {
      expect(api.login).toHaveBeenCalledWith('testuser', 'password123')
    })
  })

  it('should submit form when clicking submit button', async () => {
    const user = userEvent.setup()
    const mockResponse = {
      token: 'mock-jwt-token',
      user: { username: 'testuser' }
    }

    api.login.mockResolvedValueOnce(mockResponse)

    render(Login, { props: { onLogin: mockOnLogin } })

    await user.type(screen.getByLabelText(/username/i), 'testuser')
    await user.type(screen.getByLabelText(/password/i), 'password123')

    const form = screen.getByRole('button', { name: /login/i }).closest('form')
    await fireEvent.submit(form)

    await waitFor(() => {
      expect(api.login).toHaveBeenCalledWith('testuser', 'password123')
    })
  })

  it('should clear fields on mount', () => {
    const { component } = render(Login, { props: { onLogin: mockOnLogin } })

    const usernameInput = screen.getByLabelText(/username/i)
    const passwordInput = screen.getByLabelText(/password/i)

    expect(usernameInput.value).toBe('')
    expect(passwordInput.value).toBe('')
  })

  it('should require username and password fields', () => {
    render(Login, { props: { onLogin: mockOnLogin } })

    const usernameInput = screen.getByLabelText(/username/i)
    const passwordInput = screen.getByLabelText(/password/i)

    expect(usernameInput).toBeRequired()
    expect(passwordInput).toBeRequired()
  })

  it('should handle network errors gracefully', async () => {
    const user = userEvent.setup()

    api.login.mockRejectedValueOnce(new Error('Network error'))

    render(Login, { props: { onLogin: mockOnLogin } })

    await user.type(screen.getByLabelText(/username/i), 'testuser')
    await user.type(screen.getByLabelText(/password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /login/i }))

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('should display default error message when error has no message', async () => {
    const user = userEvent.setup()

    api.login.mockRejectedValueOnce({ message: '' })

    render(Login, { props: { onLogin: mockOnLogin } })

    await user.type(screen.getByLabelText(/username/i), 'testuser')
    await user.type(screen.getByLabelText(/password/i), 'password123')
    await user.click(screen.getByRole('button', { name: /login/i }))

    await waitFor(() => {
      expect(screen.getByText('Login failed')).toBeInTheDocument()
    })
  })

  it('should clear error message on new login attempt', async () => {
    const user = userEvent.setup()

    // First attempt - fails
    api.login.mockRejectedValueOnce(new Error('Invalid credentials'))

    render(Login, { props: { onLogin: mockOnLogin } })

    await user.type(screen.getByLabelText(/username/i), 'baduser')
    await user.type(screen.getByLabelText(/password/i), 'badpass')
    await user.click(screen.getByRole('button', { name: /login/i }))

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeInTheDocument()
    })

    // Second attempt - should clear error
    api.login.mockResolvedValueOnce({
      token: 'token',
      user: { username: 'gooduser' }
    })

    await user.clear(screen.getByLabelText(/username/i))
    await user.clear(screen.getByLabelText(/password/i))
    await user.type(screen.getByLabelText(/username/i), 'gooduser')
    await user.type(screen.getByLabelText(/password/i), 'goodpass')
    await user.click(screen.getByRole('button', { name: /login/i }))

    await waitFor(() => {
      expect(screen.queryByText('Invalid credentials')).not.toBeInTheDocument()
    })
  })

  it('should have accessible form labels', () => {
    render(Login, { props: { onLogin: mockOnLogin } })

    const usernameLabel = screen.getByText('Username')
    const passwordLabel = screen.getByText('Password')

    expect(usernameLabel).toHaveAttribute('for', 'username')
    expect(passwordLabel).toHaveAttribute('for', 'password')
  })

  it('should display project subtitle', () => {
    render(Login, { props: { onLogin: mockOnLogin } })

    expect(screen.getByText(/Multi-Modal Artificial Intelligence Project/i)).toBeInTheDocument()
  })
})
