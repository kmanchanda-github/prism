import { useQuery } from "@tanstack/react-query";

interface Version {
  version: number;
  edited_by: string;
  edit_source: string;
  created_at: string;
  confidence_score: number;
}

interface Props { analysisId: string; currentVersion: number; }

export function VersionHistory({ analysisId, currentVersion }: Props) {
  const { data: versions } = useQuery<Version[]>({
    queryKey: ["versions", analysisId],
    queryFn: async () => {
      const res = await fetch(`/api/analysis/${analysisId}/versions`);
      return res.json();
    },
  });

  if (!versions || versions.length <= 1) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 px-5 py-4">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Version History</h3>
      <div className="space-y-1.5">
        {versions.map((v) => (
          <div key={v.version} className={`flex items-center justify-between text-sm rounded-lg px-3 py-2 ${v.version === currentVersion ? "bg-blue-50 text-blue-800" : "text-gray-600"}`}>
            <span className="font-medium">
              v{v.version} — {v.version === 0 ? "AI Generated" : v.edit_source.replace("_", " ")}
            </span>
            <span className="text-xs text-gray-400">
              {v.edited_by !== "ai" ? v.edited_by : "AI"} · {new Date(v.created_at).toLocaleTimeString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
