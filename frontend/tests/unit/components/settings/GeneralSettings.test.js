import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import GeneralSettings from '@/components/settings/GeneralSettings.svelte'
import * as api from '@/lib/api.js'

vi.mock('@/lib/api.js', () => ({
  updateSystemPromptConfig: vi.fn()
}))

describe('GeneralSettings Component', () => {
  const defaultConfig = {
    persona_name: 'THEO',
    tone: 'professional, conversational, direct',
    style_rules: '',
    custom_instructions: ''
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render system prompt configuration form', () => {
    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    expect(screen.getByText('System Prompt Configuration')).toBeInTheDocument()
    expect(screen.getByLabelText('Persona Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Tone')).toBeInTheDocument()
    expect(screen.getByLabelText('Style Rules')).toBeInTheDocument()
    expect(screen.getByLabelText(/Custom Instructions/i)).toBeInTheDocument()
  })

  it('should display current configuration values', () => {
    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    expect(screen.getByLabelText('Persona Name')).toHaveValue('THEO')
    expect(screen.getByLabelText('Tone')).toHaveValue('professional, conversational, direct')
  })

  it('should allow editing persona name', async () => {
    const user = userEvent.setup()

    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const input = screen.getByLabelText('Persona Name')
    await user.clear(input)
    await user.type(input, 'ASSISTANT')

    expect(input).toHaveValue('ASSISTANT')
  })

  it('should allow editing tone', async () => {
    const user = userEvent.setup()

    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const input = screen.getByLabelText('Tone')
    await user.clear(input)
    await user.type(input, 'friendly, casual')

    expect(input).toHaveValue('friendly, casual')
  })

  it('should allow editing style rules', async () => {
    const user = userEvent.setup()

    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const textarea = screen.getByLabelText('Style Rules')
    await user.type(textarea, '- Be concise\n- Use bullet points')

    expect(textarea).toHaveValue('- Be concise\n- Use bullet points')
  })

  it('should allow editing custom instructions', async () => {
    const user = userEvent.setup()

    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const textarea = screen.getByLabelText(/Custom Instructions/i)
    await user.type(textarea, 'Always ask for clarification')

    expect(textarea).toHaveValue('Always ask for clarification')
  })

  it('should save configuration on button click', async () => {
    const user = userEvent.setup()

    api.updateSystemPromptConfig.mockResolvedValue({ success: true })

    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const saveButton = screen.getByRole('button', { name: /save settings/i })
    await user.click(saveButton)

    await waitFor(() => {
      expect(api.updateSystemPromptConfig).toHaveBeenCalledWith(defaultConfig)
    })
  })

  it('should show saving state when submitting', async () => {
    const user = userEvent.setup()

    let resolveSave
    const savePromise = new Promise((resolve) => {
      resolveSave = resolve
    })

    api.updateSystemPromptConfig.mockReturnValue(savePromise)

    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const saveButton = screen.getByRole('button', { name: /save settings/i })
    await user.click(saveButton)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /saving/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled()
    })

    resolveSave({ success: true })
  })

  it('should show success message after saving', async () => {
    const user = userEvent.setup()

    api.updateSystemPromptConfig.mockResolvedValue({ success: true })

    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const saveButton = screen.getByRole('button', { name: /save settings/i })
    await user.click(saveButton)

    await waitFor(() => {
      expect(screen.getByText(/Settings saved successfully/i)).toBeInTheDocument()
    })
  })

  it('should hide success message after 3 seconds', async () => {
    const user = userEvent.setup()
    vi.useFakeTimers()

    api.updateSystemPromptConfig.mockResolvedValue({ success: true })

    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const saveButton = screen.getByRole('button', { name: /save settings/i })
    await user.click(saveButton)

    await waitFor(() => {
      expect(screen.getByText(/Settings saved successfully/i)).toBeInTheDocument()
    })

    vi.advanceTimersByTime(3000)

    await waitFor(() => {
      expect(screen.queryByText(/Settings saved successfully/i)).not.toBeInTheDocument()
    })

    vi.useRealTimers()
  })

  it('should show error message on save failure', async () => {
    const user = userEvent.setup()

    api.updateSystemPromptConfig.mockRejectedValue(new Error('Network error'))

    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const saveButton = screen.getByRole('button', { name: /save settings/i })
    await user.click(saveButton)

    await waitFor(() => {
      expect(screen.getByText(/Error: Network error/i)).toBeInTheDocument()
    })
  })

  it('should have proper field placeholders', () => {
    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    expect(screen.getByPlaceholderText('e.g., THEO')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g., professional, conversational, direct')).toBeInTheDocument()
  })

  it('should display helper text for fields', () => {
    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    expect(screen.getByText(/The name your AI assistant will identify as/i)).toBeInTheDocument()
    expect(screen.getByText(/The overall tone and style of responses/i)).toBeInTheDocument()
    expect(screen.getByText(/Bullet-pointed list of style guidelines/i)).toBeInTheDocument()
    expect(screen.getByText(/Any extra instructions or preferences/i)).toBeInTheDocument()
  })

  it('should have correct field IDs for accessibility', () => {
    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    expect(screen.getByLabelText('Persona Name')).toHaveAttribute('id', 'persona-name')
    expect(screen.getByLabelText('Tone')).toHaveAttribute('id', 'tone')
    expect(screen.getByLabelText('Style Rules')).toHaveAttribute('id', 'style-rules')
    expect(screen.getByLabelText(/Custom Instructions/i)).toHaveAttribute('id', 'custom-instructions')
  })

  it('should preserve edited values on save error', async () => {
    const user = userEvent.setup()

    api.updateSystemPromptConfig.mockRejectedValue(new Error('Save failed'))

    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const personaInput = screen.getByLabelText('Persona Name')
    await user.clear(personaInput)
    await user.type(personaInput, 'MODIFIED')

    const saveButton = screen.getByRole('button', { name: /save settings/i })
    await user.click(saveButton)

    await waitFor(() => {
      expect(screen.getByText(/Error:/i)).toBeInTheDocument()
    })

    expect(personaInput).toHaveValue('MODIFIED')
  })

  it('should call API with updated values', async () => {
    const user = userEvent.setup()

    api.updateSystemPromptConfig.mockResolvedValue({ success: true })

    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    await user.clear(screen.getByLabelText('Persona Name'))
    await user.type(screen.getByLabelText('Persona Name'), 'ASSISTANT')

    await user.clear(screen.getByLabelText('Tone'))
    await user.type(screen.getByLabelText('Tone'), 'friendly')

    await user.type(screen.getByLabelText('Style Rules'), 'Be brief')

    await user.click(screen.getByRole('button', { name: /save settings/i }))

    await waitFor(() => {
      expect(api.updateSystemPromptConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          persona_name: 'ASSISTANT',
          tone: 'friendly',
          style_rules: 'Be brief'
        })
      )
    })
  })

  it('should have multiline textarea for style rules', () => {
    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const textarea = screen.getByLabelText('Style Rules')
    expect(textarea).toHaveAttribute('rows', '6')
  })

  it('should have multiline textarea for custom instructions', () => {
    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    const textarea = screen.getByLabelText(/Custom Instructions/i)
    expect(textarea).toHaveAttribute('rows', '4')
  })

  it('should render subtitle', () => {
    render(GeneralSettings, { props: { systemPromptConfig: defaultConfig } })

    expect(screen.getByText(/Customize how THEO responds and behaves/i)).toBeInTheDocument()
  })

  it('should handle empty configuration gracefully', () => {
    const emptyConfig = {
      persona_name: '',
      tone: '',
      style_rules: '',
      custom_instructions: ''
    }

    render(GeneralSettings, { props: { systemPromptConfig: emptyConfig } })

    expect(screen.getByLabelText('Persona Name')).toHaveValue('')
    expect(screen.getByLabelText('Tone')).toHaveValue('')
    expect(screen.getByLabelText('Style Rules')).toHaveValue('')
    expect(screen.getByLabelText(/Custom Instructions/i)).toHaveValue('')
  })
})
