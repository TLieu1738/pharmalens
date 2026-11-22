import { useEffect, useState } from 'react'
import { api } from '@/services/api'
import type { EvidenceRecord } from '@/types/research'

export function useEvidence(sessionId: string | undefined, enabled: boolean) {
  const [records, setRecords] = useState<EvidenceRecord[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId || !enabled) return
    let cancelled = false
    api
      .getEvidence(sessionId)
      .then((r) => !cancelled && setRecords(r))
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [sessionId, enabled])

  return { records, error }
}
