import { useState } from 'react'
import { SearchBar } from './components/SearchBar'
import { AnswerCard } from './components/AnswerCard'
import styles from './App.module.css'

// The backend resolves provider/model; `id: null` means "use the provider's
// configured default" (for local servers the model is set via CHRONO_RAG_LLM_*).
const MODELS = [
  { key: 'anthropic', id: 'claude-opus-4-8', provider: 'anthropic', label: 'Claude Opus 4.8' },
  { key: 'openai',    id: 'gpt-4o-mini',     provider: 'openai',    label: 'GPT-4o mini' },
  { key: 'local',     id: null,              provider: 'local',     label: 'Local LLM' },
]

export default function App() {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [modelKey, setModelKey] = useState(MODELS[0].key)

  const hasResult = result !== null || error !== null || loading

  async function handleSubmit() {
    if (!query.trim()) return
    const selected = MODELS.find(m => m.key === modelKey)
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const res = await fetch('/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          top_k: 5,
          model: selected.id,
          provider: selected.provider,
        }),
      })
      if (!res.ok) {
        let detail = null
        try {
          detail = (await res.json()).detail
        } catch {
          // non-JSON error body; fall through to the generic message
        }
        throw new Error(detail || `The backend returned an error (HTTP ${res.status}).`)
      }
      setResult(await res.json())
    } catch (err) {
      if (err instanceof TypeError) {
        // fetch() network failure: the backend is not reachable at all
        setError('Could not reach the chrono-rag backend. Is it running on port 8000?')
      } else {
        setError(err.message)
      }
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
        models={MODELS}
        model={modelKey}
        onModelChange={setModelKey}
      />
      <AnswerCard result={result} loading={loading} error={error} />
    </div>
  )
}
