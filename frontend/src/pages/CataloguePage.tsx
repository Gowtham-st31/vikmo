import React, { useState, useEffect, useCallback } from 'react';
import type { Product } from '../types';
import { getProducts, ApiError } from '../api';
import { useCart } from '../context/CartContext';
import { ErrorBanner } from '../components/ErrorBanner';
import { Pagination } from '../components/Pagination';

export const CataloguePage: React.FC = () => {
  const { addToCart } = useCart();

  const [products, setProducts] = useState<Product[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  // Filters & Pagination
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [category, setCategory] = useState('');
  const [vehicle, setVehicle] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 12;

  // Local quantity inputs per SKU
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const fetchProductsList = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getProducts({
        search: search || undefined,
        category: category || undefined,
        vehicle: vehicle || undefined,
        page,
        page_size: pageSize,
      });
      setProducts(res.results || []);
      setTotalCount(res.count || 0);

      // Initialize default quantities to 1
      const initialQtys: Record<string, number> = {};
      res.results.forEach((p) => {
        initialQtys[p.sku] = quantities[p.sku] || 1;
      });
      setQuantities((prev) => ({ ...initialQtys, ...prev }));
    } catch (err: any) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [search, category, vehicle, page, pageSize]);

  useEffect(() => {
    fetchProductsList();
  }, [fetchProductsList]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput.trim());
  };

  const handleCategoryChange = (cat: string) => {
    setCategory(cat);
    setPage(1);
  };

  const handleQuantityChange = (sku: string, qty: number) => {
    setQuantities((prev) => ({
      ...prev,
      [sku]: Math.max(1, qty),
    }));
  };

  const handleAddToCart = (product: Product) => {
    const qty = quantities[product.sku] || 1;
    addToCart(product, qty);
    setToastMessage(`Added ${qty} × ${product.name} to cart!`);
    setTimeout(() => setToastMessage(null), 3000);
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">OEM Parts Catalogue</h1>
          <p className="page-description">
            Search, filter, and order genuine spare parts directly from the warehouse.
          </p>
        </div>
      </div>

      {toastMessage && <div className="floating-toast">{toastMessage}</div>}

      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} onRetry={fetchProductsList} />}

      {/* Filter and Search Bar */}
      <div className="filter-bar-card">
        <form onSubmit={handleSearchSubmit} className="search-form">
          <input
            type="text"
            className="input-text search-input"
            placeholder="Search by SKU, part name, or brand..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          <button type="submit" className="btn btn-primary">
            Search
          </button>
          {search && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setSearch('');
                setSearchInput('');
                setPage(1);
              }}
            >
              Clear
            </button>
          )}
        </form>

        <div className="filter-group">
          <label className="filter-label">Category:</label>
          <select
            className="select-input"
            value={category}
            onChange={(e) => handleCategoryChange(e.target.value)}
          >
            <option value="">All Categories</option>
            <option value="Brakes">Brakes</option>
            <option value="Filters">Filters</option>
            <option value="Engine">Engine</option>
            <option value="Transmission">Transmission</option>
            <option value="Electrical">Electrical</option>
            <option value="Suspension">Suspension</option>
          </select>

          <label className="filter-label">Vehicle Fitment:</label>
          <input
            type="text"
            className="input-text vehicle-input"
            placeholder="e.g. Pulsar 150, Activa"
            value={vehicle}
            onChange={(e) => {
              setVehicle(e.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>

      {/* Product Grid / Table */}
      {loading ? (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Loading catalogue items...</p>
        </div>
      ) : products.length === 0 ? (
        <div className="empty-state">
          <h3>No products found</h3>
          <p>Try adjusting your search query or filters.</p>
        </div>
      ) : (
        <div className="product-grid">
          {products.map((product) => {
            const isOutOfStock = product.stock <= 0;
            const isLowStock = product.stock > 0 && product.stock <= 10;
            const currentQty = quantities[product.sku] || 1;

            return (
              <div key={product.sku} className="product-card">
                <div className="product-card-header">
                  <span className="product-sku-tag">{product.sku}</span>
                  <span className="product-category-tag">{product.category}</span>
                </div>

                <h3 className="product-name">{product.name}</h3>

                <div className="product-meta">
                  <div className="meta-item">
                    <span className="meta-label">Brand:</span>
                    <span className="meta-value">{product.brand || 'OEM'}</span>
                  </div>
                  <div className="meta-item">
                    <span className="meta-label">Fitment:</span>
                    <span className="meta-value">{product.vehicle_fitment}</span>
                  </div>
                </div>

                <div className="product-pricing-stock">
                  <div className="price-display">
                    <span className="currency-symbol">₹</span>
                    <span className="price-value">{product.price}</span>
                  </div>

                  <div className="stock-display">
                    {isOutOfStock ? (
                      <span className="stock-pill stock-out">Out of stock (0)</span>
                    ) : isLowStock ? (
                      <span className="stock-pill stock-low">Low stock ({product.stock})</span>
                    ) : (
                      <span className="stock-pill stock-available">In stock ({product.stock})</span>
                    )}
                  </div>
                </div>

                <div className="product-card-actions">
                  <div className="quantity-controls">
                    <button
                      type="button"
                      className="btn-qty"
                      onClick={() => handleQuantityChange(product.sku, currentQty - 1)}
                    >
                      -
                    </button>
                    <input
                      type="number"
                      min="1"
                      className="input-qty"
                      value={currentQty}
                      onChange={(e) =>
                        handleQuantityChange(product.sku, parseInt(e.target.value, 10) || 1)
                      }
                    />
                    <button
                      type="button"
                      className="btn-qty"
                      onClick={() => handleQuantityChange(product.sku, currentQty + 1)}
                    >
                      +
                    </button>
                  </div>

                  <button
                    type="button"
                    className="btn btn-primary btn-add-cart"
                    onClick={() => handleAddToCart(product)}
                  >
                    🛒 Add to Cart
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination Controls */}
      <Pagination
        currentPage={page}
        totalCount={totalCount}
        pageSize={pageSize}
        onPageChange={(newPage) => setPage(newPage)}
        disabled={loading}
      />
    </div>
  );
};
