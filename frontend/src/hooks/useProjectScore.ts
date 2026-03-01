import { useEffect, useState } from 'react'

export interface ProjectScore {
  project: {
    id: number
    name: string
    fuel_type: string
    capacity_mw: number
    state: string
  }
  nearest_substation: {
    id: number
    name: string
    voltage_kv: number
    owner: string
    dist_km: number
  } | null
  scores: {
    total: number
    substation: number
    voltage: number
    competition: number
    land_use: number
    slope: number
    excluded: boolean
  }
}

export function useProjectScore(projectId: number | null) {
  const [data, setData] = useState<ProjectScore | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    if (projectId == null) {
      setData(null)
      return
    }

    const controller = new AbortController()
    setIsLoading(true)

    fetch(`/api/projects/${projectId}/score`, { signal: controller.signal })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(json => {
        setData(json)
        setError(null)
      })
      .catch(err => {
        if (err.name !== 'AbortError') setError(err)
      })
      .finally(() => setIsLoading(false))

    return () => controller.abort()
  }, [projectId])

  return { data, isLoading, error }
}
