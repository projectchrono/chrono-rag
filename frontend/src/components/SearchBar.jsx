import styles from './SearchBar.module.css'

export function SearchBar({ value, onChange, onSubmit, disabled }) {
  function handleKeyDown(e) {
    if (e.key === 'Enter') onSubmit()
  }

  return (
    <div className={styles.wrapper}>
      <input
        className={styles.input}
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about Chrono or PyChrono..."
        disabled={disabled}
      />
      <button
        className={styles.button}
        onClick={onSubmit}
        disabled={disabled || !value.trim()}
      >
        Search
      </button>
    </div>
  )
}
