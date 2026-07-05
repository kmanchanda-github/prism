import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

interface EvaluationResult {
  analysis_id: string;
  accuracy_score: number;
  what_it_got_right: string;
  what_it_missed: string;
  hint_summary: string;
  created_at: string;
}

interface Props { analysisId: string; status?: string; }

export function EvaluationPanel({ analysisId, status }: Props) {
  const queryClient = useQueryClient();
  const [resolution, setResolution] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: evaluation, isLoading } = useQuery<EvaluationResult | null>({
    queryKey: ["evaluation", analysisId],
    queryFn: async () => {
      const res = await fetch(`/api/analysis/${analysisId}/evaluation`);
      if (res.status === 404) return null;
      return res.json();
    },
    enabled: status === "complete",
  });

  async function submit() {
    if (!resolution.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`/api/analysis/${analysisId}/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actual_resolution: resolution }),
      });
      if (!res.ok) throw new Error("Evaluation failed");
      queryClient.setQueryData(["evaluation", analysisId], await res.json());
    } catch {
      setError("Couldn't evaluate this analysis. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (status !== "complete" || isLoading) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 px-5 py-4">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
        Evaluate Against Actual Resolution
      </h3>

      {evaluation ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
              evaluation.accuracy_score >= 0.7 ? "bg-green-100 text-green-700"
              : evaluation.accuracy_score >= 0.4 ? "bg-yellow-100 text-yellow-700"
              : "bg-red-100 text-red-700"
            }`}>
              {Math.round(evaluation.accuracy_score * 100)}% accurate
            </span>
            <span className="text-xs text-gray-400">
              evaluated {new Date(evaluation.created_at).toLocaleString()}
            </span>
          </div>
          {evaluation.what_it_got_right && (
            <p className="text-sm text-gray-700"><strong className="text-gray-500">Got right:</strong> {evaluation.what_it_got_right}</p>
          )}
          {evaluation.what_it_missed && (
            <p className="text-sm text-gray-700"><strong className="text-gray-500">Missed:</strong> {evaluation.what_it_missed}</p>
          )}
          <div className="border border-blue-200 bg-blue-50 rounded-lg p-3">
            <p className="text-xs font-semibold text-blue-700 uppercase tracking-wide mb-1">Lesson for future runs</p>
            <p className="text-sm text-blue-800">{evaluation.hint_summary}</p>
            <p className="text-xs text-blue-500 mt-1.5">
              Applied automatically to the next matching-service incident's synthesis.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <textarea
            rows={3}
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            placeholder="What actually happened? How was this really resolved?"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
          <div className="flex items-center gap-3">
            <button
              onClick={submit}
              disabled={submitting || !resolution.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {submitting ? "Evaluating..." : "Evaluate"}
            </button>
            {error && <span className="text-xs text-red-600">{error}</span>}
          </div>
        </div>
      )}
    </div>
  );
}
