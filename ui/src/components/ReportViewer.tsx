import { useState } from "react";
import ReactMarkdown from "react-markdown";

interface Action { id: string; title: string; description: string; priority: string; type: string; }
interface Version { root_cause: string; workaround: string; recommended_actions: Action[]; confidence_score: number; }
interface Props { analysisId: string; version?: Version; onSave: () => void; }

export function ReportViewer({ analysisId, version, onSave }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Version | null>(null);
  const [saving, setSaving] = useState(false);

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
