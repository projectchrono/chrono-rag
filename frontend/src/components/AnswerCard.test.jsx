import { render, screen } from '@testing-library/react'
import { AnswerCard } from './AnswerCard'

test('renders nothing in initial state', () => {
  const { container } = render(<AnswerCard answer={null} loading={false} error={null} />)
  expect(container.firstChild).toBeNull()
})

test('shows loading indicator when loading is true', () => {
  render(<AnswerCard answer={null} loading={true} error={null} />)
  expect(screen.getByRole('status')).toBeInTheDocument()
})

test('shows error message when error is provided', () => {
  render(<AnswerCard answer={null} loading={false} error="Something went wrong. Please try again." />)
  expect(screen.getByText('Something went wrong. Please try again.')).toBeInTheDocument()
})

test('renders answer text when provided', () => {
  render(<AnswerCard answer="Chrono is a physics library." loading={false} error={null} />)
  expect(screen.getByText('Chrono is a physics library.')).toBeInTheDocument()
})

test('does not show error when loading', () => {
  render(<AnswerCard answer={null} loading={true} error="Something went wrong. Please try again." />)
  expect(screen.queryByText('Something went wrong. Please try again.')).not.toBeInTheDocument()
})
