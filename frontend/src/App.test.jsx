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

test('shows answer after successful search', async () => {
  global.fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ answer: 'Chrono is a physics simulation library.' }),
  })
  render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'What is Chrono?' } })
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  await waitFor(() =>
    expect(screen.getByText('Chrono is a physics simulation library.')).toBeInTheDocument()
  )
})

test('calls fetch with correct payload', async () => {
  global.fetch.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ answer: 'Some answer.' }),
  })
  render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'How do I use PyChrono?' } })
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1))
  expect(global.fetch).toHaveBeenCalledWith('/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: 'How do I use PyChrono?', top_k: 5, model: 'claude-opus-4-8' }),
  })
})

test('shows error message on network failure', async () => {
  global.fetch.mockRejectedValueOnce(new Error('Network error'))
  render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'What is Chrono?' } })
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  await waitFor(() =>
    expect(screen.getByText('Something went wrong. Please try again.')).toBeInTheDocument()
  )
})

test('shows error message on non-2xx response', async () => {
  global.fetch.mockResolvedValueOnce({ ok: false, status: 500 })
  render(<App />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'What is Chrono?' } })
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  await waitFor(() =>
    expect(screen.getByText('Something went wrong. Please try again.')).toBeInTheDocument()
  )
})

test('does not fire fetch when query is empty', () => {
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  expect(global.fetch).not.toHaveBeenCalled()
})
