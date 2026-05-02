import { useState } from "react";

interface Props {
  onSubmit: (data: Record<string, unknown>) => Promise<void>;
}

const SEVERITIES = ["P0", "P1", "P2", "P3"] as const;
const CHANNELS = ["slack", "email", "webex"] as const;

export function IncidentForm({ onSubmit }: Props) {
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    title: "", description: "", severity: "P1" as string,
    product: "", version: "", customer: "",
    notify_channels: [] as string[],
  });

  function toggle(channel: string) {
    setForm((f) => ({
      ...f,
      notify_channels: f.notify_channels.includes(channel)
        ? f.notify_channels.filter((c) => c !== channel)
        : [...f.notify_channels, channel],
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await onSubmit({
        title: form.title,
        description: form.description,
        severity: form.severity,
        metadata: { product: form.product, version: form.version, customer: form.customer },
        notify_channels: form.notify_channels,
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
        <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="e.g. Payment service timeout on checkout" />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
        <textarea required rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Describe what is happening, steps to reproduce, error messages..." />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
        <div className="flex gap-2">
          {SEVERITIES.map((s) => (
            <button key={s} type="button" onClick={() => setForm({ ...form, severity: s })}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border transition ${
                form.severity === s ? "bg-blue-600 text-white border-blue-600" : "border-gray-300 text-gray-600 hover:border-blue-400"
              }`}>
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {(["product", "version", "customer"] as const).map((field) => (
          <div key={field}>
            <label className="block text-sm font-medium text-gray-700 mb-1 capitalize">{field}</label>
            <input value={form[field]} onChange={(e) => setForm({ ...form, [field]: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
        ))}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Notify on completion</label>
        <div className="flex gap-3">
          {CHANNELS.map((c) => (
            <label key={c} className="flex items-center gap-2 cursor-pointer text-sm text-gray-700">
              <input type="checkbox" checked={form.notify_channels.includes(c)} onChange={() => toggle(c)}
                className="rounded border-gray-300" />
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </label>
          ))}
        </div>
      </div>

      <button type="submit" disabled={loading}
        className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition">
        {loading ? "Submitting..." : "Run Analysis"}
      </button>
    </form>
  );
}
