import React, { useState, useEffect, useCallback } from 'react';
import type { ReorderSuggestion, ForecastResponse } from '../types';
import { getReorderSuggestions, getForecast, getProducts, ApiError } from '../api';
import { useCart } from '../context/CartContext';
import { ErrorBanner } from '../components/ErrorBanner';

export const ReorderPage: React.FC = () => {
  const { addToCart } = useCart();

  const [suggestions, setSuggestions] = useState<ReorderSuggestion[]>([]);
  const [productNames, setProductNames] = useState<Record<string, { name: string; price: string }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  // Filter
  const [onlyNeeded, setOnlyNeeded] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Forecast Modal state
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastError, setForecastError] = useState<string | null>(null);

  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const fetchSuggestions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getReorderSuggestions();
      setSuggestions(res.results || []);

      // Fetch catalogue products to enrich product names and prices
      try {
        const prodRes = await getProducts({ page_size: 100 });
        const map: Record<string, { name: string; price: string }> = {};
        prodRes.results.forEach((p) => {
          map[p.sku] = { name: p.name, price: p.price };
        });
        setProductNames(map);
      } catch {
        // Catalogue enrichment non-critical
      }
    } catch (err: any) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  const handleOpenForecast = async (sku: string) => {
    setSelectedSku(sku);
    setForecastLoading(true);
    setForecastError(null);
    setForecastData(null);

    try {
      const data = await getForecast(sku);
      setForecastData(data);
    } catch (err: any) {
      setForecastError(err?.message || `Failed to load 4-week forecast for ${sku}`);
    } finally {
      setForecastLoading(false);
    }
  };

  const handleAddSingleToCart = (item: ReorderSuggestion) => {
    const qty = item.reorder_qty > 0 ? item.reorder_qty : 1;
    const info = productNames[item.sku] || { name: item.sku, price: '0.00' };
    addToCart({ sku: item.sku, name: info.name, price: info.price, stock: item.current_stock }, qty);
    setToastMsg(`Added ${qty} × ${item.sku} to cart`);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const handleAddAllNeededToCart = () => {
    const needed = suggestions.filter((s) => s.reorder_qty > 0);
    if (needed.length === 0) {
      alert('No items currently have reorder_qty > 0.');
      return;
    }
    needed.forEach((item) => {
      const info = productNames[item.sku] || { name: item.sku, price: '0.00' };
      addToCart({ sku: item.sku, name: info.name, price: info.price, stock: item.current_stock }, item.reorder_qty);
    });
    setToastMsg(`Added all ${needed.length} replenishment items to cart!`);
    setTimeout(() => setToastMsg(null), 3000);
  };

  // Filtered list
  const filteredList = suggestions.filter((s) => {
    if (onlyNeeded && s.reorder_qty <= 0) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const name = productNames[s.sku]?.name?.toLowerCase() || '';
      return s.sku.toLowerCase().includes(q) || name.includes(q);
    }
    return true;
  });

  const totalSKUs = suggestions.length;
  const skusNeedingReorder = suggestions.filter((s) => s.reorder_qty > 0).length;
  const totalUnitsToReorder = suggestions.reduce((sum, s) => sum + (s.reorder_qty > 0 ? s.reorder_qty : 0), 0);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Reorder Suggestions & Demand Forecasting</h1>
          <p className="page-description">
            ML-driven inventory replenishment calculations based on lead times, 12-week sales volatility, and safety stock.
          </p>
        </div>
        <div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleAddAllNeededToCart}
            disabled={skusNeedingReorder === 0}
          >
            ⚡ Add All Needed ({totalUnitsToReorder} units) to Cart
          </button>
        </div>
      </div>

      {toastMsg && <div className="floating-toast">{toastMsg}</div>}

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} onRetry={fetchSuggestions} />}

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-title">Monitored Forecast SKUs</div>
          <div className="kpi-value">{totalSKUs}</div>
          <div className="kpi-desc">Based on lead times and sales history</div>
        </div>

        <div className="kpi-card kpi-card-warning">
          <div className="kpi-title">Stock Out Risk (Reorder Needed)</div>
          <div className="kpi-value text-accent">{skusNeedingReorder}</div>
          <div className="kpi-desc">SKUs where current stock &lt; reorder point</div>
        </div>

        <div className="kpi-card kpi-card-info">
          <div className="kpi-title">Total Units Recommended</div>
          <div className="kpi-value">{totalUnitsToReorder}</div>
          <div className="kpi-desc">Units required to restore target stock</div>
        </div>
      </div>

      {/* Filters */}
      <div className="filter-bar-card">
        <div className="search-form">
          <input
            type="text"
            className="input-text"
            placeholder="Filter by SKU or part name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="filter-toggle-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={onlyNeeded}
              onChange={(e) => setOnlyNeeded(e.target.checked)}
            />
            <span>Show only items needing reorder (reorder_qty &gt; 0)</span>
          </label>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Calculating reorder suggestions from forecasting model...</p>
        </div>
      ) : filteredList.length === 0 ? (
        <div className="empty-state">
          <h3>No reorder suggestions match</h3>
          <p>All parts have healthy inventory levels or no match for query.</p>
        </div>
      ) : (
        <div className="orders-table-card">
          <div className="table-responsive">
            <table className="order-table">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Part Name</th>
                  <th className="text-center">Current Stock</th>
                  <th className="text-center">Lead Time (Weeks)</th>
                  <th className="text-right">Lead Demand</th>
                  <th className="text-right">Safety Stock</th>
                  <th className="text-right">Reorder Point</th>
                  <th className="text-center">Suggested Reorder Qty</th>
                  <th className="text-center">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredList.map((item) => {
                  const isShort = item.reorder_qty > 0;
                  const info = productNames[item.sku];

                  return (
                    <tr key={item.sku} className={isShort ? 'row-reorder-highlight' : ''}>
                      <td>
                        <button
                          type="button"
                          className="sku-forecast-link"
                          onClick={() => handleOpenForecast(item.sku)}
                          title="Click to view 4-week demand forecast"
                        >
                          {item.sku} 📊
                        </button>
                      </td>
                      <td>
                        <div className="item-name-bold">{info?.name || 'OEM Component'}</div>
                      </td>
                      <td className="text-center">
                        <span className={`stock-tag ${item.current_stock <= 10 ? 'stock-tag-danger' : ''}`}>
                          {item.current_stock}
                        </span>
                      </td>
                      <td className="text-center">{item.lead_time_weeks}w</td>
                      <td className="text-right">{item.lead_time_demand}</td>
                      <td className="text-right">{item.safety_stock}</td>
                      <td className="text-right font-semibold">{item.reorder_point}</td>
                      <td className="text-center">
                        {isShort ? (
                          <span className="reorder-qty-badge">
                            +{item.reorder_qty} units
                          </span>
                        ) : (
                          <span className="reorder-ok-badge">0 (Healthy)</span>
                        )}
                      </td>
                      <td className="text-center">
                        <div className="reorder-action-btns">
                          <button
                            type="button"
                            className={`btn btn-sm ${isShort ? 'btn-primary' : 'btn-secondary'}`}
                            onClick={() => handleAddSingleToCart(item)}
                          >
                            + Add {isShort ? item.reorder_qty : 1}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 4-Week Forecast Modal */}
      {selectedSku && (
        <div className="modal-overlay" onClick={() => setSelectedSku(null)}>
          <div className="modal-content-card forecast-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📈 4-Week Forecast: {selectedSku}</h3>
              <button
                type="button"
                className="btn-close-sm"
                onClick={() => setSelectedSku(null)}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              {forecastLoading && (
                <div className="loading-state">
                  <div className="spinner"></div>
                  <p>Loading 4-week forecast model data...</p>
                </div>
              )}

              {forecastError && <div className="alert-box alert-warning">{forecastError}</div>}

              {forecastData && (
                <>
                  <p className="forecast-intro">
                    Predicted sales units from Ridge Regression model trained on seasonality, lag features, and rolling statistics:
                  </p>

                  <div className="forecast-bars-container">
                    {forecastData.forecast.map((fw) => {
                      const maxUnits = Math.max(
                        ...forecastData.forecast.map((f) => f.forecast_units),
                        10
                      );
                      const barPercent = Math.min(100, (fw.forecast_units / maxUnits) * 100);

                      return (
                        <div key={fw.week_start} className="forecast-bar-item">
                          <div className="bar-header">
                            <span className="bar-week">{fw.week_start}</span>
                            <span className="bar-units font-bold text-accent">
                              {fw.forecast_units} units
                            </span>
                          </div>
                          <div className="bar-track">
                            <div
                              className="bar-fill"
                              style={{ width: `${barPercent}%` }}
                            ></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="formula-box">
                    <strong>Replenishment Formula (§10):</strong>
                    <code>reorder_point = lead_time_demand + ceil(1.65 × σ × √L)</code>
                    <small>
                      Safety stock covers 95% service level against demand uncertainty over supplier lead time.
                    </small>
                  </div>
                </>
              )}
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSelectedSku(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
