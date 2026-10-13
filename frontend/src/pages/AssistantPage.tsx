import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import type { ChatMessage, Product } from '../types';
import { chatAssistant, getProduct } from '../api';
import { useDealer } from '../context/DealerContext';
import { useCart } from '../context/CartContext';
import { ErrorBanner } from '../components/ErrorBanner';

const SESSION_STORAGE_KEY = 'vikmo_assistant_session_id';
const CHAT_STORAGE_KEY = 'vikmo_assistant_messages';

export const AssistantPage: React.FC = () => {
  const { selectedDealer } = useDealer();
  const { addToCart } = useCart();

  const [sessionId, setSessionId] = useState<string>('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  // Quick SKU popover / preview modal
  const [previewSku, setPreviewSku] = useState<Product | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize or restore session
  useEffect(() => {
    let sid = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!sid) {
      sid = crypto.randomUUID ? crypto.randomUUID() : `sess-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
      sessionStorage.setItem(SESSION_STORAGE_KEY, sid);
    }
    setSessionId(sid);

    const savedMessages = sessionStorage.getItem(CHAT_STORAGE_KEY);
    if (savedMessages) {
      try {
        setMessages(JSON.parse(savedMessages));
      } catch {
        // ignore
      }
    } else {
      // Welcome message
      setMessages([
        {
          id: 'welcome',
          role: 'assistant',
          content:
            'Hello! I am your VIKMO Dealer Assistant. I can search OEM parts catalogue, check warehouse stock levels, recommend parts for specific motorcycle models, and prepare draft orders for you.',
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  }, []);

  // Save messages to sessionStorage
  useEffect(() => {
    if (messages.length > 0) {
      sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
    }
  }, [messages]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim();
    if (!text || loading) return;

    if (!selectedDealer) {
      setError(new Error('Please select an active dealer in the top bar before chatting.'));
      return;
    }

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setLoading(true);
    setError(null);

    try {
      const response = await chatAssistant({
        session_id: sessionId,
        dealer_id: selectedDealer.id,
        message: text,
      });

      const assistantMsg: ChatMessage = {
        id: `asst-${Date.now()}`,
        role: 'assistant',
        content: response.reply,
        timestamp: new Date().toISOString(),
        cited_skus: response.cited_skus || [],
        tool_calls: response.tool_calls || [],
        actions: response.actions || [],
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setError(err);
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `I encountered an issue processing your request: ${err?.message || 'Please try again in a moment.'}`,
        timestamp: new Date().toISOString(),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleResetSession = () => {
    const newSid = crypto.randomUUID ? crypto.randomUUID() : `sess-${Date.now()}`;
    sessionStorage.setItem(SESSION_STORAGE_KEY, newSid);
    setSessionId(newSid);
    const initialMsg: ChatMessage[] = [
      {
        id: `welcome-${Date.now()}`,
        role: 'assistant',
        content: 'Session reset. How can I help you today?',
        timestamp: new Date().toISOString(),
      },
    ];
    setMessages(initialMsg);
    sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(initialMsg));
    setError(null);
  };

  const handleSkuClick = async (sku: string) => {
    try {
      setPreviewLoading(true);
      const prod = await getProduct(sku);
      setPreviewSku(prod);
    } catch (e: any) {
      alert(`Could not load details for SKU ${sku}`);
    } finally {
      setPreviewLoading(false);
    }
  };

  const samplePrompts = [
    'Do you have brake pads for a Pulsar 150?',
    'Check stock for BRK-1044',
    'What engine filters are available for Hero Splendor?',
    'Create a draft order for 2 units of BRK-1044',
  ];

  return (
    <div className="page-container chat-page-layout">
      <div className="page-header">
        <div>
          <h1 className="page-title">GenAI Dealer Assistant</h1>
          <p className="page-description">
            Natural language parts discovery, live inventory checks, and autonomous draft order creation.
          </p>
        </div>
        <div className="assistant-header-meta">
          <span className="session-id-tag">
            Session: <code>{sessionId.slice(0, 8)}...</code>
          </span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={handleResetSession}>
            🔄 New Conversation
          </button>
        </div>
      </div>

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}
      {previewLoading && <div className="floating-toast">Loading SKU details...</div>}

      <div className="chat-window-card">
        {/* Messages Stream */}
        <div className="chat-messages-container">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`chat-bubble-row ${msg.role === 'user' ? 'bubble-user-row' : 'bubble-assistant-row'}`}
            >
              <div className="chat-avatar">{msg.role === 'user' ? '👤' : '🤖'}</div>

              <div className={`chat-bubble ${msg.role === 'user' ? 'bubble-user' : 'bubble-assistant'} ${msg.isError ? 'bubble-error' : ''}`}>
                <div className="bubble-content">{msg.content}</div>

                {/* Draft Order Action Banner */}
                {msg.actions &&
                  msg.actions.map((act, idx) => {
                    if (
                      act.type === 'draft_order_created' ||
                      act.type === 'create_draft_order' ||
                      act.order_number
                    ) {
                      const ordNum = act.order_number;
                      return (
                        <div key={idx} className="action-order-banner">
                          <span className="action-icon">📋</span>
                          <div className="action-text">
                            <strong>Draft Order Created:</strong> {ordNum}
                          </div>
                          {ordNum && (
                            <Link
                              to={`/orders/${encodeURIComponent(ordNum)}`}
                              className="btn btn-sm btn-primary action-btn-view"
                            >
                              View & Confirm Order →
                            </Link>
                          )}
                        </div>
                      );
                    }
                    return null;
                  })}

                {/* Cited SKUs interactive chips */}
                {msg.cited_skus && msg.cited_skus.length > 0 && (
                  <div className="cited-skus-container">
                    <span className="cited-skus-label">Referenced SKUs:</span>
                    <div className="cited-skus-chips">
                      {msg.cited_skus.map((sku) => (
                        <button
                          key={sku}
                          type="button"
                          className="sku-chip-btn"
                          onClick={() => handleSkuClick(sku)}
                          title="Click to view details and add to cart"
                        >
                          📦 {sku}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Tool Calls Accordion */}
                {msg.tool_calls && msg.tool_calls.length > 0 && (
                  <details className="tool-calls-details">
                    <summary className="tool-calls-summary">
                      🛠️ Executed {msg.tool_calls.length} Tool Call{msg.tool_calls.length > 1 ? 's' : ''}
                    </summary>
                    <div className="tool-calls-body">
                      {msg.tool_calls.map((tc, tcIdx) => (
                        <div key={tcIdx} className="tool-call-item">
                          <span className="tool-call-name">{tc.name}</span>
                          <pre className="tool-call-args">
                            {JSON.stringify(tc.arguments, null, 2)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </details>
                )}

                <div className="bubble-time">
                  {new Date(msg.timestamp).toLocaleTimeString('en-IN', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="chat-bubble-row bubble-assistant-row">
              <div className="chat-avatar">🤖</div>
              <div className="chat-bubble bubble-assistant bubble-thinking">
                <span className="thinking-dot"></span>
                <span className="thinking-dot"></span>
                <span className="thinking-dot"></span>
                <span className="thinking-text">Querying catalogue and database...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggested Prompts */}
        <div className="chat-prompts-bar">
          <span className="prompts-label">Try asking:</span>
          {samplePrompts.map((p, idx) => (
            <button
              key={idx}
              type="button"
              className="prompt-chip"
              onClick={() => handleSendMessage(p)}
              disabled={loading}
            >
              {p}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="chat-input-bar">
          <input
            type="text"
            className="chat-text-input"
            placeholder={
              selectedDealer
                ? `Ask assistant for ${selectedDealer.name}...`
                : 'Select an active dealer in top bar to chat...'
            }
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            disabled={loading || !selectedDealer}
          />
          <button
            type="button"
            className="btn btn-primary btn-chat-send"
            onClick={() => handleSendMessage()}
            disabled={loading || !selectedDealer || !inputText.trim()}
          >
            {loading ? 'Thinking...' : 'Send 🚀'}
          </button>
        </div>
      </div>

      {/* SKU Popover Modal */}
      {previewSku && (
        <div className="modal-overlay" onClick={() => setPreviewSku(null)}>
          <div className="modal-content-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📦 Part Details: {previewSku.sku}</h3>
              <button
                type="button"
                className="btn-close-sm"
                onClick={() => setPreviewSku(null)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div className="preview-row">
                <strong>Name:</strong> <span>{previewSku.name}</span>
              </div>
              <div className="preview-row">
                <strong>Category:</strong> <span>{previewSku.category}</span>
              </div>
              <div className="preview-row">
                <strong>Fitment:</strong> <span>{previewSku.vehicle_fitment}</span>
              </div>
              <div className="preview-row">
                <strong>Price:</strong> <span className="font-bold text-accent">₹{previewSku.price}</span>
              </div>
              <div className="preview-row">
                <strong>Available Stock:</strong>{' '}
                <span className={previewSku.stock > 0 ? 'text-green' : 'text-red'}>
                  {previewSku.stock} units
                </span>
              </div>
              {previewSku.description && (
                <div className="preview-desc">
                  <small>{previewSku.description}</small>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setPreviewSku(null)}
              >
                Close
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  addToCart(previewSku, 1);
                  setPreviewSku(null);
                }}
              >
                Add 1 to Cart
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
