import ReactMarkdown from 'react-markdown'
import styles from './AnswerCard.module.css'

export function AnswerCard({ result, loading, error }) {
  if (!result && !loading && !error) return null

  const sources = result?.sources ?? []

  return (
    <div className={styles.card}>
      {loading && (
        <div className={styles.spinnerWrapper}>
          <div role="status" aria-label="Loading" className={styles.spinner} />
        </div>
      )}
      {!loading && error && <p className={styles.error} role="alert">{error}</p>}
      {!loading && !error && result && (
        <>
          {result.insufficient && (
            <p className={styles.notice}>
              Nothing sufficiently relevant was found in the indexed Chrono code, so no
              LLM was called. Try a class or function name, or the exact error message.
            </p>
          )}
          <div className={styles.answer}>
            <ReactMarkdown>{result.answer}</ReactMarkdown>
          </div>
          {sources.length > 0 && (
            <div className={styles.sources}>
              <span className={styles.sourcesTitle}>Sources</span>
              <ul className={styles.sourceList}>
                {sources.map(s => (
                  <li key={s}><code>{s}</code></li>
                ))}
              </ul>
            </div>
          )}
          {result.model && (
            <p className={styles.footer}>
              answered by {result.provider}/{result.model}
              {sources.length > 0 && ` · grounded in ${sources.length} source${sources.length !== 1 ? 's' : ''}`}
            </p>
          )}
        </>
      )}
    </div>
  )
}
