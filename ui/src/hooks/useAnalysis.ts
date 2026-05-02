import { useQuery } from "@tanstack/react-query";

async function fetchAnalysis(id: string) {
  const res = await fetch(`/api/analysis/${id}`);
  if (!res.ok) throw new Error("Failed to fetch analysis");
  return res.json();
}

export function useAnalysis(id: string) {
  return useQuery({
    queryKey: ["analysis", id],
    queryFn: () => fetchAnalysis(id),
    // Poll every 3s while analysis is running
    refetchInterval: (query) => {
      const status = query.state.data?.report?.status;
      return status === "pending" || status === "running" ? 3000 : false;
    },
  });
}
