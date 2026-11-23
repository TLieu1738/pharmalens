import { useEffect, useState } from 'react'
import { api } from '@/services/api'
import type { LibraryRecord } from '@/types/research'

const TTL_MS = 30_000
let cache: { at: number; data: LibraryRecord[] } | null = null
let inflight: Promise<LibraryRecord[]> | null = null

/** Drop the cached library (call after starting new research or signing out). */
export function invalidateLibrary(): void {
  cache = null
}

function load(): Promise<LibraryRecord[]> {
  if (cache && Date.now() - cache.at < TTL_MS) return Promise.resolve(cache.data)
  inflight ??= api
    .getLibrary()
    .then((data) => {
      cache = { at: Date.now(), data }
      return data
    })
    .finally(() => {
      inflight = null
    })
  return inflight
}

/** Every evidence record retrieved across the signed-in user's sessions (shared, briefly cached). */
export function useLibrary(): { records: LibraryRecord[] | null; error: string | null } {
  const [records, setRecords] = useState<LibraryRecord[] | null>(cache?.data ?? null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    load()
      .then((data) => !cancelled && setRecords(data))
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [])

  return { records, error }
}
