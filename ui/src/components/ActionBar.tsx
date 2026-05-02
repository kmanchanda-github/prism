import { useState } from "react";

interface Props { analysisId: string; status?: string; }

type ExportFormat = "pdf" | "pptx";
type ExportTemplate = "technical" | "executive" | "customer";

export function ActionBar({ analysisId, status }: Props) {
  const [exporting, setExporting] = useState<string | null>(null);

  async function exportReport(format: ExportFormat, template: ExportTemplate) {
    const key = `${format}_${template}`;
    setExporting(key);
    try {
      const res = await fetch(`/api/analysis/${analysisId}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format, template }),
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `analysis_${analysisId.slice(0, 8)}_${template}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(null);
    }
  }

  async function sendAction(actionType: string) {
    await fetch(`/api/analysis/${analysisId}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_type: actionType, performed_by: "engineer" }),
    });
  }

  const disabled = status !== "complete";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button onClick={() => sendAction("execute_workaround")} disabled={disabled}
        className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-40 transition">
        Execute Workaround
      </button>

      <div className="w-px h-6 bg-gray-200" />

      {(["slack", "email", "webex"] as const).map((ch) => (
        <button key={ch} onClick={() => sendAction(`notify_${ch}`)} disabled={disabled}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-40 capitalize transition">
          {ch}
        </button>
      ))}

      <div className="w-px h-6 bg-gray-200" />

      {([
        { format: "pdf" as ExportFormat, template: "technical" as ExportTemplate, label: "PDF Technical" },
        { format: "pdf" as ExportFormat, template: "executive" as ExportTemplate, label: "PDF Executive" },
        { format: "pptx" as ExportFormat, template: "executive" as ExportTemplate, label: "PPT Executive" },
        { format: "pptx" as ExportFormat, template: "customer" as ExportTemplate, label: "PPT Customer" },
      ]).map(({ format, template, label }) => {
        const key = `${format}_${template}`;
        return (
          <button key={key} onClick={() => exportReport(format, template)} disabled={disabled || exporting === key}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-40 transition">
            {exporting === key ? "Generating..." : label}
          </button>
        );
      })}
    </div>
  );
}
