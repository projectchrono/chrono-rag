import { useState } from 'react'
import { SearchBar } from './components/SearchBar'
import { AnswerCard } from './components/AnswerCard'
import styles from './App.module.css'

export default function App() {
  const [query, setQuery] = useState('')
  const [answer, setAnswer] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const hasResult = answer !== null || error !== null || loading

  async function handleSubmit() {
    if (!query.trim()) return
    setLoading(true)
    setAnswer(null)
    setError(null)
    try {
      const res = await fetch('/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_k: 5 }),
      })
      if (!res.ok) throw new Error(`${res.status}`)
      const data = await res.json()
      setAnswer(data.answer)
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`${styles.page} ${hasResult ? styles.pageCompact : ''}`}>
      <header className={styles.header}>
        <h1 className={styles.title}>Chrono RAG</h1>
        <p className={styles.subtitle}>Ask anything about Chrono &amp; PyChrono</p>
      </header>
      <SearchBar
        value={query}
        onChange={setQuery}
        onSubmit={handleSubmit}
        disabled={loading}
      />
      <AnswerCard answer={answer} loading={loading} error={error} />
    </div>
  )
}
