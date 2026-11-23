import cytoscape, { type Core, type ElementDefinition } from 'cytoscape'
import { ArrowUpRight, Maximize2, Minus, Plus, RotateCcw } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { EmptyState, FilterBar, SearchInput, Select } from '@/components/ui/Controls'
import { PageHeader } from '@/components/ui/PageHeader'
import { Panel } from '@/components/ui/Panel'
import { StatCard, StatGrid } from '@/components/ui/StatCard'
import { useLibrary } from '@/hooks/useLibrary'
import { useMySessions } from '@/hooks/useMySessions'
import { SOURCE_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { api } from '@/services/api'
import type { GraphEdge, GraphNode, GraphNodeType, GraphRelation, KnowledgeGraph as Graph, LibraryRecord } from '@/types/research'

const TYPES: { type: GraphNodeType; label: string; color: string; shape: cytoscape.Css.NodeShape }[] = [
  { type: 'disease', label: 'Diseases & conditions', color: '#be123c', shape: 'round-rectangle' },
  { type: 'target', label: 'Targets', color: '#0d9488', shape: 'ellipse' },
  { type: 'compound', label: 'Compounds', color: '#7c3aed', shape: 'diamond' },
  { type: 'trial', label: 'Trials', color: '#2563eb', shape: 'round-rectangle' },
  { type: 'publication', label: 'Publications', color: '#64748b', shape: 'ellipse' },
  { type: 'sponsor', label: 'Sponsors', color: '#b45309', shape: 'hexagon' },
]
const TYPE = Object.fromEntries(TYPES.map((t) => [t.type, t])) as Record<GraphNodeType, (typeof TYPES)[number]>

const RELATION_LABELS: Record<GraphRelation, { forward: string; reverse: string; source: string }> = {
  associated_with: { forward: 'associated with', reverse: 'associated target', source: 'Open Targets association' },
  acts_on: { forward: 'acts on', reverse: 'targeted by', source: 'ChEMBL mechanism of action' },
  tests: { forward: 'tests', reverse: 'tested in', source: 'Trial intervention matches the ChEMBL compound name' },
  studies: { forward: 'studies', reverse: 'studied in', source: 'Condition registered for the trial' },
  sponsored_by: { forward: 'sponsored by', reverse: 'sponsors', source: 'Lead sponsor registered for the trial' },
  references: { forward: 'references', reverse: 'referenced by', source: 'NCT number appears in the title or abstract' },
  mentions: { forward: 'mentions', reverse: 'mentioned in', source: 'Compound named in the title or abstract' },
}

function neighbours(edges: GraphEdge[], id: string): Set<string> {
  const out = new Set<string>()
  for (const e of edges) {
    if (e.source === id) out.add(e.target)
    if (e.target === id) out.add(e.source)
  }
  return out
}

export default function KnowledgeGraph() {
  const [params, setParams] = useSearchParams()
  const sessionId = params.get('session') ?? ''
  const focusParam = params.get('focus')
  const { items: sessions } = useMySessions()
  const { records } = useLibrary()
  const key = `${sessionId}|${focusParam ?? ''}`
  const [loaded, setLoaded] = useState<{ key: string; graph: Graph | null; error: string | null } | null>(null)
  const graph = loaded?.key === key ? loaded.graph : null
  const error = loaded?.key === key ? loaded.error : null
  const [hidden, setHidden] = useState<Set<GraphNodeType>>(new Set())
  const [selected, setSelected] = useState<string | null>(focusParam)
  const [visible, setVisible] = useState<Set<string> | null>(null) // null = whole graph
  const [query, setQuery] = useState('')

  useEffect(() => {
    let cancelled = false
    api
      .getGraph(sessionId || undefined)
      .then((g) => {
        if (cancelled) return
        setLoaded({ key, graph: g, error: null })
        const focus = focusParam && g.nodes.some((n) => n.id === focusParam) ? focusParam : null
        setSelected(focus)
        setVisible(focus ? new Set([focus, ...neighbours(g.edges, focus)]) : null)
      })
      .catch((e: Error) => !cancelled && setLoaded({ key, graph: null, error: e.message }))
    return () => {
      cancelled = true
    }
  }, [key, sessionId, focusParam])

  const nodeById = useMemo(() => new Map((graph?.nodes ?? []).map((n) => [n.id, n])), [graph])
  const recordById = useMemo(() => new Map((records ?? []).map((r) => [r.record_id, r])), [records])

  const shown = useMemo(() => {
    if (!graph) return { nodes: [] as GraphNode[], edges: [] as GraphEdge[] }
    const nodes = graph.nodes.filter((n) => !hidden.has(n.type) && (!visible || visible.has(n.id)))
    const ids = new Set(nodes.map((n) => n.id))
    return { nodes, edges: graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target)) }
  }, [graph, hidden, visible])

  const focusOn = (id: string) => {
    if (!graph) return
    setSelected(id)
    setVisible(new Set([id, ...neighbours(graph.edges, id)]))
  }
  const expand = (id: string) => {
    if (!graph) return
    setVisible((v) => new Set([...(v ?? []), id, ...neighbours(graph.edges, id)]))
    setSelected(id)
  }

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q || !graph) return []
    return graph.nodes.filter((n) => n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q)).slice(0, 8)
  }, [query, graph])

  const selectedNode = selected ? nodeById.get(selected) : undefined
  const connections = useMemo(() => {
    if (!graph || !selected) return []
    return graph.edges
      .filter((e) => e.source === selected || e.target === selected)
      .map((e) => {
        const outgoing = e.source === selected
        return { edge: e, other: nodeById.get(outgoing ? e.target : e.source)!, label: outgoing ? RELATION_LABELS[e.relation].forward : RELATION_LABELS[e.relation].reverse }
      })
      .sort((a, b) => a.label.localeCompare(b.label) || a.other.label.localeCompare(b.other.label))
  }, [graph, selected, nodeById])

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[{ label: 'Workspace', to: '/' }, { label: 'Knowledge graph' }]}
        title="Knowledge Graph"
        subtitle="Diseases, targets, compounds, trials and publications from your research, connected only where a retrieved record states the connection. Click any node or link to see the records behind it."
      />

      {graph && (
        <StatGrid>
          <StatCard label="Entities" value={graph.nodes.length} hint={`From ${graph.stats.records} evidence records`} />
          <StatCard label="Source-stated links" value={graph.edges.length} hint="Each one traceable to a record" />
          <StatCard label="Targets" value={graph.stats.nodes_by_type.target ?? 0} hint={`${graph.stats.edges_by_relation.acts_on ?? 0} compound → target mechanisms`} />
          <StatCard label="Publications linked" value={graph.stats.nodes_by_type.publication ?? 0} hint={`${graph.stats.publications_without_links} name no retrieved trial or compound`} />
        </StatGrid>
      )}

      <FilterBar>
        <div className="relative min-w-[16rem] flex-[2]">
          <SearchInput value={query} onChange={setQuery} placeholder="Find a target, compound, trial or disease…" />
          {matches.length > 0 && (
            <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg">
              {matches.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => {
                      focusOn(n.id)
                      setQuery('')
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50"
                  >
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: TYPE[n.type].color }} aria-hidden="true" />
                    <span className="truncate">{n.label}</span>
                    <span className="ml-auto text-xs text-slate-400">{n.type}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <Select
          label="Research session"
          value={sessionId}
          onChange={(v) => setParams(v ? { session: v } : {})}
          options={[{ value: '', label: 'All my research' }, ...(sessions ?? []).filter((s) => s.status === 'completed').map((s) => ({ value: s.session_id, label: s.research_question.slice(0, 70) }))]}
        />
      </FilterBar>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Entity types">
        {TYPES.map((t) => {
          const off = hidden.has(t.type)
          return (
            <button
              key={t.type}
              type="button"
              aria-pressed={!off}
              onClick={() =>
                setHidden((h) => {
                  const next = new Set(h)
                  if (off) next.delete(t.type)
                  else next.add(t.type)
                  return next
                })
              }
              className={cn('flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs', off ? 'border-slate-200 text-slate-400' : 'border-slate-300 bg-white text-ink-900')}
            >
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: off ? '#cbd5e1' : t.color }} aria-hidden="true" />
              {t.label} · {graph?.stats.nodes_by_type[t.type] ?? 0}
            </button>
          )
        })}
      </div>

      {error ? (
        <p className="text-sm text-rose-700">{error}</p>
      ) : !graph ? (
        <p className="text-sm text-slate-500">Building graph from your evidence…</p>
      ) : graph.nodes.length === 0 ? (
        <EmptyState title="No connections yet">
          The graph is built from records retrieved in your research.{' '}
          <Link to="/" className="font-medium text-accent-700 hover:underline">
            Start research
          </Link>
        </EmptyState>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
          <GraphCanvas
            nodes={shown.nodes}
            edges={shown.edges}
            selected={selected}
            focused={visible !== null}
            onSelect={setSelected}
            onExpand={expand}
            onReset={() => {
              setVisible(null)
              setSelected(null)
            }}
          />
          <Panel title={selectedNode ? selectedNode.label : 'Select a node'} subtitle={selectedNode ? TYPE[selectedNode.type].label.replace(/s( & conditions)?$/, '') : 'Click a node to see where it comes from'} bodyClassName="p-5 pt-3">
            {!selectedNode ? (
              <div className="space-y-3 text-sm text-slate-600">
                <p>Links are drawn only from what sources state:</p>
                <ul className="space-y-1.5 text-xs">
                  {Object.entries(RELATION_LABELS).map(([k, v]) => (
                    <li key={k}>
                      <span className="font-medium text-ink-900">{v.forward}</span> — {v.source}
                    </li>
                  ))}
                </ul>
                <p className="text-xs text-slate-500">Nothing is inferred by AI. Double-click a node to expand its neighbours.</p>
              </div>
            ) : (
              <NodeDetails
                node={selectedNode}
                connections={connections}
                recordById={recordById}
                onFocus={focusOn}
                focused={visible !== null}
              />
            )}
          </Panel>
        </div>
      )}
    </div>
  )
}

function GraphCanvas({
  nodes,
  edges,
  selected,
  focused,
  onSelect,
  onExpand,
  onReset,
}: {
  nodes: GraphNode[]
  edges: GraphEdge[]
  selected: string | null
  focused: boolean
  onSelect: (id: string | null) => void
  onExpand: (id: string) => void
  onReset: () => void
}) {
  const container = useRef<HTMLDivElement>(null)
  const cy = useRef<Core | null>(null)
  const handlers = useRef({ onSelect, onExpand })
  useEffect(() => {
    handlers.current = { onSelect, onExpand }
  }, [onSelect, onExpand])

  useEffect(() => {
    if (!container.current) return
    const elements: ElementDefinition[] = [
      ...nodes.map((n) => ({ data: { id: n.id, label: n.label.length > 32 ? `${n.label.slice(0, 30)}…` : n.label, type: n.type, degree: 0 } })),
      ...edges.map((e) => ({ data: { id: e.id, source: e.source, target: e.target, label: RELATION_LABELS[e.relation].forward } })),
    ]
    const instance = cytoscape({
      container: container.current,
      elements,
      minZoom: 0.15,
      maxZoom: 3,
      wheelSensitivity: 0.3,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (el: cytoscape.NodeSingular) => TYPE[el.data('type') as GraphNodeType].color,
            shape: (el: cytoscape.NodeSingular) => TYPE[el.data('type') as GraphNodeType].shape,
            label: 'data(label)',
            'font-size': 9,
            color: '#0f172a',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'text-wrap': 'ellipsis',
            'text-max-width': '120px',
            width: (el: cytoscape.NodeSingular) => 14 + Math.min(26, el.degree(false) * 2.5),
            height: (el: cytoscape.NodeSingular) => 14 + Math.min(26, el.degree(false) * 2.5),
            'border-width': 0,
          },
        },
        { selector: 'node[type = "publication"]', style: { 'font-size': 7, color: '#475569' } },
        { selector: 'edge', style: { width: 1.2, 'line-color': '#cbd5e1', 'curve-style': 'bezier', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#cbd5e1', 'arrow-scale': 0.7 } },
        { selector: '.faded', style: { opacity: 0.15 } },
        { selector: 'node.focus', style: { 'border-width': 3, 'border-color': '#0f172a' } },
        { selector: 'edge.focus', style: { 'line-color': '#0d9488', 'target-arrow-color': '#0d9488', width: 2, label: 'data(label)', 'font-size': 7, color: '#0f766e', 'text-background-color': '#ffffff', 'text-background-opacity': 1, 'text-background-padding': '1px' } },
      ],
      layout: { name: 'cose', animate: false, nodeRepulsion: () => 9000, idealEdgeLength: () => 70, padding: 30, randomize: true } as cytoscape.LayoutOptions,
    })
    // Small neighbourhoods would otherwise be zoomed in until a few nodes fill the canvas.
    if (instance.zoom() > 1.4) {
      instance.zoom(1.4)
      instance.center()
    }
    instance.on('tap', 'node', (evt) => handlers.current.onSelect(evt.target.id()))
    instance.on('dbltap', 'node', (evt) => handlers.current.onExpand(evt.target.id()))
    instance.on('tap', (evt) => {
      if (evt.target === instance) handlers.current.onSelect(null)
    })
    cy.current = instance
    return () => {
      instance.destroy()
      cy.current = null
    }
  }, [nodes, edges])

  useEffect(() => {
    const c = cy.current
    if (!c) return
    c.elements().removeClass('faded focus')
    if (!selected) return
    const node = c.getElementById(selected)
    if (node.empty()) return
    const hood = node.closedNeighborhood()
    c.elements().not(hood).addClass('faded')
    node.addClass('focus')
    node.connectedEdges().addClass('focus')
  }, [selected, nodes, edges])

  const fit = () => cy.current?.fit(undefined, 30)
  const zoom = (factor: number) => {
    const c = cy.current
    if (c) c.zoom({ level: c.zoom() * factor, renderedPosition: { x: c.width() / 2, y: c.height() / 2 } })
  }

  return (
    <section className="relative overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div ref={container} className="h-[640px] w-full" role="img" aria-label={`Knowledge graph with ${nodes.length} entities and ${edges.length} links`} />
      <div className="absolute right-3 top-3 flex flex-col gap-1">
        <ToolButton label="Zoom in" onClick={() => zoom(1.25)}>
          <Plus className="h-4 w-4" aria-hidden="true" />
        </ToolButton>
        <ToolButton label="Zoom out" onClick={() => zoom(0.8)}>
          <Minus className="h-4 w-4" aria-hidden="true" />
        </ToolButton>
        <ToolButton label="Fit to view" onClick={fit}>
          <Maximize2 className="h-4 w-4" aria-hidden="true" />
        </ToolButton>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-4 py-2.5 text-xs text-slate-500">
        <span>
          {nodes.length} entities · {edges.length} links{focused ? ' · neighbourhood view (double-click a node to expand)' : ''}
        </span>
        {focused && (
          <button type="button" onClick={onReset} className="inline-flex items-center gap-1 font-medium text-accent-700 hover:underline">
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" /> Show whole graph
          </button>
        )}
      </div>
    </section>
  )
}

function ToolButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} aria-label={label} title={label} className="rounded border border-slate-200 bg-white p-1.5 text-slate-600 hover:text-ink-900">
      {children}
    </button>
  )
}

function RecordLink({ id, record }: { id: string; record?: LibraryRecord }) {
  if (!record) return <span className="font-mono text-xs text-slate-500">{id}</span>
  return (
    <a href={record.source_url} target="_blank" rel="noreferrer" className="group block rounded border border-slate-100 px-2.5 py-1.5 hover:border-accent-200 hover:bg-accent-50/40">
      <span className="line-clamp-2 text-xs text-ink-900 group-hover:text-accent-800">{record.title}</span>
      <span className="mt-0.5 inline-flex items-center gap-1 text-[11px] text-slate-500">
        {SOURCE_LABELS[record.source_name]} · {record.source_identifier} <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
      </span>
    </a>
  )
}

function NodeDetails({
  node,
  connections,
  recordById,
  onFocus,
  focused,
}: {
  node: GraphNode
  connections: { edge: GraphEdge; other: GraphNode; label: string }[]
  recordById: Map<string, LibraryRecord>
  onFocus: (id: string) => void
  focused: boolean
}) {
  const facts = Object.entries(node.data).filter(([, v]) => v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && !v.length))
  const [open, setOpen] = useState<string | null>(null)
  return (
    <div className="space-y-5 text-sm">
      <div className="flex flex-wrap gap-2">
        {!focused && (
          <button type="button" onClick={() => onFocus(node.id)} className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-ink-900 hover:bg-slate-50">
            Show neighbourhood
          </button>
        )}
        {node.type === 'compound' && typeof node.data.chembl_id === 'string' && (
          <Link to={`/drugs/${node.data.chembl_id}`} className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-ink-900 hover:bg-slate-50">
            Open drug profile
          </Link>
        )}
        {node.url && (
          <a href={node.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-ink-900 hover:bg-slate-50">
            Source page <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
          </a>
        )}
      </div>

      {facts.length > 0 && (
        <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
          {facts.map(([k, v]) => (
            <div key={k}>
              <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{k.replace(/_/g, ' ')}</dt>
              <dd className="mt-0.5 break-words text-ink-900">{Array.isArray(v) ? v.join(', ') : String(v)}</dd>
            </div>
          ))}
        </dl>
      )}

      {node.record_ids.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Source records</p>
          <div className="mt-2 space-y-1.5">
            {node.record_ids.map((id) => (
              <RecordLink key={id} id={id} record={recordById.get(id)} />
            ))}
          </div>
        </div>
      )}

      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Connections · {connections.length}</p>
        <ul className="mt-2 max-h-80 space-y-1 overflow-y-auto pr-1">
          {connections.map(({ edge, other, label }) => (
            <li key={edge.id} className="rounded border border-slate-100">
              <div className="flex items-center gap-2 px-2.5 py-1.5">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: TYPE[other.type].color }} aria-hidden="true" />
                <span className="text-xs text-slate-500">{label}</span>
                <button type="button" onClick={() => onFocus(other.id)} className="min-w-0 flex-1 truncate text-left text-xs font-medium text-ink-900 hover:text-accent-700" title={other.label}>
                  {other.label}
                </button>
                <button type="button" onClick={() => setOpen(open === edge.id ? null : edge.id)} className="shrink-0 text-[11px] text-accent-700 hover:underline" aria-expanded={open === edge.id}>
                  why?
                </button>
              </div>
              {open === edge.id && (
                <div className="space-y-1.5 border-t border-slate-100 bg-slate-50/60 px-2.5 py-2">
                  <p className="text-[11px] text-slate-600">
                    {RELATION_LABELS[edge.relation].source}
                    {edge.detail ? ` — ${edge.detail}` : ''}
                  </p>
                  {edge.record_ids.map((id) => (
                    <RecordLink key={id} id={id} record={recordById.get(id)} />
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
