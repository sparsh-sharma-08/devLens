"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send, Loader2, Bot, User, Code2, FileText, MessageSquare } from "lucide-react";
import { api, type ChatMessage, type Citation } from "@/lib/api";

function CitationChip({ citation }: { citation: Citation }) {
  const filename = citation.file_path.split("/").pop() ?? citation.file_path;
  return (
    <a
      href={`#${citation.file_path}`}
      className="citation-chip"
      title={`${citation.file_path}:${citation.start_line}-${citation.end_line}`}
    >
      <Code2 size={11} />
      {filename}:{citation.start_line}
    </a>
  );
}

function Message({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div
      style={{
        display: "flex",
        gap: 14,
        flexDirection: isUser ? "row-reverse" : "row",
        marginBottom: 24,
        animation: "fadeInUp 0.3s ease",
      }}
    >
      {/* Avatar */}
      <div
        style={{
          width: 34,
          height: 34,
          borderRadius: "50%",
          flexShrink: 0,
          background: isUser
            ? "linear-gradient(135deg, var(--primary), var(--primary-dark))"
            : "linear-gradient(135deg, var(--accent), #0891b2)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {isUser ? <User size={16} color="white" /> : <Bot size={16} color="white" />}
      </div>

      {/* Bubble */}
      <div style={{ maxWidth: "75%", minWidth: 0 }}>
        <div
          style={{
            padding: "14px 18px",
            borderRadius: isUser ? "16px 4px 16px 16px" : "4px 16px 16px 16px",
            background: isUser ? "linear-gradient(135deg, var(--primary), var(--primary-dark))" : "var(--bg-card)",
            border: isUser ? "none" : "1px solid var(--border)",
            fontSize: "0.9rem",
            lineHeight: 1.7,
            color: "var(--text-primary)",
          }}
        >
          {isUser ? (
            <p style={{ margin: 0 }}>{msg.content}</p>
          ) : (
            <div className="prose-dark">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ children, className, ...props }) {
                    return (
                      <code
                        style={{
                          background: "rgba(99,102,241,0.1)",
                          padding: "2px 6px",
                          borderRadius: 4,
                          fontFamily: "var(--font-mono)",
                          fontSize: "0.85em",
                          color: "var(--text-code)",
                        }}
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  },
                  pre({ children, ...props }) {
                    return (
                      <pre
                        style={{
                          background: "var(--bg-surface)",
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          padding: "12px 16px",
                          overflowX: "auto",
                          fontFamily: "var(--font-mono)",
                          fontSize: "0.85em",
                        }}
                        {...props}
                      >
                        {children}
                      </pre>
                    );
                  },
                  p({ children, ...props }) {
                    return <p style={{ margin: "0 0 10px" }} {...props}>{children}</p>;
                  },
                }}
              >
                {msg.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Citations */}
        {msg.citations && msg.citations.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
            {msg.citations.map((c, i) => (
              <CitationChip key={i} citation={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div style={{ display: "flex", gap: 14, marginBottom: 24 }}>
      <div style={{ width: 34, height: 34, borderRadius: "50%", background: "linear-gradient(135deg, var(--accent), #0891b2)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
        <Bot size={16} color="white" />
      </div>
      <div style={{ padding: "14px 18px", background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: "4px 16px 16px 16px", display: "flex", alignItems: "center", gap: 6 }}>
        {[0, 0.2, 0.4].map((delay, i) => (
          <span key={i} style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--primary)", display: "block", animation: `pulse 1.4s ease-in-out ${delay}s infinite` }} />
        ))}
      </div>
    </div>
  );
}

const SUGGESTIONS = [
  "What does this project do?",
  "What are the main modules or components?",
  "Where is authentication handled?",
  "How is the database accessed?",
];

export default function ChatTab({ repoId }: { repoId: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await api.chat.send(repoId, text, conversationId);
      setConversationId(res.conversation_id);
      setMessages((prev) => [...prev, res.message]);
    } catch (err: any) {
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: `Sorry, I encountered an error: ${err.message}. Please try again.`,
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 200px)", minHeight: 500 }}>
      {/* Messages area */}
      <div style={{ flex: 1, overflowY: "auto", paddingRight: 8 }}>
        {messages.length === 0 ? (
          <div style={{ textAlign: "center", padding: "48px 0 32px" }}>
            <div style={{ width: 64, height: 64, borderRadius: 18, background: "linear-gradient(135deg, var(--accent), #0891b2)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
              <MessageSquare size={28} color="white" />
            </div>
            <h3 style={{ fontSize: "1.2rem", marginBottom: 8 }}>Ask anything about this codebase</h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: 28 }}>
              Every answer is grounded in the real knowledge graph and semantic embeddings.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center" }}>
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="btn-ghost"
                  style={{ fontSize: "0.82rem", padding: "8px 14px" }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ paddingTop: 8 }}>
            {messages.map((m, i) => <Message key={i} msg={m} />)}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 16, marginTop: 8 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
          <textarea
            ref={inputRef}
            className="input"
            placeholder="Ask about functions, architecture, features… (Enter to send)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            style={{
              flex: 1,
              resize: "none",
              minHeight: 48,
              maxHeight: 120,
              overflowY: "auto",
              paddingTop: 12,
              paddingBottom: 12,
              lineHeight: 1.5,
            }}
          />
          <button
            className="btn-primary"
            onClick={() => sendMessage(input)}
            disabled={loading || !input.trim()}
            style={{ padding: "12px 18px", flexShrink: 0, height: 48 }}
            id="chat-send-btn"
          >
            {loading ? <Loader2 size={17} className="animate-spin" /> : <Send size={17} />}
          </button>
        </div>
        <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 8 }}>
          Answers include clickable citations to the exact source files and lines.
        </p>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
          40% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
