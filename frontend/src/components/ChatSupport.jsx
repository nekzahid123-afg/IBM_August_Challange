import { useState, useRef, useEffect } from "react";
import { sendChatMessage } from "../api/chat";

/**
 * ChatSupport — floating chatbot panel for mission Q&A.
 *
 * - RAG-grounded answers via POST /chat (watsonx.ai + ChromaDB)
 * - Displays retrieved source_chunks as collapsible citations
 * - Persists conversation within session
 * - Always visible as a prominent button when closed
 */
export default function ChatSupport({ sessionId }) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const historyRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to latest message
  useEffect(() => {
    if (historyRef.current) {
      historyRef.current.scrollTop = historyRef.current.scrollHeight;
    }
  }, [items, loading]);

  // Focus textarea when panel opens
  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  async function submit(e) {
    e.preventDefault();
    const text = message.trim();
    if (!text || loading) return;

    setItems((prev) => [...prev, { role: "user", text, sources: [] }]);
    setMessage("");
    setLoading(true);

    try {
      const data = await sendChatMessage(sessionId, text);
      setItems((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.answer || "No response received.",
          sources: data.source_chunks || [],
        },
      ]);
    } catch {
      setItems((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "Unable to retrieve an answer right now. Please check your connection and try again.",
          sources: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(e);
    }
  }

  function clearChat() {
    setItems([]);
    setMessage("");
  }

  // Quick starter prompts
  const starters = [
    "What anomalies were detected?",
    "How is battery health?",
    "Summarise mission status",
  ];

  return (
    <div
      className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3"
      aria-label="Mission support chat"
    >
      {/* ── Chat panel ─────────────────────────────────────────────────────── */}
      {open && (
        <div
          className="flex flex-col bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden"
          style={{
            width: "min(520px, calc(100vw - 32px))",
            height: "min(720px, calc(100vh - 120px))",
          }}
          role="dialog"
          aria-label="Mission AI chat"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-blue-700 to-blue-600 shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-white font-bold text-sm tracking-wide">
                🛰 Mission AI
              </span>
              <span className="text-blue-200 text-xs">RAG-powered</span>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="text-blue-200 hover:text-white text-xs px-2 py-1 rounded transition-colors"
                onClick={clearChat}
                title="Clear conversation"
              >
                Clear
              </button>
              <button
                type="button"
                className="text-blue-200 hover:text-white w-7 h-7 flex items-center justify-center rounded-full
                           hover:bg-blue-500/40 transition-colors text-lg leading-none"
                onClick={() => setOpen(false)}
                aria-label="Close chat"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Message history */}
          <div
            ref={historyRef}
            className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 bg-slate-900 scroll-smooth"
            aria-live="polite"
          >
            {/* Welcome / empty state */}
            {items.length === 0 && (
              <div className="flex flex-col items-center gap-4 py-6">
                <div className="w-14 h-14 rounded-2xl bg-blue-600/20 border border-blue-600/30 flex items-center justify-center text-2xl">
                  🛰
                </div>
                <div className="text-center">
                  <p className="text-white font-semibold text-sm">
                    Mission AI Assistant
                  </p>
                  <p className="text-slate-400 text-xs mt-1 leading-relaxed">
                    Ask me anything about this mission's telemetry, anomalies,
                    or attached reference documents.
                  </p>
                </div>
                {/* Quick starter prompts */}
                <div className="flex flex-col gap-2 w-full">
                  {starters.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className="w-full text-left text-xs text-blue-300 bg-blue-950/40 border border-blue-800/40
                                 rounded-xl px-3 py-2.5 hover:bg-blue-900/40 hover:border-blue-600/50 transition-all"
                      onClick={() => {
                        setMessage(s);
                        setTimeout(() => inputRef.current?.focus(), 50);
                      }}
                    >
                      {s} →
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Messages */}
            {items.map((item, idx) => (
              <div
                key={idx}
                className={[
                  "flex",
                  item.role === "user" ? "justify-end" : "justify-start",
                ].join(" ")}
              >
                <div
                  className={[
                    "max-w-[85%] rounded-2xl px-3.5 py-2.5",
                    item.role === "user"
                      ? "bg-blue-600 text-white rounded-br-sm"
                      : "bg-slate-800 border border-slate-700 text-slate-200 rounded-bl-sm",
                  ].join(" ")}
                >
                  <p className="text-sm leading-relaxed whitespace-pre-wrap break-words m-0">
                    {item.text}
                  </p>

                  {/* Source citations */}
                  {item.role === "assistant" && item.sources?.length > 0 && (
                    <details className="mt-2 border-t border-slate-600 pt-2">
                      <summary className="text-xs text-blue-400 font-semibold cursor-pointer hover:text-blue-300 transition-colors">
                        📎 {item.sources.length} source
                        {item.sources.length !== 1 ? "s" : ""}
                      </summary>
                      <div className="mt-2 flex flex-col gap-2">
                        {item.sources.map((src, si) => (
                          <div
                            key={si}
                            className="bg-slate-900 border border-slate-700 rounded-lg p-2"
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-bold text-slate-300 truncate">
                                {src.source_doc}
                              </span>
                              <span className="text-xs text-slate-500 ml-2 shrink-0">
                                {Math.round((src.similarity_score || 0) * 100)}%
                                match
                              </span>
                            </div>
                            <p className="text-xs text-slate-400 leading-relaxed line-clamp-3 m-0">
                              {src.chunk_text}
                            </p>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              </div>
            ))}

            {/* Thinking indicator */}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-slate-800 border border-slate-700 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            )}
          </div>

          {/* Input form */}
          <form
            onSubmit={submit}
            className="shrink-0 flex gap-2 p-3 border-t border-slate-700 bg-slate-800/80"
          >
            <textarea
              ref={inputRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about mission telemetry… (Enter to send)"
              className="flex-1 bg-slate-700 border border-slate-600 text-white placeholder-slate-500 rounded-xl
                         px-3 py-2 text-sm resize-none outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50
                         transition-colors leading-relaxed min-h-[40px] max-h-[100px]"
              rows={1}
              aria-label="Chat message"
              disabled={loading}
            />
            <button
              type="submit"
              className="shrink-0 w-10 h-10 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600
                         disabled:cursor-not-allowed text-white flex items-center justify-center transition-colors
                         shadow-sm shadow-blue-600/30"
              disabled={loading || !message.trim()}
              aria-label="Send message"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
          </form>
        </div>
      )}

      {/* ── Floating launcher button ──────────────────────────────────────────── */}
      <button
        type="button"
        className={[
          "flex items-center gap-3 px-7 py-4 rounded-full font-bold text-base text-white",
          "bg-gradient-to-r from-blue-700 to-blue-600",
          "shadow-xl shadow-blue-700/40 hover:shadow-blue-600/50",
          "hover:scale-105 active:scale-95 transition-all duration-200",
          "border border-blue-500/50",
        ].join(" ")}
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close mission chat" : "Open mission chat"}
      >
        <span className="text-xl">{open ? "✕" : "💬"}</span>
        <span>{open ? "Close Chat" : "ASK ME"}</span>
        {!open && items.length > 0 && (
          <span className="ml-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
            {items.filter((i) => i.role === "assistant").length}
          </span>
        )}
      </button>
    </div>
  );
}
