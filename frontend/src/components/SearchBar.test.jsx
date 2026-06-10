import { render, screen, fireEvent } from '@testing-library/react'
import { SearchBar } from './SearchBar'

test('submit button is disabled when value is empty', () => {
  render(<SearchBar value="" onChange={() => {}} onSubmit={() => {}} disabled={false} />)
  expect(screen.getByRole('button', { name: /search/i })).toBeDisabled()
})

test('submit button is disabled when value is only whitespace', () => {
  render(<SearchBar value="   " onChange={() => {}} onSubmit={() => {}} disabled={false} />)
  expect(screen.getByRole('button', { name: /search/i })).toBeDisabled()
})

test('submit button is enabled when value has content', () => {
  render(<SearchBar value="hello" onChange={() => {}} onSubmit={() => {}} disabled={false} />)
  expect(screen.getByRole('button', { name: /search/i })).not.toBeDisabled()
})

test('submit button is disabled when disabled prop is true', () => {
  render(<SearchBar value="hello" onChange={() => {}} onSubmit={() => {}} disabled={true} />)
  expect(screen.getByRole('button', { name: /search/i })).toBeDisabled()
})

test('calls onChange when input changes', () => {
  const onChange = vi.fn()
  render(<SearchBar value="" onChange={onChange} onSubmit={() => {}} disabled={false} />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'test' } })
  expect(onChange).toHaveBeenCalledWith('test')
})

test('calls onSubmit when button is clicked', () => {
  const onSubmit = vi.fn()
  render(<SearchBar value="hello" onChange={() => {}} onSubmit={onSubmit} disabled={false} />)
  fireEvent.click(screen.getByRole('button', { name: /search/i }))
  expect(onSubmit).toHaveBeenCalledTimes(1)
})

test('calls onSubmit when Enter key is pressed', () => {
  const onSubmit = vi.fn()
  render(<SearchBar value="hello" onChange={() => {}} onSubmit={onSubmit} disabled={false} />)
  fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' })
  expect(onSubmit).toHaveBeenCalledTimes(1)
})

test('does not call onSubmit on other keys', () => {
  const onSubmit = vi.fn()
  render(<SearchBar value="hello" onChange={() => {}} onSubmit={onSubmit} disabled={false} />)
  fireEvent.keyDown(screen.getByRole('textbox'), { key: 'a' })
  expect(onSubmit).not.toHaveBeenCalled()
})
