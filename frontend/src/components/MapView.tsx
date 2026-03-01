import { useEffect, useRef } from 'react'
import mapboxgl from 'mapbox-gl'
import { useAtom, useAtomValue, useSetAtom } from 'jotai'
import { selectedProjectIdAtom, mapBoundsAtom, scorecardOpenAtom } from '../state/atoms'
import { useProjects } from '../hooks/useProjects'
import 'mapbox-gl/dist/mapbox-gl.css'

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN

// Mapbox expression: interpolate score → colour
const SCORE_COLOR: mapboxgl.Expression = [
  'interpolate', ['linear'], ['get', 'score'],
  0,  '#ef4444',   // red   — poor siting
  50, '#f59e0b',   // amber — moderate
  80, '#00e5a0',   // green — excellent
]

const CIRCLE_RADIUS: mapboxgl.Expression = [
  'interpolate', ['linear'], ['zoom'],
  3, 3,
  8, 7,
  12, 14,
]

export function MapView() {
  const mapContainer = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<mapboxgl.Map | null>(null)
  const popupRef = useRef<mapboxgl.Popup | null>(null)

  const [, setSelectedId] = useAtom(selectedProjectIdAtom)
  const setScorecardOpen = useSetAtom(scorecardOpenAtom)
  const setBounds = useSetAtom(mapBoundsAtom)
  const { data } = useProjects()

  // ── Initialise map ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapContainer.current) return

    const map = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: [-98.5, 39.5],
      zoom: 4,
    })
    mapRef.current = map

    map.addControl(new mapboxgl.NavigationControl(), 'top-right')
    map.addControl(new mapboxgl.ScaleControl(), 'bottom-left')

    map.on('load', () => {
      // ── Transmission lines (vector tile source) ─────────────────────
      // Replace with your own tileset or serve via pg_tileserv
      map.addSource('transmission', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] }, // swap for real tileset
      })
      map.addLayer({
        id: 'transmission-lines',
        type: 'line',
        source: 'transmission',
        paint: {
          'line-color': '#3b82f6',
          'line-width': 1,
          'line-opacity': 0.4,
        },
      })

      // ── Project points ───────────────────────────────────────────────
      map.addSource('projects', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
        cluster: false,
      })

      map.addLayer({
        id: 'projects-circle',
        type: 'circle',
        source: 'projects',
        paint: {
          'circle-color': SCORE_COLOR,
          'circle-radius': CIRCLE_RADIUS,
          'circle-stroke-color': 'rgba(0, 0, 0, 0.35)',
          'circle-stroke-width': 1,
          'circle-opacity': 0.85,
        },
      })

      // ── Selected project highlight ───────────────────────────────────
      map.addLayer({
        id: 'projects-selected',
        type: 'circle',
        source: 'projects',
        filter: ['==', ['get', 'id'], -1],
        paint: {
          'circle-color': SCORE_COLOR,
          'circle-radius': ['+', CIRCLE_RADIUS as any, 5],
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 2,
          'circle-opacity': 1,
        },
      })
    })

    // ── Click: open scorecard ──────────────────────────────────────────
    map.on('click', 'projects-circle', e => {
      const props = e.features?.[0]?.properties
      if (!props) return
      setSelectedId(props.id)
      setScorecardOpen(true)
      map.setFilter('projects-selected', ['==', ['get', 'id'], props.id])
    })

    // ── Hover popup ────────────────────────────────────────────────────
    map.on('mouseenter', 'projects-circle', e => {
      map.getCanvas().style.cursor = 'pointer'
      const f = e.features?.[0]
      if (!f) return
      const props = f.properties!
      const coords = (f.geometry as GeoJSON.Point).coordinates as [number, number]
      const scoreColor = props.score >= 80 ? '#00e5a0' : props.score >= 50 ? '#f59e0b' : '#ef4444'

      popupRef.current = new mapboxgl.Popup({ closeButton: false, offset: 12 })
        .setLngLat(coords)
        .setHTML(`
          <div style="font-family:monospace;font-size:12px;min-width:160px">
            <div style="font-weight:700;color:${scoreColor};margin-bottom:6px">${props.name ?? 'Unknown'}</div>
            <div style="display:flex;justify-content:space-between;gap:12px;color:#94a3b8">
              <span>Score</span><span style="color:#e2e8f0">${props.score ?? '—'}/100</span>
            </div>
            <div style="display:flex;justify-content:space-between;gap:12px;color:#94a3b8">
              <span>Capacity</span><span style="color:#e2e8f0">${props.capacity_mw ? props.capacity_mw + ' MW' : '—'}</span>
            </div>
            <div style="display:flex;justify-content:space-between;gap:12px;color:#94a3b8">
              <span>Type</span><span style="color:#e2e8f0">${props.fuel_type ?? '—'}</span>
            </div>
          </div>
        `)
        .addTo(map)
    })

    map.on('mouseleave', 'projects-circle', () => {
      map.getCanvas().style.cursor = ''
      popupRef.current?.remove()
    })

    // ── Bounds change: re-query API ────────────────────────────────────
    const updateBounds = () => {
      const b = map.getBounds()
      setBounds({
        min_lon: b.getWest(),
        min_lat: b.getSouth(),
        max_lon: b.getEast(),
        max_lat: b.getNorth(),
      })
    }
    map.on('moveend', updateBounds)
    map.on('load', updateBounds)

    return () => map.remove()
  }, [])

  // ── Update data when API responds ──────────────────────────────────────
  useEffect(() => {
    const source = mapRef.current?.getSource('projects') as mapboxgl.GeoJSONSource | undefined
    if (source && data) {
      source.setData(data as GeoJSON.FeatureCollection)
    }
  }, [data])

  return <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />
}
