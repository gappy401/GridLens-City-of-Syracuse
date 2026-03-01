import { useEffect, useState } from 'react'
import { useAtomValue } from 'jotai'
import { mapBoundsAtom, filtersAtom } from '../state/atoms'

interface GeoJSONCollection {
  type: 'FeatureCollection'
  features: GeoJSONFeature[]
  total: number
}

interface GeoJSONFeature {
  type: 'Feature'
  geometry: { type: string; coordinates: number[] }
  properties: {
    id: number
    name: string
    fuel_type: string
    capacity_mw: number
    state: string
    score: number
  }
}

export function useProjects() {
  const bounds = useAtomValue(mapBoundsAtom)
  const filters = useAtomValue(filtersAtom)
  const [data, setData] = useState<GeoJSONCollection | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    if (!bounds) return

    const params = new URLSearchParams({
      min_lon: bounds.min_lon.toFixed(6),
      min_lat: bounds.min_lat.toFixed(6),
      max_lon: bounds.max_lon.toFixed(6),
      max_lat: bounds.max_lat.toFixed(6),
    })
    if (filters.fuelType)       params.set('fuel_type', filters.fuelType)
    if (filters.minScore != null) params.set('min_score', String(filters.minScore))

    const controller = new AbortController()
    setIsLoading(true)

    fetch(`/api/projects?${params}`, { signal: controller.signal })
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
  }, [bounds, filters])

  return { data, isLoading, error }
}
