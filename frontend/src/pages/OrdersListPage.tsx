import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import type { Order, OrderStatus } from '../types';
import { getOrders, ApiError } from '../api';
import { useDealer } from '../context/DealerContext';
import { ErrorBanner } from '../components/ErrorBanner';
import { Pagination } from '../components/Pagination';

export const OrdersListPage: React.FC = () => {
  const { dealers, selectedDealer } = useDealer();

  const [orders, setOrders] = useState<Order[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  // Filters
  const [filterDealerId, setFilterDealerId] = useState<string>(
    selectedDealer ? selectedDealer.id.toString() : ''
  );
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [page, setPage] = useState(1);
  const pageSize = 15;

  // Sync default filter with selectedDealer if changed
  useEffect(() => {
    if (selectedDealer) {
      setFilterDealerId(selectedDealer.id.toString());
      setPage(1);
    }
  }, [selectedDealer]);

  const fetchOrdersList = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getOrders({
        dealer_id: filterDealerId ? parseInt(filterDealerId, 10) : undefined,
        status: filterStatus || undefined,
        page,
        page_size: pageSize,
      });
      setOrders(res.results || []);
      setTotalCount(res.count || 0);
    } catch (err: any) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [filterDealerId, filterStatus, page, pageSize]);

  useEffect(() => {
    fetchOrdersList();
  }, [fetchOrdersList]);

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

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dealer Orders</h1>
          <p className="page-description">
            Track, review, and manage dealership order fulfillment and status transitions.
          </p>
        </div>
        <div>
          <Link to="/" className="btn btn-primary">
            + New Order (Catalogue)
          </Link>
        </div>
      </div>

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} onRetry={fetchOrdersList} />}

      {/* Filter Bar */}
      <div className="filter-bar-card">
        <div className="filter-group">
          <label className="filter-label">Dealer:</label>
          <select
            className="select-input"
            value={filterDealerId}
            onChange={(e) => {
              setFilterDealerId(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Dealers</option>
            {dealers.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.dealer_code})
              </option>
            ))}
          </select>

          <label className="filter-label">Status:</label>
          <select
            className="select-input"
            value={filterStatus}
            onChange={(e) => {
              setFilterStatus(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All Statuses</option>
            <option value="DRAFT">DRAFT</option>
            <option value="CONFIRMED">CONFIRMED</option>
            <option value="DISPATCHED">DISPATCHED</option>
            <option value="DELIVERED">DELIVERED</option>
            <option value="CANCELLED">CANCELLED</option>
          </select>
        </div>

        {(filterDealerId || filterStatus) && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setFilterDealerId('');
              setFilterStatus('');
              setPage(1);
            }}
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Orders Table */}
      {loading ? (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Loading orders...</p>
        </div>
      ) : orders.length === 0 ? (
        <div className="empty-state">
          <h3>No orders found</h3>
          <p>There are no orders matching your current filter criteria.</p>
          <Link to="/" className="btn btn-primary mt-4">
            Browse Catalogue & Order
          </Link>
        </div>
      ) : (
        <div className="orders-table-card">
          <div className="table-responsive">
            <table className="order-table">
              <thead>
                <tr>
                  <th>Order Number</th>
                  <th>Dealer</th>
                  <th>Date & Time</th>
                  <th className="text-center">Items</th>
                  <th className="text-right">Grand Total</th>
                  <th className="text-center">Status</th>
                  <th className="text-center">Action</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => {
                  const dealer = dealers.find((d) => d.id === order.dealer_id);
                  return (
                    <tr key={order.order_number}>
                      <td>
                        <Link
                          to={`/orders/${encodeURIComponent(order.order_number)}`}
                          className="order-number-link"
                        >
                          {order.order_number}
                        </Link>
                      </td>
                      <td>
                        <div className="dealer-table-cell">
                          <strong>{dealer ? dealer.name : `Dealer #${order.dealer_id}`}</strong>
                          {dealer && <span className="dealer-code-sub">{dealer.dealer_code}</span>}
                        </div>
                      </td>
                      <td>
                        <div className="date-time-cell">
                          {new Date(order.created_at).toLocaleDateString('en-IN', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                          })}
                          <span className="time-sub">
                            {new Date(order.created_at).toLocaleTimeString('en-IN', {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                        </div>
                      </td>
                      <td className="text-center">
                        <span className="qty-tag">{order.items?.length || 0}</span>
                      </td>
                      <td className="text-right font-bold text-accent">
                        ₹{order.grand_total}
                      </td>
                      <td className="text-center">
                        <span className={`status-pill ${getStatusBadgeClass(order.status)}`}>
                          ● {order.status}
                        </span>
                      </td>
                      <td className="text-center">
                        <Link
                          to={`/orders/${encodeURIComponent(order.order_number)}`}
                          className="btn btn-sm btn-outline-primary"
                        >
                          View Details →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <Pagination
            currentPage={page}
            totalCount={totalCount}
            pageSize={pageSize}
            onPageChange={(p) => setPage(p)}
            disabled={loading}
          />
        </div>
      )}
    </div>
  );
};
