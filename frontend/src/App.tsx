import { useAtomValue } from 'jotai'
import { MapView } from './components/MapView'
import { ScoreCard } from './components/ScoreCard'
import { FilterPanel } from './components/FilterPanel'
import { ProjectTable } from './components/ProjectTable'
import { scorecardOpenAtom } from './state/atoms'

export default function App() {
  const scorecardOpen = useAtomValue(scorecardOpenAtom)

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      background: '#0b0f1a',
      color: '#e2e8f0',
      fontFamily: 'DM Sans, sans-serif',
    }}>
      {/* Top bar */}
      <div style={{
        height: 48,
        background: '#111827',
        borderBottom: '1px solid #1e2d45',
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: 16,
        flexShrink: 0,
        zIndex: 20,
      }}>
        <div style={{ fontFamily: 'DM Serif Display, serif', fontSize: 18, color: '#00e5a0' }}>
          Renewable Atlas
        </div>
        <div style={{ fontFamily: 'monospace', fontSize: 10, color: '#4a5568', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          Siting Intelligence Platform
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#00e5a0', boxShadow: '0 0 6px #00e5a0', animation: 'pulse 2s infinite' }} />
          <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#64748b' }}>PostGIS live</span>
        </div>
      </div>

      {/* Map + side panel */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Map */}
        <div style={{ flex: 1, position: 'relative' }}>
          <MapView />
          <FilterPanel />
          {/* Legend */}
          <div style={{
            position: 'absolute', bottom: 32, right: scorecardOpen ? 336 : 16,
            background: 'rgba(17,24,39,0.85)',
            border: '1px solid #1e2d45',
            borderRadius: 6,
            padding: '10px 14px',
            backdropFilter: 'blur(8px)',
            transition: 'right 0.2s',
          }}>
            <div style={{ fontFamily: 'monospace', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#4a5568', marginBottom: 8 }}>
              Siting Score
            </div>
            {[['#00e5a0', 'High (80–100)'], ['#f59e0b', 'Medium (50–79)'], ['#ef4444', 'Low (0–49)']].map(([c, l]) => (
              <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: c }} />
                <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#94a3b8' }}>{l}</span>
              </div>
            ))}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
              <div style={{ width: 12, height: 3, borderRadius: 1, background: '#3b82f6' }} />
              <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#94a3b8' }}>Transmission</span>
            </div>
          </div>

          {/* Score card panel */}
          {scorecardOpen && <ScoreCard />}
        </div>
      </div>

      {/* Bottom table */}
      <div style={{ height: 280, borderTop: '1px solid #1e2d45', padding: '12px 16px', overflow: 'hidden', flexShrink: 0 }}>
        <ProjectTable />
      </div>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        * { box-sizing: border-box; }
        body { margin: 0; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e2d45; border-radius: 3px; }
      `}</style>
    </div>
  )
}
