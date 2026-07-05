import { useCallback } from "react";
import { useParams } from "react-router-dom";
import { useAnalysis } from "../hooks/useAnalysis";
import { ActionBar } from "../components/ActionBar";
import { ChatPanel } from "../components/ChatPanel";
import { EvaluationPanel } from "../components/EvaluationPanel";
import { ReportViewer } from "../components/ReportViewer";
import { VersionHistory } from "../components/VersionHistory";

export function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, refetch } = useAnalysis(id!);

  const handleApplyEdit = useCallback(async (field: string, value: string) => {
    const { version } = data ?? {};
    if (!version || !id) return;
    const updated = {
      root_cause: version.root_cause,
      workaround: version.workaround,
      recommended_actions: version.recommended_actions,
      [field]: value,
      edit_source: "chat_suggestion",
    };
    await fetch(`/api/analysis/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updated),
    });
    refetch();
  }, [data, id, refetch]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Running AI analysis...</p>
        </div>
      </div>
    );
  }

  const { report, version } = data ?? {};

  if (report?.status === "failed") {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <h2 className="text-red-700 font-semibold text-lg">Analysis Failed</h2>
          <p className="text-red-600 mt-2">The analysis could not be completed. You can re-run it below.</p>
          <button onClick={() => refetch()} className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700">
            Re-run Analysis
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{version?.analysis_id?.slice(0, 8) ?? id?.slice(0, 8)}</h1>
            <div className="flex items-center gap-2 mt-1">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${severityColor(report?.severity)}`}>
                {report?.severity ?? "—"}
              </span>
              <span className="text-sm text-gray-500">
                {report?.status === "complete" ? "Analysis complete" : "Running..."}
              </span>
              {version && (
                <span className="text-sm text-gray-400">
                  Confidence: {(version.confidence_score * 100).toFixed(0)}%
                </span>
              )}
            </div>
          </div>
          <button onClick={() => refetch()} className="text-sm text-blue-600 hover:underline">
            Refresh
          </button>
        </div>
      </header>

      {/* Main layout */}
      <div className="max-w-7xl mx-auto px-6 py-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <ReportViewer analysisId={id!} version={version} tokenUsage={report?.token_usage} onSave={refetch} onApplyEdit={handleApplyEdit} />
          <VersionHistory analysisId={id!} currentVersion={report?.current_version ?? 0} />
          <EvaluationPanel analysisId={id!} status={report?.status} />
        </div>
        <ChatPanel analysisId={id!} onApplyEdit={(e) => handleApplyEdit(e.field, e.value)} />
      </div>

      {/* Action bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-6 py-3">
        <div className="max-w-7xl mx-auto">
          <ActionBar analysisId={id!} status={report?.status} />
        </div>
      </div>
    </div>
  );
}

function severityColor(severity?: string): string {
  return { P0: "bg-red-100 text-red-700", P1: "bg-orange-100 text-orange-700",
           P2: "bg-yellow-100 text-yellow-700", P3: "bg-gray-100 text-gray-600" }[severity ?? ""] ?? "bg-gray-100 text-gray-600";
}
