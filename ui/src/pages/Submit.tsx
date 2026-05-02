import { useNavigate } from "react-router-dom";
import { IncidentForm } from "../components/IncidentForm";

export function SubmitPage() {
  const navigate = useNavigate();

  async function handleSubmit(data: Record<string, unknown>) {
    const res = await fetch("/api/analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const json = await res.json();
    navigate(`/analysis/${json.id}`);
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="bg-white rounded-xl shadow-md w-full max-w-2xl p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Submit Incident for AI Analysis</h1>
        <IncidentForm onSubmit={handleSubmit} />
      </div>
    </div>
  );
}
