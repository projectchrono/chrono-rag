import styles from './SearchBar.module.css'

export function SearchBar({ value, onChange, onSubmit, disabled, models, model, onModelChange }) {
  function handleKeyDown(e) {
    if (e.key === 'Enter') onSubmit()
  }

  return (
    <div className={styles.container}>
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
      {models && (
        <div className={styles.modelRow}>
          <span className={styles.modelLabel}>Model</span>
          <div className={styles.toggle}>
            {models.map(m => (
              <button
                key={m.id}
                className={`${styles.toggleOption} ${model === m.id ? styles.toggleActive : ''}`}
                onClick={() => onModelChange(m.id)}
                disabled={disabled}
                type="button"
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
