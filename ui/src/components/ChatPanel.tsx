import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useChat } from "../hooks/useChat";

interface Props { analysisId: string; }

export function ChatPanel({ analysisId }: Props) {
  const { messages, streaming, send } = useChat(analysisId);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  async function handleSend() {
    if (!input.trim() || streaming) return;
    const msg = input;
    setInput("");
    await send(msg);
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 flex flex-col h-[600px]">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-lg font-semibold text-gray-900">Chat with AI</h2>
        <p className="text-xs text-gray-400 mt-0.5">Ask for clarifications on the analysis</p>
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.length === 0 && (
          <p className="text-sm text-gray-400 text-center mt-8">
            Ask a question about the analysis...
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${
              m.role === "user" ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-800"
            }`}>
              <ReactMarkdown className="prose prose-sm max-w-none">{m.content}</ReactMarkdown>
              {m.suggested_edit && (
                <div className="mt-2 border border-blue-300 bg-blue-50 rounded-lg p-2 text-xs text-blue-800">
                  <span className="font-medium">Suggested edit to {m.suggested_edit.field}:</span>
                  <p className="mt-1 line-clamp-2">{m.suggested_edit.value}</p>
                  <div className="flex gap-2 mt-2">
                    <button className="px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">Apply</button>
                    <button className="px-2 py-1 text-blue-600 hover:underline">Dismiss</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {streaming && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-xl px-4 py-2.5">
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-5 py-3 border-t border-gray-100 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          disabled={streaming}
          placeholder="Ask a question..."
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        />
        <button onClick={handleSend} disabled={streaming || !input.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition">
          Send
        </button>
      </div>
    </div>
  );
}
