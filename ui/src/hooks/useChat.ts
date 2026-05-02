import { useState } from "react";

export interface ChatEntry {
  role: "user" | "assistant";
  content: string;
  suggested_edit?: { field: string; value: string } | null;
}

export function useChat(analysisId: string) {
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [streaming, setStreaming] = useState(false);

  async function send(message: string): Promise<{ suggested_edit?: Record<string, string> | null }> {
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setStreaming(true);

    let assistantContent = "";
    let suggestedEdit = null;

    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    const res = await fetch(`/api/analysis/${analysisId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const lines = decoder.decode(value).split("\n");
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = JSON.parse(line.slice(6));
        if (data.done) {
          suggestedEdit = data.suggested_edit;
        } else if (data.token) {
          assistantContent += data.token;
          setMessages((prev) => [
            ...prev.slice(0, -1),
            { role: "assistant", content: assistantContent },
          ]);
        }
      }
    }

    setStreaming(false);
    if (suggestedEdit) {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: "assistant", content: assistantContent, suggested_edit: suggestedEdit },
      ]);
    }

    return { suggested_edit: suggestedEdit };
  }

  return { messages, streaming, send };
}
