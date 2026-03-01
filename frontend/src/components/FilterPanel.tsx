import { useAtom } from 'jotai'
import { filtersAtom } from '../state/atoms'

const FUEL_TYPES = ['Solar', 'Wind', 'Battery', 'Geothermal', 'Hydro']

export function FilterPanel() {
  const [filters, setFilters] = useAtom(filtersAtom)

  const panelStyle: React.CSSProperties = {
    position: 'absolute',
    top: 16,
    left: 16,
    background: 'rgba(17, 24, 39, 0.92)',
    border: '1px solid #1e2d45',
    borderRadius: 6,
    padding: '14px 16px',
    backdropFilter: 'blur(8px)',
    minWidth: 200,
    fontFamily: 'DM Sans, sans-serif',
    zIndex: 10,
  }

  const labelStyle: React.CSSProperties = {
    fontSize: 9,
    fontFamily: 'monospace',
    letterSpacing: '0.1em',
    textTransform: 'uppercase' as const,
    color: '#4a5568',
    marginBottom: 6,
    marginTop: 12,
    display: 'block',
  }

  const selectStyle: React.CSSProperties = {
    width: '100%',
    background: '#0b0f1a',
    border: '1px solid #1e2d45',
    borderRadius: 4,
    color: '#e2e8f0',
    padding: '6px 8px',
    fontSize: 12,
    fontFamily: 'monospace',
    outline: 'none',
  }

  const rangeStyle: React.CSSProperties = {
    width: '100%',
    accentColor: '#00e5a0',
  }

  return (
    <div style={panelStyle}>
      <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#00e5a0', marginBottom: 2 }}>
        ◈ Filters
      </div>

      <label style={labelStyle}>Fuel Type</label>
      <select
        style={selectStyle}
        value={filters.fuelType ?? ''}
        onChange={e => setFilters(f => ({ ...f, fuelType: e.target.value || null }))}
      >
        <option value="">All types</option>
        {FUEL_TYPES.map(t => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>

      <label style={labelStyle}>Min Siting Score: {filters.minScore ?? 0}</label>
      <input
        type="range"
        min={0}
        max={100}
        step={5}
        style={rangeStyle}
        value={filters.minScore ?? 0}
        onChange={e => setFilters(f => ({ ...f, minScore: Number(e.target.value) || null }))}
      />

      <label style={labelStyle}>Min Capacity (MW): {filters.minCapacityMw ?? 0}</label>
      <input
        type="range"
        min={0}
        max={1000}
        step={50}
        style={rangeStyle}
        value={filters.minCapacityMw ?? 0}
        onChange={e => setFilters(f => ({ ...f, minCapacityMw: Number(e.target.value) || null }))}
      />

      <button
        onClick={() => setFilters({ fuelType: null, minScore: null, minCapacityMw: null })}
        style={{
          marginTop: 12,
          width: '100%',
          padding: '5px 0',
          background: 'transparent',
          border: '1px solid #1e2d45',
          borderRadius: 4,
          color: '#64748b',
          fontSize: 11,
          fontFamily: 'monospace',
          cursor: 'pointer',
        }}
      >
        Reset filters
      </button>
    </div>
  )
}
