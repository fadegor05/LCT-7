import { useEffect, useState } from 'react'

export function App() {
  const [health, setHealth] = useState<string>('...')

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => setHealth(d.status))
      .catch(() => setHealth('error'))
  }, [])

  return (
    <main style={{ fontFamily: 'sans-serif', padding: 32 }}>
      <h1>LCT-7</h1>
      <p>
        Backend health: <b>{health}</b>
      </p>
    </main>
  )
}
