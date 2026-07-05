import { useState } from "react";
import ReactMarkdown from "react-markdown";

interface Action { id: string; title: string; description: string; priority: string; type: string; }
interface SubReport { agent: string; findings: string; sources_used: string[]; confidence: number; }
interface Version {
  root_cause: string; workaround: string; recommended_actions: Action[];
  confidence_score: number; sub_reports?: SubReport[]; applied_hints?: string[] | null;
}
interface AgentCost { input: number; output: number; cost_usd: number; }
interface TokenUsage {
  per_agent?: Record<string, AgentCost>;
  total_input?: number; total_output?: number; total_tokens?: number;
  estimated_cost_usd?: number; model?: string;
}
interface Props { analysisId: string; version?: Version; tokenUsage?: TokenUsage; onSave: () => void; onApplyEdit?: (field: string, value: string) => void; }

export function ReportViewer({ analysisId, version, tokenUsage, onSave, onApplyEdit }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Version | null>(null);
  const [saving, setSaving] = useState(false);
  const [showFindings, setShowFindings] = useState(false);

  function startEdit() {
    setDraft(version ? { ...version } : null);
    setEditing(true);
  }

  async function save() {
    if (!draft) return;
    setSaving(true);
    await fetch(`/api/analysis/${analysisId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...draft, edit_source: "manual_edit" }),
    });
    setSaving(false);
    setEditing(false);
    onSave();
  }

  if (!version) {
    return <div className="bg-white rounded-xl border border-gray-200 p-6 text-gray-400 text-sm">Analysis report will appear here.</div>;
  }

  const display = editing && draft ? draft : version;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Analysis Report</h2>
        {!editing
          ? <button onClick={startEdit} className="text-sm text-blue-600 hover:underline">Edit</button>
          : <div className="flex gap-3">
              <button onClick={() => setEditing(false)} className="text-sm text-gray-500 hover:underline">Cancel</button>
              <button onClick={save} disabled={saving} className="text-sm text-blue-600 font-medium hover:underline disabled:opacity-50">
                {saving ? "Saving..." : "Save Version"}
              </button>
            </div>
        }
      </div>

      {version.applied_hints && version.applied_hints.length > 0 && (
        <div className="border border-purple-200 bg-purple-50 rounded-lg p-3">
          <p className="text-xs font-semibold text-purple-700 uppercase tracking-wide mb-1.5">
            💡 {version.applied_hints.length} lesson{version.applied_hints.length > 1 ? "s" : ""} applied from prior evaluations
          </p>
          <ul className="text-sm text-purple-800 space-y-1 list-disc list-inside">
            {version.applied_hints.map((h, i) => <li key={i}>{h}</li>)}
          </ul>
        </div>
      )}

      <Section label="Root Cause">
        {editing
          ? <textarea rows={4} value={draft?.root_cause ?? ""} onChange={(e) => setDraft((d) => d ? { ...d, root_cause: e.target.value } : d)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
          : <ReactMarkdown className="prose prose-sm max-w-none text-gray-700">{display.root_cause}</ReactMarkdown>
        }
      </Section>

      <Section label="Workaround">
        {editing
          ? <textarea rows={3} value={draft?.workaround ?? ""} onChange={(e) => setDraft((d) => d ? { ...d, workaround: e.target.value } : d)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
          : <ReactMarkdown className="prose prose-sm max-w-none text-gray-700">{display.workaround}</ReactMarkdown>
        }
      </Section>

      <Section label="Recommended Actions">
        <ul className="space-y-2">
          {display.recommended_actions.map((a) => (
            <li key={a.id} className="flex items-start gap-2">
              <span className={`mt-0.5 px-1.5 py-0.5 rounded text-xs font-medium ${priorityColor(a.priority)}`}>{a.priority}</span>
              <span className="text-sm text-gray-700"><strong>{a.title}</strong> — {a.description}</span>
            </li>
          ))}
        </ul>
      </Section>

      {version.sub_reports && version.sub_reports.length > 0 && (
        <div>
          <button
            onClick={() => setShowFindings((v) => !v)}
            className="flex items-center gap-1.5 text-sm font-semibold text-gray-500 uppercase tracking-wide hover:text-gray-700"
          >
            <span>{showFindings ? "▾" : "▸"}</span>
            Agent Findings ({version.sub_reports.length})
          </button>

          {showFindings && (
            <div className="mt-3 space-y-4">
              {version.sub_reports.map((r, i) => {
                const pct = Math.round(r.confidence * 100);
                const barColor = pct >= 70 ? "bg-green-500" : pct >= 40 ? "bg-yellow-400" : "bg-red-400";
                return (
                  <div key={i} className="border border-gray-100 rounded-lg p-4 bg-gray-50">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold text-gray-700 capitalize">{r.agent.replace("_", " ")}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-xs text-gray-500">{pct}% confidence</span>
                      </div>
                    </div>
                    {r.sources_used.length > 0 && (
                      <p className="text-xs text-gray-400 mb-2">
                        Sources: {r.sources_used.join(", ")}
                      </p>
                    )}
                    <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono bg-white border border-gray-100 rounded p-3 max-h-48 overflow-y-auto">
                      {r.findings}
                    </pre>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {tokenUsage?.per_agent && Object.keys(tokenUsage.per_agent).length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Token Usage &amp; Cost
          </h3>
          <div className="border border-gray-100 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 text-gray-400">
                <tr>
                  <th className="text-left font-medium px-3 py-2">Agent</th>
                  <th className="text-right font-medium px-3 py-2">Input</th>
                  <th className="text-right font-medium px-3 py-2">Output</th>
                  <th className="text-right font-medium px-3 py-2">Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {Object.entries(tokenUsage.per_agent).map(([agent, u]) => (
                  <tr key={agent}>
                    <td className="px-3 py-1.5 text-gray-700 capitalize">{agent.replace("_", " ")}</td>
                    <td className="px-3 py-1.5 text-right text-gray-500">{u.input.toLocaleString()}</td>
                    <td className="px-3 py-1.5 text-right text-gray-500">{u.output.toLocaleString()}</td>
                    <td className="px-3 py-1.5 text-right text-gray-700 font-medium">${u.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-gray-50 border-t border-gray-200">
                <tr>
                  <td className="px-3 py-2 font-semibold text-gray-700">Total</td>
                  <td className="px-3 py-2 text-right text-gray-500">{tokenUsage.total_input?.toLocaleString() ?? "—"}</td>
                  <td className="px-3 py-2 text-right text-gray-500">{tokenUsage.total_output?.toLocaleString() ?? "—"}</td>
                  <td className="px-3 py-2 text-right font-semibold text-gray-900">
                    ${tokenUsage.estimated_cost_usd?.toFixed(4) ?? "0.0000"}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          {tokenUsage.model && (
            <p className="text-xs text-gray-400 mt-1.5">Priced for {tokenUsage.model} (estimated — not a billing statement)</p>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">{label}</h3>
      {children}
    </div>
  );
}

function priorityColor(p: string) {
  return { high: "bg-red-100 text-red-700", medium: "bg-yellow-100 text-yellow-700", low: "bg-gray-100 text-gray-600" }[p] ?? "bg-gray-100";
}
