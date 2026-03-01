import {
  RadarChart, PolarGrid, PolarAngleAxis,
  Radar, ResponsiveContainer, Tooltip,
} from 'recharts'
import { useAtomValue, useSetAtom } from 'jotai'
import { selectedProjectIdAtom, scorecardOpenAtom } from '../state/atoms'
import { useProjectScore } from '../hooks/useProjectScore'

const DIMS = [
  { key: 'substation',  label: 'Substation',  weight: '30%' },
  { key: 'voltage',     label: 'Voltage',      weight: '25%' },
  { key: 'competition', label: 'Competition',  weight: '15%' },
  { key: 'land_use',    label: 'Land Use',     weight: '15%' },
  { key: 'slope',       label: 'Slope',        weight: '15%' },
] as const

function scoreColor(score: number): string {
  if (score >= 80) return '#00e5a0'
  if (score >= 50) return '#f59e0b'
  return '#ef4444'
}

interface ScoreBarProps {
  label: string
  weight: string
  value: number
}

function ScoreBar({ label, weight, value }: ScoreBarProps) {
  const color = scoreColor(value)
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: '#94a3b8' }}>
          {label}
          <span style={{ marginLeft: 6, fontSize: 10, color: '#4a5568' }}>{weight}</span>
        </span>
        <span style={{ fontFamily: 'monospace', fontSize: 12, color }}>{value}</span>
      </div>
      <div style={{ height: 4, background: '#1e2d45', borderRadius: 2, overflow: 'hidden' }}>
        <div
          style={{
            height: '100%',
            width: `${value}%`,
            background: color,
            borderRadius: 2,
            transition: 'width 0.4s ease',
          }}
        />
      </div>
    </div>
  )
}

export function ScoreCard() {
  const projectId = useAtomValue(selectedProjectIdAtom)
  const setScorecardOpen = useSetAtom(scorecardOpenAtom)
  const { data, isLoading } = useProjectScore(projectId)

  const panelStyle: React.CSSProperties = {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    width: 320,
    background: '#111827',
    borderLeft: '1px solid #1e2d45',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    fontFamily: 'DM Sans, sans-serif',
  }

  if (!projectId) {
    return (
      <div style={panelStyle}>
        <div style={{ padding: 24, color: '#4a5568', fontSize: 13, textAlign: 'center', marginTop: 60 }}>
          Click a project on the map to view its siting scorecard.
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div style={panelStyle}>
        <div style={{ padding: 24, color: '#4a5568', fontSize: 13 }}>Loading scorecard…</div>
      </div>
    )
  }

  if (!data) return null

  const radarData = DIMS.map(d => ({
    subject: d.label,
    score: data.scores[d.key],
  }))

  const total = data.scores.total
  const color = scoreColor(total)

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid #1e2d45', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#4a5568', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>
            Siting Scorecard
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', lineHeight: 1.3 }}>
            {data.project.name}
          </div>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
            {data.project.fuel_type} · {data.project.capacity_mw} MW · {data.project.state}
          </div>
        </div>
        <button
          onClick={() => setScorecardOpen(false)}
          style={{ background: 'none', border: 'none', color: '#4a5568', cursor: 'pointer', fontSize: 18, padding: 4 }}
        >
          ×
        </button>
      </div>

      {/* Score badge */}
      <div style={{ padding: '20px 20px 0', textAlign: 'center' }}>
        <div style={{ fontFamily: 'monospace', fontSize: 48, fontWeight: 700, color, lineHeight: 1 }}>
          {total}
          <span style={{ fontSize: 16, color: '#4a5568' }}>/100</span>
        </div>
        {data.scores.excluded && (
          <div style={{ fontSize: 11, color: '#ef4444', marginTop: 4 }}>⚠ Excluded — conservation / flood zone</div>
        )}
      </div>

      {/* Radar chart */}
      <ResponsiveContainer width="100%" height={180}>
        <RadarChart data={radarData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
          <PolarGrid stroke="#1e2d45" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: '#64748b', fontSize: 10, fontFamily: 'monospace' }}
          />
          <Radar
            dataKey="score"
            stroke={color}
            fill={color}
            fillOpacity={0.12}
            strokeWidth={1.5}
          />
          <Tooltip
            contentStyle={{ background: '#111827', border: '1px solid #1e2d45', borderRadius: 4, fontFamily: 'monospace', fontSize: 11 }}
            labelStyle={{ color: '#94a3b8' }}
            itemStyle={{ color }}
          />
        </RadarChart>
      </ResponsiveContainer>

      {/* Dimension bars */}
      <div style={{ padding: '0 20px 16px', flex: 1, overflowY: 'auto' }}>
        {DIMS.map(d => (
          <ScoreBar key={d.key} label={d.label} weight={d.weight} value={data.scores[d.key]} />
        ))}
      </div>

      {/* Nearest substation */}
      {data.nearest_substation && (
        <div style={{ padding: '12px 20px', borderTop: '1px solid #1e2d45', background: '#0b0f1a' }}>
          <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#4a5568', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>
            Nearest Substation
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
            <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{data.nearest_substation.name}</span>
            <span style={{ color: '#64748b', fontFamily: 'monospace' }}>{data.nearest_substation.dist_km?.toFixed(1)} km</span>
          </div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
            {data.nearest_substation.voltage_kv} kV · {data.nearest_substation.owner}
          </div>
        </div>
      )}
    </div>
  )
}
