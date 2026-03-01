import { useMemo } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table'
import { useState } from 'react'
import { useSetAtom } from 'jotai'
import { selectedProjectIdAtom, scorecardOpenAtom } from '../state/atoms'
import { useProjects } from '../hooks/useProjects'

interface ProjectRow {
  id: number
  name: string
  fuel_type: string
  capacity_mw: number
  state: string
  score: number
}

const colHelper = createColumnHelper<ProjectRow>()

function ScorePill({ score }: { score: number }) {
  const color = score >= 80 ? '#00e5a0' : score >= 50 ? '#f59e0b' : '#ef4444'
  const bg = score >= 80 ? 'rgba(0,229,160,0.1)' : score >= 50 ? 'rgba(245,158,11,0.1)' : 'rgba(239,68,68,0.1)'
  return (
    <span style={{
      fontFamily: 'monospace', fontSize: 11, fontWeight: 700,
      color, background: bg, padding: '2px 7px', borderRadius: 3,
    }}>
      {score}
    </span>
  )
}

export function ProjectTable() {
  const { data, isLoading } = useProjects()
  const setSelectedId = useSetAtom(selectedProjectIdAtom)
  const setScorecardOpen = useSetAtom(scorecardOpenAtom)
  const [sorting, setSorting] = useState<SortingState>([{ id: 'score', desc: true }])

  const rows: ProjectRow[] = useMemo(
    () => (data?.features ?? []).map(f => f.properties as ProjectRow),
    [data]
  )

  const columns = useMemo(() => [
    colHelper.accessor('name', {
      header: 'Project',
      cell: info => (
        <span style={{ color: '#e2e8f0', fontWeight: 500, fontSize: 12 }}>
          {info.getValue() ?? '—'}
        </span>
      ),
    }),
    colHelper.accessor('fuel_type', {
      header: 'Type',
      cell: info => (
        <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#64748b' }}>
          {info.getValue()}
        </span>
      ),
    }),
    colHelper.accessor('state', {
      header: 'State',
      cell: info => (
        <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#64748b' }}>
          {info.getValue()}
        </span>
      ),
    }),
    colHelper.accessor('capacity_mw', {
      header: 'MW',
      cell: info => (
        <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#94a3b8' }}>
          {info.getValue()?.toLocaleString() ?? '—'}
        </span>
      ),
    }),
    colHelper.accessor('score', {
      header: 'Score',
      cell: info => <ScorePill score={info.getValue()} />,
    }),
  ], [])

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const containerStyle: React.CSSProperties = {
    background: '#111827',
    border: '1px solid #1e2d45',
    borderRadius: 6,
    overflow: 'hidden',
    fontFamily: 'DM Sans, sans-serif',
  }

  const thStyle: React.CSSProperties = {
    padding: '8px 12px',
    fontFamily: 'monospace',
    fontSize: 10,
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    color: '#4a5568',
    background: '#0b0f1a',
    borderBottom: '1px solid #1e2d45',
    textAlign: 'left',
    cursor: 'pointer',
    userSelect: 'none',
    whiteSpace: 'nowrap',
  }

  const tdStyle: React.CSSProperties = {
    padding: '9px 12px',
    borderBottom: '1px solid rgba(30,45,69,0.4)',
  }

  if (isLoading) {
    return (
      <div style={containerStyle}>
        <div style={{ padding: 16, color: '#4a5568', fontFamily: 'monospace', fontSize: 12 }}>
          Loading projects…
        </div>
      </div>
    )
  }

  return (
    <div style={containerStyle}>
      <div style={{ padding: '10px 14px', borderBottom: '1px solid #1e2d45', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontFamily: 'monospace', fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748b' }}>
          Projects in view
        </span>
        <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#4a5568', background: '#0b0f1a', padding: '2px 8px', borderRadius: 3, border: '1px solid #1e2d45' }}>
          {rows.length.toLocaleString()}
        </span>
      </div>
      <div style={{ overflowY: 'auto', maxHeight: 320 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id}>
                {hg.headers.map(h => (
                  <th
                    key={h.id}
                    style={thStyle}
                    onClick={h.column.getToggleSortingHandler()}
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {h.column.getIsSorted() === 'asc' ? ' ↑' : h.column.getIsSorted() === 'desc' ? ' ↓' : ''}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map(row => (
              <tr
                key={row.id}
                style={{ cursor: 'pointer' }}
                onClick={() => {
                  setSelectedId(row.original.id)
                  setScorecardOpen(true)
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLTableRowElement).style.background = 'rgba(0,229,160,0.04)'
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLTableRowElement).style.background = ''
                }}
              >
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} style={tdStyle}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
