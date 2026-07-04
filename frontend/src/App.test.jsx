import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from './App'

beforeEach(() => {
  global.fetch = vi.fn()
})

afterEach(() => {
  vi.restoreAllMocks()
})

test('renders title and search bar on initial load', () => {
  render(<App />)
  expect(screen.getByText('Chrono RAG')).toBeInTheDocument()
  expect(screen.getByRole('textbox')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument()
})

test('shows answer, sources, and answering model after successful search', async () => {
  global.fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => ({
      answer: 'Chrono is a physics simulation library.',
      sources: ['src/chrono/ChBody.cpp:12'],
      insufficient: false,
      model: 'claude-opus-4-8',
      provider: 'anthropic',
    }),
  })
  render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'What is Chrono?' } })
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  await waitFor(() =>
    expect(screen.getByText('Chrono is a physics simulation library.')).toBeInTheDocument()
  )
  expect(screen.getByText('src/chrono/ChBody.cpp:12')).toBeInTheDocument()
  expect(screen.getByText(/answered by anthropic\/claude-opus-4-8/)).toBeInTheDocument()
})

test('calls fetch with correct payload', async () => {
  global.fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ answer: 'Some answer.', sources: [], insufficient: false }),
  })
  render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'How do I use PyChrono?' } })
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1))
  expect(global.fetch).toHaveBeenCalledWith('/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: 'How do I use PyChrono?',
      top_k: 5,
      model: 'claude-opus-4-8',
      provider: 'anthropic',
    }),
  })
})

test('shows insufficient-evidence notice when retrieval abstains', async () => {
  global.fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => ({
      answer: 'I could not find relevant context for that query.',
      sources: [],
      insufficient: true,
      model: null,
      provider: null,
    }),
  })
  render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'how do I bake a pie' } })
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  await waitFor(() =>
    expect(screen.getByText(/no LLM was called/i)).toBeInTheDocument()
  )
})

test('shows backend-unreachable message on network failure', async () => {
  global.fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))
  render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'What is Chrono?' } })
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  await waitFor(() =>
    expect(screen.getByText(/Could not reach the chrono-rag backend/)).toBeInTheDocument()
  )
})

test('surfaces the backend error detail on non-2xx response', async () => {
  global.fetch.mockResolvedValueOnce({
    ok: false,
    status: 500,
    json: async () => ({ detail: 'the LLM call failed: the server has no valid API key' }),
  })
  render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'What is Chrono?' } })
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  await waitFor(() =>
    expect(screen.getByText(/no valid API key/)).toBeInTheDocument()
  )
})

test('falls back to a generic message when the error body is not JSON', async () => {
  global.fetch.mockResolvedValueOnce({
    ok: false,
    status: 502,
    json: async () => { throw new Error('not json') },
  })
  render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'What is Chrono?' } })
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  await waitFor(() =>
    expect(screen.getByText(/HTTP 502/)).toBeInTheDocument()
  )
})

test('does not fire fetch when query is empty', () => {
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  expect(global.fetch).not.toHaveBeenCalled()
})
