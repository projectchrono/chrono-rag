import ReactMarkdown from 'react-markdown'
import styles from './AnswerCard.module.css'

export function AnswerCard({ answer, loading, error }) {
  if (!answer && !loading && !error) return null

  return (
    <div className={styles.card}>
      {loading && (
        <div className={styles.spinnerWrapper}>
          <div role="status" aria-label="Loading" className={styles.spinner} />
        </div>
      )}
      {!loading && error && <p className={styles.error} role="alert">{error}</p>}
      {!loading && answer && (
        <div className={styles.answer}>
          <ReactMarkdown>{answer}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}
