import { useRef, useState } from "react";
import { loadSample, uploadCSV } from "../../api/telemetry";
import { uploadDocuments } from "../../api/documents";
import { sendChatMessage } from "../../api/chat";

/**
 * UploadPanel
 *
 * Single universal upload zone that accepts CSV, PDF, DOCX, TXT, and MD.
 *
 *  - CSV files  → telemetry pipeline (anomaly detection, session creation).
 *  - All others → document indexer (ChromaDB / RAG knowledge base).
 *
 * Props:
 *   onSuccess({ sessionId, healthScore, summaryStats }) — called after telemetry CSV upload.
 */
export default function UploadPanel({ onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [docFiles, setDocFiles] = useState([]);
  const [docStatus, setDocStatus] = useState(null);
  const [docMessage, setDocMessage] = useState("");
  const [sessionId, setSessionId] = useState(null);

  const fileInputRef = useRef(null);

  // ── helpers ───────────────────────────────────────────────────────────────

  function clearError() {
    setError(null);
  }

  function extractError(err) {
    return (
      err?.response?.data?.error?.message ||
      err?.message ||
      "An unexpected error occurred."
    );
  }

  function isCSV(file) {
    return file.name.toLowerCase().endsWith(".csv");
  }

  // ── CSV / telemetry upload ────────────────────────────────────────────────

  async function handleCsvData(promise, documents = []) {
    setLoading(true);
    clearError();
    try {
      const data = await promise;
      setSessionId(data.session_id);
      if (documents.length) {
        setDocStatus("uploading");
        const results = await uploadDocuments(data.session_id, documents);
        const total = results.reduce(
          (sum, r) => sum + (r.chunks_indexed || 0),
          0,
        );
        setDocMessage(
          `${results.length} file(s) indexed — ${total} chunk(s) added to the knowledge base.`,
        );
        setDocStatus("done");
      }
      onSuccess({
        sessionId: data.session_id,
        healthScore: data.health_score,
        summaryStats: data.summary_stats,
      });
    } catch (err) {
      setError(extractError(err));
      if (documents.length) {
        setDocStatus("error");
        setDocMessage(extractError(err));
      }
    } finally {
      setLoading(false);
    }
  }

  // ── reference document upload ─────────────────────────────────────────────

  function removeDocFile(idx) {
    setDocFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleDocUpload(files = docFiles) {
    if (!files.length) return;

    setDocStatus("uploading");
    setDocMessage("");
    try {
      const results = await uploadDocuments(sessionId, files);
      const total = results.reduce(
        (sum, r) => sum + (r.chunks_indexed || 0),
        0,
      );
      if (!sessionId && results[0]?.session_id) {
        setSessionId(results[0].session_id);
      }
      setDocMessage(
        `${results.length} file(s) indexed — ${total} chunk(s) added to the knowledge base.`,
      );
      setDocStatus("done");
      setDocFiles([]);
    } catch (err) {
      setDocMessage(extractError(err));
      setDocStatus("error");
    }
  }

  // ── unified file handler ──────────────────────────────────────────────────

  function handleFiles(files) {
    const csvFile = files.find(isCSV);
    const docFiles = files.filter((f) => !isCSV(f));

    if (csvFile) {
      handleCsvData(uploadCSV(csvFile), docFiles);
    } else if (docFiles.length) {
      setDocFiles(docFiles);
      setDocStatus(null);
      setDocMessage("");
      handleDocUpload(docFiles);
    }
  }

  // ── drag-and-drop ─────────────────────────────────────────────────────────

  function onDragOver(e) {
    e.preventDefault();
    setDragging(true);
  }

  function onDragLeave() {
    setDragging(false);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files || []);
    if (files.length) handleFiles(files);
  }

  // ── input change ──────────────────────────────────────────────────────────

  function onFileChange(e) {
    const files = Array.from(e.target.files || []);
    if (files.length) handleFiles(files);
    e.target.value = "";
  }

  // ── render ────────────────────────────────────────────────────────────────

  return (
    <div className="upload-page" style={page.root}>
      {/* ── star field ───────────────────────────────────────────────────── */}
      <div style={page.starsBg} aria-hidden="true">
        {STAR_POSITIONS.map((s, i) => (
          <div
            key={i}
            style={{
              ...page.star,
              top: s.top,
              left: s.left,
              width: s.size,
              height: s.size,
              opacity: s.opacity,
            }}
          />
        ))}
      </div>

      {/* ══ TOP HERO ROW ════════════════════════════════════════════════════ */}
      <div className="heroRow" style={page.heroRow}>
        {/* ── mission headline ───────────────────────────────────────────── */}
        <div style={page.heroLeft}>
          <h1 style={page.heroHeadline}>
            Space Telemetry to
            <br />
            <span style={page.heroAccent}>Mission Insights</span>
          </h1>
        </div>
      </div>

      {/* ══ CENTRED BRAND HEADER ═══════════════════════════════════════════ */}
      <div className="brandHeader" style={page.brandHeader}>
        <div style={page.logoRow}>
          <svg
            className="brandMark"
            width="38"
            height="38"
            viewBox="0 0 44 44"
            fill="none"
            aria-hidden="true"
          >
            <circle cx="22" cy="22" r="8" fill="url(#planetGrad)" />
            <ellipse
              cx="22"
              cy="22"
              rx="20"
              ry="7"
              stroke="url(#ringGrad)"
              strokeWidth="2"
              fill="none"
              transform="rotate(-20 22 22)"
            />
            <circle cx="36" cy="10" r="2.5" fill="#60a5fa" />
            <defs>
              <radialGradient id="planetGrad" cx="40%" cy="35%">
                <stop offset="0%" stopColor="#60a5fa" />
                <stop offset="100%" stopColor="#3b5bdb" />
              </radialGradient>
              <linearGradient id="ringGrad" x1="2" y1="22" x2="42" y2="22">
                <stop offset="0%" stopColor="#818cf8" />
                <stop offset="100%" stopColor="#60a5fa" />
              </linearGradient>
            </defs>
          </svg>
          <span className="logoText" style={page.logoText}>
            OrbitLens <span style={page.logoAI}>AI</span>
          </span>
        </div>
      </div>

      {/* ══ UPLOAD SECTION — centred ══════════════════════════════════════════ */}
      <section style={page.uploadSection}>
        <p style={page.uploadEyebrow}>Get Started</p>
        <h2 style={page.uploadHeading}>Upload Your Mission Data</h2>
        <p style={page.uploadSubtitle}>
          Drop any supported file below. CSV files start telemetry analysis
          instantly — PDF, DOCX, TXT &amp; MD files are indexed into the AI
          knowledge base.
        </p>

        {/* Drop zone — logic unchanged */}
        <div
          style={{
            ...upload.dropZone,
            ...(dragging ? upload.dropZoneDragging : {}),
            ...(loading ? upload.dropZoneDisabled : {}),
          }}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => !loading && fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Drop files here or click to browse"
          onKeyDown={(e) =>
            e.key === "Enter" && !loading && fileInputRef.current?.click()
          }
        >
          {loading ? (
            <span style={upload.spinner} aria-label="Loading" />
          ) : (
            <>
              <svg
                width="40"
                height="40"
                viewBox="0 0 40 40"
                fill="none"
                aria-hidden="true"
                style={{ marginBottom: "4px" }}
              >
                <circle
                  cx="20"
                  cy="20"
                  r="19"
                  stroke="#3b5bdb"
                  strokeWidth="1.5"
                  strokeDasharray="4 3"
                />
                <path
                  d="M20 26V14M14 20l6-6 6 6"
                  stroke="#60a5fa"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <p style={upload.dropText}>
                {dragging ? "Release to upload" : "Drag & drop files here"}
              </p>
              <p style={upload.dropHint}>
                .csv &nbsp;•&nbsp; .pdf &nbsp;•&nbsp; .docx &nbsp;•&nbsp; .txt
                &nbsp;•&nbsp; .md &nbsp;— multiple files allowed
              </p>
            </>
          )}
        </div>

        {/* Hidden universal file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.pdf,.docx,.txt,.md"
          multiple
          style={{ display: "none" }}
          onChange={onFileChange}
        />

        {/* Sample button */}
        <button
          type="button"
          style={upload.sampleButton}
          onClick={() => handleCsvData(loadSample())}
          disabled={loading}
        >
          ▶&nbsp; Try Sample Mission
        </button>

        {/* Inline CSV error */}
        {error && (
          <p role="alert" style={upload.errorText}>
            {error}
          </p>
        )}

        {/* Queued non-CSV documents */}
        {docFiles.length > 0 && (
          <div style={upload.fileList}>
            <p style={upload.fileListLabel}>Documents queued for indexing:</p>
            {docFiles.map((f, i) => (
              <div key={i} style={upload.fileItem}>
                <span style={upload.fileName}>{f.name}</span>
                <button
                  type="button"
                  style={upload.removeBtn}
                  onClick={() => removeDocFile(i)}
                  aria-label={`Remove ${f.name}`}
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              type="button"
              style={upload.uploadDocsBtn}
              onClick={handleDocUpload}
              disabled={docStatus === "uploading"}
            >
              {docStatus === "uploading"
                ? "Indexing…"
                : `Index ${docFiles.length} document(s)`}
            </button>
          </div>
        )}

        {/* Doc index status */}
        {docStatus === "done" && <p style={upload.successText}>{docMessage}</p>}
        {docStatus === "error" && (
          <p role="alert" style={upload.errorText}>
            {docMessage}
          </p>
        )}
      </section>

      {/* ══ CHAT BUBBLE — fixed bottom-right ══════════════════════════════════ */}
      <ChatBubble sessionId={sessionId} />
    </div>
  );
}

/* ── Chat bubble — interactive, RAG/Granite-ready ───────────────────────────── */
function ChatBubble({ sessionId }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([
    {
      role: "assistant",
      text: "👋 Hi! I'm OrbitLens AI, your mission intelligence assistant.\n\nAsk me anything about space telemetry, anomalies, or your uploaded mission data.",
    },
  ]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef(null);

  // Auto-scroll to latest message
  function scrollBottom() {
    setTimeout(
      () => bottomRef.current?.scrollIntoView({ behavior: "smooth" }),
      60,
    );
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || thinking) return;

    setMsgs((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setThinking(true);
    scrollBottom();

    try {
      // sendChatMessage sends { session_id, message } to POST /chat
      // session_id may be null if the user hasn't uploaded a file yet — the
      // backend accepts that and still queries RAG + Granite.
      const data = await sendChatMessage(sessionId, text);
      const reply =
        data?.answer ??
        "I couldn't reach the server right now. Please try again shortly.";
      setMsgs((prev) => [...prev, { role: "assistant", text: reply }]);
    } catch (err) {
      const msg =
        err?.response?.data?.error?.message ||
        err?.message ||
        "Connection error. Please check the backend is running.";
      setMsgs((prev) => [...prev, { role: "assistant", text: msg }]);
    } finally {
      setThinking(false);
      scrollBottom();
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  return (
    <>
      {/* ── Floating action button ─────────────────────────────────────── */}
      <div style={chat.fabWrap}>
        {!open && <span style={chat.fabLabel}>ASK ME</span>}
        <button
          type="button"
          style={chat.fab}
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "Close AI chat" : "Open AI chat"}
          title="Ask OrbitLens AI"
        >
          {open ? (
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#fff"
              strokeWidth="2.5"
              strokeLinecap="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          ) : (
            /* Robot coder icon */
            <svg
              width="36"
              height="36"
              viewBox="0 0 64 64"
              fill="none"
              aria-hidden="true"
            >
              {/* helmet */}
              <ellipse cx="32" cy="18" rx="18" ry="14" fill="#5b6aee" />
              <rect
                x="14"
                y="16"
                width="36"
                height="10"
                rx="5"
                fill="#7c88ff"
              />
              {/* face */}
              <rect
                x="16"
                y="26"
                width="32"
                height="24"
                rx="10"
                fill="#f0f0f0"
              />
              {/* eyes */}
              <circle cx="24" cy="36" r="4" fill="#1a1a2e" />
              <circle cx="40" cy="36" r="4" fill="#1a1a2e" />
              <circle cx="25.5" cy="34.5" r="1.2" fill="#fff" />
              <circle cx="41.5" cy="34.5" r="1.2" fill="#fff" />
              {/* smile */}
              <path
                d="M26 43 q6 5 12 0"
                stroke="#1a1a2e"
                strokeWidth="1.8"
                fill="none"
                strokeLinecap="round"
              />
              {/* body / code badge */}
              <rect
                x="20"
                y="52"
                width="24"
                height="14"
                rx="4"
                fill="#f0f0f0"
              />
              <text
                x="32"
                y="63"
                textAnchor="middle"
                fontSize="7"
                fontWeight="bold"
                fill="#5b6aee"
                fontFamily="monospace"
              >
                &lt;/&gt;
              </text>
            </svg>
          )}
        </button>
      </div>

      {/* ── Chat window ────────────────────────────────────────────────── */}
      {open && (
        <div style={chat.window} role="dialog" aria-label="OrbitLens AI Chat">
          {/* Header */}
          <div style={chat.header}>
            <div style={chat.headerLeft}>
              <div style={chat.headerIcon}>
                <svg width="20" height="20" viewBox="0 0 44 44" fill="none">
                  <circle cx="22" cy="22" r="8" fill="#60a5fa" />
                  <ellipse
                    cx="22"
                    cy="22"
                    rx="20"
                    ry="7"
                    stroke="#a78bfa"
                    strokeWidth="2"
                    fill="none"
                    transform="rotate(-20 22 22)"
                  />
                  <circle cx="36" cy="10" r="2.5" fill="#60a5fa" />
                </svg>
              </div>
              <div>
                <p style={chat.headerTitle}>OrbitLens AI</p>
                <p style={chat.headerSub}>IBM Granite · RAG-Grounded Answers</p>
              </div>
            </div>
            <div style={chat.onlineDot} title="Online" />
          </div>

          {/* Messages */}
          <div style={chat.messages}>
            {msgs.map((m, i) => (
              <div
                key={i}
                style={
                  m.role === "user" ? chat.msgUserWrap : chat.msgAssistantWrap
                }
              >
                {m.role === "assistant" && (
                  <div style={chat.msgAvatar}>
                    <svg width="12" height="12" viewBox="0 0 44 44" fill="none">
                      <circle cx="22" cy="22" r="8" fill="#60a5fa" />
                      <ellipse
                        cx="22"
                        cy="22"
                        rx="20"
                        ry="7"
                        stroke="#a78bfa"
                        strokeWidth="2.5"
                        fill="none"
                        transform="rotate(-20 22 22)"
                      />
                    </svg>
                  </div>
                )}
                <div
                  style={
                    m.role === "user" ? chat.msgUserBubble : chat.msgAiBubble
                  }
                >
                  {m.text.split("\n").map((line, j) => (
                    <span key={j}>
                      {line}
                      {j < m.text.split("\n").length - 1 && <br />}
                    </span>
                  ))}
                </div>
              </div>
            ))}
            {thinking && (
              <div style={chat.msgAssistantWrap}>
                <div style={chat.msgAvatar}>
                  <svg width="12" height="12" viewBox="0 0 44 44" fill="none">
                    <circle cx="22" cy="22" r="8" fill="#60a5fa" />
                    <ellipse
                      cx="22"
                      cy="22"
                      rx="20"
                      ry="7"
                      stroke="#a78bfa"
                      strokeWidth="2.5"
                      fill="none"
                      transform="rotate(-20 22 22)"
                    />
                  </svg>
                </div>
                <div style={chat.msgAiBubble}>
                  <span style={chat.dot} />
                  <span style={{ ...chat.dot, animationDelay: "0.2s" }} />
                  <span style={{ ...chat.dot, animationDelay: "0.4s" }} />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input bar */}
          <div style={chat.inputBar}>
            <input
              style={chat.input}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ask about space telemetry…"
              aria-label="Chat message input"
              disabled={thinking}
            />
            <button
              type="button"
              style={{
                ...chat.sendBtn,
                opacity: !input.trim() || thinking ? 0.4 : 1,
                cursor: !input.trim() || thinking ? "default" : "pointer",
              }}
              onClick={sendMessage}
              disabled={!input.trim() || thinking}
              aria-label="Send message"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#fff"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon
                  points="22 2 15 22 11 13 2 9 22 2"
                  fill="#fff"
                  stroke="none"
                />
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}

// ── static data ───────────────────────────────────────────────────────────────

// Deterministic star positions (no Math.random so no hydration mismatch)
const STAR_POSITIONS = [
  { top: "8%", left: "12%", size: "2px", opacity: 0.6 },
  { top: "15%", left: "78%", size: "3px", opacity: 0.8 },
  { top: "25%", left: "45%", size: "2px", opacity: 0.5 },
  { top: "5%", left: "60%", size: "2px", opacity: 0.7 },
  { top: "40%", left: "90%", size: "2px", opacity: 0.4 },
  { top: "55%", left: "5%", size: "3px", opacity: 0.6 },
  { top: "70%", left: "30%", size: "2px", opacity: 0.5 },
  { top: "80%", left: "75%", size: "2px", opacity: 0.7 },
  { top: "18%", left: "25%", size: "2px", opacity: 0.4 },
  { top: "90%", left: "50%", size: "3px", opacity: 0.3 },
  { top: "33%", left: "55%", size: "2px", opacity: 0.6 },
  { top: "62%", left: "88%", size: "2px", opacity: 0.5 },
  { top: "48%", left: "18%", size: "2px", opacity: 0.7 },
  { top: "72%", left: "62%", size: "3px", opacity: 0.4 },
  { top: "12%", left: "93%", size: "2px", opacity: 0.8 },
];

// ── page layout styles ─────────────────────────────────────────────────────────

const page = {
  root: {
    minHeight: "100vh",
    background:
      "linear-gradient(160deg, #050d1a 0%, #0a1628 40%, #0d1f3c 70%, #0a1020 100%)",
    fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif',
    color: "#f1f5f9",
    overflowX: "hidden",
  },
  heroRow: {
    display: "flex",
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    maxWidth: "1280px",
    margin: "0 auto",
    padding: "32px clamp(20px, 5vw, 64px) 24px",
  },
  heroLeft: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: "18px",
    flex: "1 1 auto",
    minWidth: 0,
    width: "100%",
  },
  brandHeader: {
    display: "flex",
    justifyContent: "center",
    width: "100%",
    padding: "0 20px 24px",
    position: "relative",
    zIndex: 1,
  },
  starsBg: {
    position: "fixed",
    inset: 0,
    pointerEvents: "none",
    zIndex: 0,
  },
  star: {
    position: "absolute",
    borderRadius: "50%",
    background: "#fff",
  },
  logoRow: {
    display: "flex",
    alignItems: "center",
    gap: "16px",
  },
  logoText: {
    fontSize: "60px",
    fontWeight: 900,
    color: "#ffffff",
    letterSpacing: "0",
    lineHeight: 1,
  },
  logoAI: {
    color: "#60a5fa",
  },
  divider: {
    width: "56px",
    height: "3px",
    background: "linear-gradient(90deg, #60a5fa, #a78bfa)",
    borderRadius: "2px",
  },
  heroHeadline: {
    margin: 0,
    fontSize: "44px",
    fontWeight: 800,
    lineHeight: 1.15,
    color: "#f1f5f9",
    letterSpacing: "0",
  },
  heroAccent: {
    background: "linear-gradient(90deg, #60a5fa 0%, #a78bfa 100%)",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
    backgroundClip: "text",
  },
  uploadSection: {
    width: "min(100% - 32px, 620px)",
    margin: "0 auto",
    padding: "0 32px 40px",
    display: "flex",
    flexDirection: "column",
    alignItems: "stretch",
    gap: "12px",
    position: "relative",
    zIndex: 1,
  },
  uploadEyebrow: {
    margin: 0,
    fontSize: "12px",
    fontWeight: 700,
    color: "#60a5fa",
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    textAlign: "center",
  },
  uploadHeading: {
    margin: 0,
    fontSize: "24px",
    fontWeight: 800,
    color: "#f1f5f9",
    textAlign: "center",
    lineHeight: 1.2,
  },
  uploadSubtitle: {
    margin: 0,
    fontSize: "14px",
    color: "#64748b",
    textAlign: "center",
    lineHeight: 1.6,
  },
};

// ── upload section styles ──────────────────────────────────────────────────────

const upload = {
  dropZone: {
    width: "100%",
    minHeight: "180px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    border: "1.5px dashed rgba(96,165,250,0.4)",
    borderRadius: "16px",
    background: "rgba(96,165,250,0.04)",
    cursor: "pointer",
    transition: "border-color 0.15s, background 0.15s",
    userSelect: "none",
    padding: "24px",
    boxSizing: "border-box",
  },
  dropZoneDragging: {
    borderColor: "#60a5fa",
    background: "rgba(96,165,250,0.10)",
  },
  dropZoneDisabled: {
    cursor: "default",
    opacity: 0.6,
  },
  dropText: {
    margin: 0,
    fontSize: "15px",
    color: "#e2e8f0",
    fontWeight: 600,
  },
  dropHint: {
    margin: 0,
    fontSize: "13px",
    color: "#64748b",
  },
  spinner: {
    display: "inline-block",
    width: "36px",
    height: "36px",
    border: "3px solid rgba(96,165,250,0.2)",
    borderTop: "3px solid #60a5fa",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  sampleButton: {
    padding: "10px 28px",
    fontSize: "14px",
    fontWeight: 600,
    color: "#60a5fa",
    background: "transparent",
    border: "1.5px solid rgba(96,165,250,0.5)",
    borderRadius: "8px",
    cursor: "pointer",
    transition: "background 0.15s, border-color 0.15s",
    alignSelf: "center",
  },
  fileList: {
    width: "100%",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    padding: "12px 14px",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: "10px",
    boxSizing: "border-box",
  },
  fileListLabel: {
    margin: 0,
    fontSize: "11px",
    fontWeight: 600,
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
  fileItem: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "8px",
  },
  fileName: {
    fontSize: "13px",
    color: "#e2e8f0",
    flex: 1,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  removeBtn: {
    background: "transparent",
    border: "none",
    color: "#f87171",
    cursor: "pointer",
    fontSize: "13px",
    padding: "0 4px",
    lineHeight: 1,
  },
  uploadDocsBtn: {
    marginTop: "4px",
    padding: "8px 20px",
    fontSize: "13px",
    fontWeight: 600,
    color: "#fff",
    background: "linear-gradient(90deg, #7c5cd8, #5b4fcf)",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    alignSelf: "flex-start",
  },
  successText: {
    margin: 0,
    fontSize: "13px",
    color: "#4ade80",
    background: "rgba(74,222,128,0.08)",
    border: "1px solid rgba(74,222,128,0.25)",
    borderRadius: "8px",
    padding: "10px 14px",
    width: "100%",
    boxSizing: "border-box",
  },
  errorText: {
    margin: 0,
    fontSize: "13px",
    color: "#f87171",
    background: "rgba(248,113,113,0.08)",
    border: "1px solid rgba(248,113,113,0.25)",
    borderRadius: "8px",
    padding: "10px 14px",
    width: "100%",
    boxSizing: "border-box",
  },
};

// ── chat bubble styles ────────────────────────────────────────────────────────

const chat = {
  fabWrap: {
    position: "fixed",
    bottom: "24px",
    right: "24px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "6px",
    zIndex: 1000,
  },
  fabLabel: {
    fontSize: "14px",
    fontWeight: 800,
    color: "#fff",
    letterSpacing: "0.12em",
    background: "linear-gradient(135deg, #3b5bdb, #7c5cd8)",
    padding: "5px 14px",
    borderRadius: "20px",
    userSelect: "none",
  },
  fab: {
    width: "84px",
    height: "84px",
    borderRadius: "50%",
    background: "linear-gradient(145deg, #1e2a4a 0%, #0d1b2e 100%)",
    border: "2px solid rgba(96,165,250,0.35)",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 4px 24px rgba(91,106,238,0.45)",
    transition: "transform 0.15s, box-shadow 0.15s",
    overflow: "hidden",
  },
  window: {
    position: "fixed",
    bottom: "124px",
    right: "24px",
    width: "min(540px, calc(100vw - 32px))",
    height: "min(720px, calc(100vh - 140px))",
    borderRadius: "16px",
    background: "#0d1b2e",
    border: "1px solid rgba(96,165,250,0.2)",
    boxShadow: "0 8px 40px rgba(0,0,0,0.6)",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    zIndex: 999,
    fontFamily: '-apple-system, "Segoe UI", system-ui, sans-serif',
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "14px 16px",
    background:
      "linear-gradient(90deg, rgba(59,91,219,0.3) 0%, rgba(124,92,216,0.3) 100%)",
    borderBottom: "1px solid rgba(96,165,250,0.12)",
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  headerIcon: {
    width: "34px",
    height: "34px",
    borderRadius: "50%",
    background: "rgba(96,165,250,0.15)",
    border: "1px solid rgba(96,165,250,0.3)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  headerTitle: {
    margin: 0,
    fontSize: "14px",
    fontWeight: 700,
    color: "#f1f5f9",
    lineHeight: 1.2,
  },
  headerSub: {
    margin: 0,
    fontSize: "11px",
    color: "#60a5fa",
    lineHeight: 1.3,
  },
  onlineDot: {
    width: "9px",
    height: "9px",
    borderRadius: "50%",
    background: "#4ade80",
    boxShadow: "0 0 6px #4ade80",
    flexShrink: 0,
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  msgAssistantWrap: {
    display: "flex",
    alignItems: "flex-end",
    gap: "8px",
  },
  msgUserWrap: {
    display: "flex",
    justifyContent: "flex-end",
  },
  msgAvatar: {
    width: "24px",
    height: "24px",
    borderRadius: "50%",
    background: "rgba(96,165,250,0.12)",
    border: "1px solid rgba(96,165,250,0.25)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    marginBottom: "2px",
  },
  msgAiBubble: {
    background: "rgba(59,91,219,0.2)",
    border: "1px solid rgba(96,165,250,0.15)",
    borderRadius: "4px 12px 12px 12px",
    padding: "9px 13px",
    fontSize: "13px",
    color: "#e2e8f0",
    lineHeight: 1.6,
    maxWidth: "82%",
    display: "flex",
    gap: "4px",
    alignItems: "center",
  },
  msgUserBubble: {
    background: "linear-gradient(135deg, #3b5bdb, #7c3cd8)",
    borderRadius: "12px 4px 12px 12px",
    padding: "9px 13px",
    fontSize: "13px",
    color: "#fff",
    lineHeight: 1.6,
    maxWidth: "82%",
  },
  dot: {
    display: "inline-block",
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    background: "#60a5fa",
    animation: "bounce 0.7s ease-in-out infinite",
  },
  inputBar: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "10px 12px",
    borderTop: "1px solid rgba(255,255,255,0.07)",
    background: "rgba(255,255,255,0.02)",
  },
  input: {
    flex: 1,
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(96,165,250,0.2)",
    borderRadius: "8px",
    padding: "8px 12px",
    fontSize: "13px",
    color: "#94a3b8",
    outline: "none",
  },
  sendBtn: {
    width: "36px",
    height: "36px",
    borderRadius: "8px",
    background: "linear-gradient(135deg, #3b5bdb, #7c5cd8)",
    border: "none",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    transition: "opacity 0.15s",
  },
};
