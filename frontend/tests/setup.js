import '@testing-library/jest-dom'
import { expect } from 'vitest'

// Note: No manual cleanup - tests that need cleanup should handle it themselves

// Mock localStorage
const localStorageMock = {
  getItem: (key) => null,
  setItem: (key, value) => {},
  removeItem: (key) => {},
  clear: () => {}
}

global.localStorage = localStorageMock

// Mock fetch for API calls
global.fetch = async (url, options) => {
  console.warn(`Unmocked fetch call to ${url}`)
  return {
    ok: true,
    status: 200,
    json: async () => ({}),
    text: async () => ''
  }
}
