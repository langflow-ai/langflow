/**
 * Popup docs chatbot. Only renders when proxyUrl is set (no keys in frontend).
 * Proxy handles Langflow + logging to Postgres.
 */

import React, { useCallback, useRef, useState } from 'react';

function parseStreamBuffer(
  buffer: string
): Array<{ event: string; data: Record<string, unknown> }> {
  const out: Array<{ event: string; data: Record<string, unknown> }> = [];
  for (const part of buffer.split('\n\n').filter(Boolean)) {
    const s = part.trim();
    if (!s) continue;
    try {
      const p = JSON.parse(s) as { event?: string; data?: Record<string, unknown> };
      if (p.event != null) out.push({ event: p.event, data: p.data ?? {} });
    } catch {
      /* ignore */
    }
  }
  return out;
}

export default function DocsChatbot({
  proxyUrl,
  open: openProp,
  onClose,
}: {
  proxyUrl: string | undefined;
  open?: boolean;
  onClose?: () => void;
}) {
  const open = openProp ?? false;
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; text: string }>>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionId = useRef<string | null>(null);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || !proxyUrl || loading) return;
    setInput('');
    setError(null);
    setMessages((m) => [...m, { role: 'user', text }, { role: 'assistant', text: '' }]);
    setLoading(true);
    if (!sessionId.current) {
      sessionId.current = `s-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    }
    let streamedContent = '';

    try {
      const res = await fetch(`${proxyUrl.replace(/\/$/, '')}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId.current }),
      });
      if (!res.ok) throw new Error(await res.text().catch(() => `HTTP ${res.status}`));
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const events = parseStreamBuffer(buffer);
          const last = buffer.lastIndexOf('\n\n');
          buffer = last >= 0 ? buffer.slice(last + 2) : buffer;
          for (const e of events) {
            if (e.event === 'token' && typeof e.data?.chunk === 'string') {
              streamedContent += e.data.chunk;
              setMessages((m) => {
                const next = [...m];
                if (next.length > 0 && next[next.length - 1].role === 'assistant') {
                  next[next.length - 1] = { role: 'assistant', text: streamedContent };
                }
                return next;
              });
            }
            if (e.event === 'error' && e.data?.error) {
              setError(String(e.data.error));
            }
          }
        }
      }
      setMessages((m) => {
        const next = [...m];
        if (next.length > 0 && next[next.length - 1].role === 'assistant' && !next[next.length - 1].text) {
          next[next.length - 1] = { role: 'assistant', text: streamedContent || 'No response.' };
        }
        return next;
      });
    } catch (e) {
      const err = e instanceof Error ? e.message : 'Request failed';
      setError(err);
      setMessages((m) => {
        const next = [...m];
        if (next.length > 0 && next[next.length - 1].role === 'assistant') {
          next[next.length - 1] = { role: 'assistant', text: err };
        }
        return next;
      });
    } finally {
      setLoading(false);
    }
  }, [proxyUrl, input, loading]);

  if (!proxyUrl) return null;

  return (
    <>
      {open && (
        <div
          role="dialog"
          aria-label="Docs chat"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1000,
            background: 'rgba(0,0,0,0.3)',
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'flex-end',
            padding: 16,
          }}
          onClick={(e) => e.target === e.currentTarget && onClose?.()}
        >
          <div
            style={{
              width: '100%',
              maxWidth: 420,
              maxHeight: '80vh',
              background: 'var(--ifm-background-color)',
              borderRadius: 12,
              boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--ifm-toc-border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong>Langflow-powered chatbot</strong>
              <button type="button" aria-label="Close" onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 20 }}>×</button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: 12, minHeight: 200 }}>
              {messages.length === 0 && <div style={{ color: 'var(--ifm-color-content-secondary)', fontSize: 14 }}>Ask a question about Langflow.</div>}
              {messages.map((msg, i) => (
                <div key={i} style={{ marginBottom: 12, textAlign: msg.role === 'user' ? 'right' : 'left' }}>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '8px 12px',
                      borderRadius: 8,
                      background: msg.role === 'user' ? 'var(--ifm-color-primary)' : 'var(--ifm-color-emphasis-200)',
                      color: msg.role === 'user' ? 'white' : 'inherit',
                      maxWidth: '85%',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontSize: 14,
                    }}
                  >
                    {msg.text || (loading && i === messages.length - 1 ? '…' : '')}
                  </span>
                </div>
              ))}
            </div>
            {error && <div style={{ padding: '8px 12px', background: '#ffebee', color: '#c62828', fontSize: 13 }}>{error}</div>}
            <div style={{ padding: 12, borderTop: '1px solid var(--ifm-toc-border-color)', display: 'flex', gap: 8 }}>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
                placeholder="Ask about the docs…"
                disabled={loading}
                style={{ flex: 1, padding: '10px 12px', borderRadius: 8, border: '1px solid var(--ifm-toc-border-color)', fontSize: 14 }}
              />
              <button type="button" onClick={send} disabled={loading || !input.trim()} style={{ padding: '10px 16px', background: '#7528FC', color: '#fff', border: 'none', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 500 }}>
                Send
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
