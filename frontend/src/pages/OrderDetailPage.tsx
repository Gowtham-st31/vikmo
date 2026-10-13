import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import type { Order, OrderStatus } from '../types';
import {
  getOrder,
  updateOrderItems,
  confirmOrder,
  dispatchOrder,
  deliverOrder,
  cancelOrder,
  ApiError,
} from '../api';
import { useDealer } from '../context/DealerContext';
import { ErrorBanner } from '../components/ErrorBanner';

export const OrderDetailPage: React.FC = () => {
  const { orderNumber } = useParams<{ orderNumber: string }>();
  const { dealers } = useDealer();

  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Edit items mode (for DRAFT orders)
  const [isEditing, setIsEditing] = useState(false);
  const [editItems, setEditItems] = useState<{ sku: string; quantity: number }[]>([]);

  const fetchOrder = useCallback(async () => {
    if (!orderNumber) return;
    try {
      setLoading(true);
      setError(null);
      const data = await getOrder(orderNumber);
      setOrder(data);
      setEditItems(data.items.map((i) => ({ sku: i.sku, quantity: i.quantity })));
    } catch (err: any) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [orderNumber]);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  const handleConfirm = async () => {
    if (!orderNumber) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await confirmOrder(orderNumber);
      setOrder(updated);
      setSuccessMessage('Order confirmed successfully! Stock allocated.');
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDispatch = async () => {
    if (!orderNumber) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await dispatchOrder(orderNumber);
      setOrder(updated);
      setSuccessMessage('Order marked as DISPATCHED.');
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeliver = async () => {
    if (!orderNumber) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await deliverOrder(orderNumber);
      setOrder(updated);
      setSuccessMessage('Order delivered successfully to dealership!');
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!orderNumber) return;
    if (!window.confirm('Are you sure you want to cancel this order?')) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await cancelOrder(orderNumber);
      setOrder(updated);
      setSuccessMessage('Order cancelled. If it was confirmed, inventory has been returned.');
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!orderNumber) return;
    if (editItems.length === 0) {
      setError(new Error('Order must contain at least one item.'));
      return;
    }
    try {
      setActionLoading(true);
      setError(null);
      const updated = await updateOrderItems(orderNumber, editItems);
      setOrder(updated);
      setIsEditing(false);
      setSuccessMessage('Order items updated successfully.');
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setError(err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleItemQtyChange = (sku: string, qty: number) => {
    setEditItems((prev) =>
      prev.map((i) => (i.sku === sku ? { ...i, quantity: Math.max(1, qty) } : i))
    );
  };

  const handleRemoveItem = (sku: string) => {
    setEditItems((prev) => prev.filter((i) => i.sku !== sku));
  };

  const getStatusBadgeClass = (status: OrderStatus) => {
    switch (status) {
      case 'DRAFT':
        return 'badge-status-draft';
      case 'CONFIRMED':
        return 'badge-status-confirmed';
      case 'DISPATCHED':
        return 'badge-status-dispatched';
      case 'DELIVERED':
        return 'badge-status-delivered';
      case 'CANCELLED':
        return 'badge-status-cancelled';
      default:
        return 'badge-status-default';
    }
  };

  if (loading) {
    return (
      <div className="page-container loading-state">
        <div className="spinner"></div>
        <p>Loading order details for {orderNumber}...</p>
      </div>
    );
  }

  if (error && !order) {
    return (
      <div className="page-container">
        <Link to="/orders" className="btn btn-secondary mb-4">
          ← Back to Orders
        </Link>
        <ErrorBanner error={error} onRetry={fetchOrder} />
      </div>
    );
  }

  if (!order) return null;

  const dealerInfo = dealers.find((d) => d.id === order.dealer_id);

  return (
    <div className="page-container">
      <div className="order-nav-breadcrumb">
        <Link to="/orders" className="breadcrumb-link">
          ← Back to Orders List
        </Link>
      </div>

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

      {successMessage && <div className="alert-box alert-success">{successMessage}</div>}

      {/* Order Header Card */}
      <div className="order-header-card">
        <div className="order-header-main">
          <div className="order-title-group">
            <span className="order-number-title">{order.order_number}</span>
            <span className={`status-pill ${getStatusBadgeClass(order.status)}`}>
              ● {order.status}
            </span>
          </div>
          <div className="order-date-group">
            <div>Created: <strong>{new Date(order.created_at).toLocaleString('en-IN')}</strong></div>
            <div>Updated: <strong>{new Date(order.updated_at).toLocaleString('en-IN')}</strong></div>
          </div>
        </div>

        <div className="order-header-meta">
          <div className="meta-block">
            <span className="meta-label">Dealer:</span>
            <span className="meta-value">
              {dealerInfo ? `${dealerInfo.name} (${dealerInfo.dealer_code})` : `Dealer #${order.dealer_id}`}
            </span>
          </div>
          {dealerInfo?.city && (
            <div className="meta-block">
              <span className="meta-label">City:</span>
              <span className="meta-value">{dealerInfo.city}</span>
            </div>
          )}
          {dealerInfo?.gstin && (
            <div className="meta-block">
              <span className="meta-label">GSTIN:</span>
              <span className="meta-value">{dealerInfo.gstin}</span>
            </div>
          )}
        </div>

        {/* Status Flow Progress Indicator */}
        <div className="status-flow-stepper">
          <div className={`step-node ${order.status !== 'CANCELLED' ? 'completed' : ''}`}>
            <span className="step-num">1</span>
            <span className="step-name">Draft</span>
          </div>
          <div className="step-line"></div>
          <div
            className={`step-node ${
              ['CONFIRMED', 'DISPATCHED', 'DELIVERED'].includes(order.status) ? 'completed' : ''
            }`}
          >
            <span className="step-num">2</span>
            <span className="step-name">Confirmed</span>
          </div>
          <div className="step-line"></div>
          <div
            className={`step-node ${
              ['DISPATCHED', 'DELIVERED'].includes(order.status) ? 'completed' : ''
            }`}
          >
            <span className="step-num">3</span>
            <span className="step-name">Dispatched</span>
          </div>
          <div className="step-line"></div>
          <div className={`step-node ${order.status === 'DELIVERED' ? 'completed' : ''}`}>
            <span className="step-num">4</span>
            <span className="step-name">Delivered</span>
          </div>
        </div>
      </div>

      {/* Action Toolbar depending on Order Status */}
      <div className="order-actions-bar">
        {order.status === 'DRAFT' && (
          <div className="actions-wrapper">
            {!isEditing ? (
              <>
                <button
                  type="button"
                  className="btn btn-primary btn-lg"
                  onClick={handleConfirm}
                  disabled={actionLoading}
                >
                  {actionLoading ? 'Confirming...' : '✓ Confirm Order'}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsEditing(true)}
                  disabled={actionLoading}
                >
                  ✏️ Edit Items
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={handleCancel}
                  disabled={actionLoading}
                >
                  ✕ Cancel Order
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="btn btn-success"
                  onClick={handleSaveEdit}
                  disabled={actionLoading}
                >
                  {actionLoading ? 'Saving...' : '💾 Save Items'}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setIsEditing(false);
                    setEditItems(order.items.map((i) => ({ sku: i.sku, quantity: i.quantity })));
                  }}
                  disabled={actionLoading}
                >
                  Cancel Edit
                </button>
              </>
            )}
          </div>
        )}

        {order.status === 'CONFIRMED' && (
          <div className="actions-wrapper">
            <button
              type="button"
              className="btn btn-primary btn-lg"
              onClick={handleDispatch}
              disabled={actionLoading}
            >
              {actionLoading ? 'Dispatching...' : '🚚 Dispatch Order'}
            </button>
            <button
              type="button"
              className="btn btn-danger"
              onClick={handleCancel}
              disabled={actionLoading}
            >
              ✕ Cancel Order (Restore Stock)
            </button>
          </div>
        )}

        {order.status === 'DISPATCHED' && (
          <div className="actions-wrapper">
            <button
              type="button"
              className="btn btn-success btn-lg"
              onClick={handleDeliver}
              disabled={actionLoading}
            >
              {actionLoading ? 'Marking Delivered...' : '📦 Mark Delivered'}
            </button>
          </div>
        )}

        {order.status === 'DELIVERED' && (
          <div className="status-terminal-banner banner-delivered">
            ✅ This order has been delivered to the dealership. No further status changes can be made.
          </div>
        )}

        {order.status === 'CANCELLED' && (
          <div className="status-terminal-banner banner-cancelled">
            🚫 This order was cancelled. Inventory reservations have been released.
          </div>
        )}
      </div>

      {/* Items Breakdown Table */}
      <div className="order-items-card">
        <h2 className="section-title">Order Line Items ({order.items.length})</h2>

        <div className="table-responsive">
          <table className="order-table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Part Description</th>
                <th className="text-right">Unit Price</th>
                <th className="text-center">Quantity</th>
                <th className="text-right">Line Subtotal</th>
                <th className="text-right">GST (18%)</th>
                <th className="text-right">Line Total</th>
                {isEditing && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {order.items.map((item) => {
                const editMatch = editItems.find((i) => i.sku === item.sku);
                const currentEditQty = editMatch ? editMatch.quantity : item.quantity;

                return (
                  <tr key={item.sku}>
                    <td>
                      <span className="sku-code">{item.sku}</span>
                    </td>
                    <td>
                      <div className="item-name-bold">{item.name}</div>
                    </td>
                    <td className="text-right">₹{item.unit_price}</td>
                    <td className="text-center">
                      {isEditing ? (
                        <input
                          type="number"
                          min="1"
                          className="input-qty-edit"
                          value={currentEditQty}
                          onChange={(e) =>
                            handleItemQtyChange(item.sku, parseInt(e.target.value, 10) || 1)
                          }
                          disabled={actionLoading}
                        />
                      ) : (
                        <span className="qty-tag">{item.quantity}</span>
                      )}
                    </td>
                    <td className="text-right">₹{item.line_subtotal}</td>
                    <td className="text-right">₹{item.line_tax}</td>
                    <td className="text-right font-semibold">₹{item.line_total}</td>
                    {isEditing && (
                      <td>
                        <button
                          type="button"
                          className="btn-remove-sm"
                          onClick={() => handleRemoveItem(item.sku)}
                          disabled={editItems.length <= 1}
                          title={editItems.length <= 1 ? 'Order must have at least one item' : 'Remove item'}
                        >
                          ✕
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Order Totals Summary Card (Exact backend string amounts!) */}
        <div className="order-summary-box">
          <div className="summary-row">
            <span className="summary-label">Items Subtotal:</span>
            <span className="summary-val">₹{order.subtotal}</span>
          </div>
          <div className="summary-row">
            <span className="summary-label">GST Total (18% rounded per line):</span>
            <span className="summary-val">₹{order.tax_total}</span>
          </div>
          <div className="summary-row grand-total-row">
            <span className="summary-label">Grand Total (Incl. Taxes):</span>
            <span className="summary-val grand-val">₹{order.grand_total}</span>
          </div>
          <small className="exact-disclaimer">
            * Values are exact API strings direct from backend database per contract §7.4.
          </small>
        </div>
      </div>
    </div>
  );
};
