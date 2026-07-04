import { render, screen } from '@testing-library/react'
import { AnswerCard } from './AnswerCard'

test('renders nothing in initial state', () => {
  const { container } = render(<AnswerCard result={null} loading={false} error={null} />)
  expect(container.firstChild).toBeNull()
})

test('shows loading indicator when loading is true', () => {
  render(<AnswerCard result={null} loading={true} error={null} />)
  expect(screen.getByRole('status')).toBeInTheDocument()
})

test('shows error message when error is provided', () => {
  render(<AnswerCard result={null} loading={false} error="Something went wrong." />)
  expect(screen.getByText('Something went wrong.')).toBeInTheDocument()
})

test('renders answer text when provided', () => {
  render(<AnswerCard result={{ answer: 'Chrono is a physics library.' }} loading={false} error={null} />)
  expect(screen.getByText('Chrono is a physics library.')).toBeInTheDocument()
})

test('renders sources and the answered-by footer', () => {
  const result = {
    answer: 'Use ChBody.',
    sources: ['src/chrono/ChBody.cpp:12', 'src/demos/python/demo.py:1'],
    insufficient: false,
    model: 'gpt-4o-mini',
    provider: 'openai',
  }
  render(<AnswerCard result={result} loading={false} error={null} />)
  expect(screen.getByText('Sources')).toBeInTheDocument()
  expect(screen.getByText('src/chrono/ChBody.cpp:12')).toBeInTheDocument()
  expect(screen.getByText(/answered by openai\/gpt-4o-mini · grounded in 2 sources/)).toBeInTheDocument()
})

test('shows the abstention notice and no footer when insufficient', () => {
  const result = { answer: 'No relevant context found.', sources: [], insufficient: true, model: null }
  render(<AnswerCard result={result} loading={false} error={null} />)
  expect(screen.getByText(/no LLM was called/i)).toBeInTheDocument()
  expect(screen.queryByText(/answered by/)).not.toBeInTheDocument()
})

test('does not show error when loading', () => {
  render(<AnswerCard result={null} loading={true} error="Something went wrong." />)
  expect(screen.queryByText('Something went wrong.')).not.toBeInTheDocument()
})
