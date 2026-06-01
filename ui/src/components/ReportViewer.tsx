import { useState } from "react";
import ReactMarkdown from "react-markdown";

interface Action { id: string; title: string; description: string; priority: string; type: string; }
interface SubReport { agent: string; findings: string; sources_used: string[]; confidence: number; }
interface Version {
  root_cause: string; workaround: string; recommended_actions: Action[];
  confidence_score: number; sub_reports?: SubReport[];
}
interface Props { analysisId: string; version?: Version; onSave: () => void; onApplyEdit?: (field: string, value: string) => void; }

export function ReportViewer({ analysisId, version, onSave, onApplyEdit }: Props) {
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
