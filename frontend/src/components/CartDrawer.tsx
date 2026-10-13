import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useDealer } from '../context/DealerContext';
import { createDraftOrder } from '../api';
import { ErrorBanner } from './ErrorBanner';

interface CartDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CartDrawer: React.FC<CartDrawerProps> = ({ isOpen, onClose }) => {
  const { items, updateQuantity, removeFromCart, clearCart, cartTotalEstimated, idempotencyKey, resetIdempotencyKey } = useCart();
  const { selectedDealer } = useDealer();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<any>(null);

  if (!isOpen) return null;

  const handleCreateDraft = async () => {
    if (!selectedDealer) {
      setError('Please select an active dealer before creating an order.');
      return;
    }
    if (items.length === 0) {
      setError('Your cart is empty.');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const orderPayload = {
        dealer_id: selectedDealer.id,
        items: items.map((i) => ({
          sku: i.sku,
          quantity: i.quantity,
        })),
      };

      // Use the context's idempotency key (auto-reset when cart changes)
      const newOrder = await createDraftOrder(orderPayload, idempotencyKey);

      // Clear cart and reset key on success
      clearCart();
      resetIdempotencyKey();
      onClose();
      navigate(`/orders/${encodeURIComponent(newOrder.order_number)}`);
    } catch (err: any) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="cart-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="cart-drawer-header">
          <div className="cart-header-title">
            <h3>🛒 Order Cart ({items.length} items)</h3>
            {selectedDealer && (
              <span className="cart-dealer-tag">
                For: <strong>{selectedDealer.name}</strong> ({selectedDealer.dealer_code})
              </span>
            )}
          </div>
          <button type="button" className="btn-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="cart-drawer-body">
          {error && (
            <ErrorBanner
              error={error}
              onDismiss={() => setError(null)}
              onRetry={handleCreateDraft}
            />
          )}

          {!selectedDealer && (
            <div className="alert-box alert-warning">
              ⚠️ Please pick a dealer from the top bar to create an order.
            </div>
          )}

          {items.length === 0 ? (
            <div className="empty-cart-state">
              <span className="empty-cart-icon">📦</span>
              <p>Your cart is empty.</p>
              <small>Browse the catalogue and add items to create a draft order.</small>
            </div>
          ) : (
            <div className="cart-items-list">
              {items.map((item) => (
                <div key={item.sku} className="cart-item-card">
                  <div className="cart-item-info">
                    <div className="cart-item-sku">{item.sku}</div>
                    <div className="cart-item-name">{item.name}</div>
                    <div className="cart-item-price">₹{item.price}</div>
                  </div>
                  <div className="cart-item-controls">
                    <div className="quantity-stepper">
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.sku, item.quantity - 1)}
                        disabled={loading}
                      >
                        -
                      </button>
                      <input
                        type="number"
                        min="1"
                        value={item.quantity}
                        onChange={(e) => updateQuantity(item.sku, parseInt(e.target.value, 10) || 1)}
                        disabled={loading}
                      />
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.sku, item.quantity + 1)}
                        disabled={loading}
                      >
                        +
                      </button>
                    </div>
                    <button
                      type="button"
                      className="btn-remove"
                      onClick={() => removeFromCart(item.sku)}
                      disabled={loading}
                      title="Remove item"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {items.length > 0 && (
          <div className="cart-drawer-footer">
            <div className="cart-total-row">
              <span>Estimated Subtotal:</span>
              <span className="cart-total-value">₹{cartTotalEstimated}</span>
            </div>
            <small className="cart-tax-notice">
              * Exact 18% GST line taxes and grand totals will be calculated by the server upon draft creation.
            </small>

            <div className="idempotency-key-tag">
              Idempotency-Key: <code>{idempotencyKey.slice(0, 8)}...</code>
            </div>

            <div className="cart-drawer-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={clearCart}
                disabled={loading}
              >
                Clear Cart
              </button>
              <button
                type="button"
                className="btn btn-primary btn-lg"
                onClick={handleCreateDraft}
                disabled={loading || !selectedDealer || items.length === 0}
              >
                {loading ? 'Creating Draft Order...' : 'Create Draft Order →'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
