import React from 'react';
import { NavLink, Link } from 'react-router-dom';
import { useDealer } from '../context/DealerContext';
import { useCart } from '../context/CartContext';

interface NavbarProps {
  onOpenCart: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onOpenCart }) => {
  const { dealers, selectedDealer, setSelectedDealer, loading } = useDealer();
  const { cartCount } = useCart();

  const handleDealerChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (!val) {
      setSelectedDealer(null);
      return;
    }
    const found = dealers.find((d) => d.id === parseInt(val, 10));
    setSelectedDealer(found || null);
  };

  return (
    <header className="navbar-header">
      <div className="navbar-container">
        {/* Brand */}
        <div className="navbar-brand">
          <Link to="/" className="brand-link">
            <span className="brand-logo-icon">⚡</span>
            <div className="brand-texts">
              <span className="brand-title">VIKMO</span>
              <span className="brand-subtitle">DealerDesk</span>
            </div>
          </Link>
        </div>

        {/* Navigation Links */}
        <nav className="navbar-nav">
          <NavLink
            to="/"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            end
          >
            📦 Catalogue
          </NavLink>
          <NavLink
            to="/orders"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            📋 Orders
          </NavLink>
          <NavLink
            to="/assistant"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            🤖 AI Assistant
          </NavLink>
          <NavLink
            to="/reorder"
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            📈 Reorder & Forecast
          </NavLink>
        </nav>

        {/* Dealer Picker & Cart button */}
        <div className="navbar-actions">
          <div className="dealer-picker-container">
            <span className="dealer-picker-label">Active Dealer:</span>
            {loading ? (
              <span className="loading-dealers-tag">Loading dealers...</span>
            ) : (
              <select
                id="dealer-select"
                aria-label="Active Dealer Picker"
                className="dealer-select-input"
                value={selectedDealer ? selectedDealer.id : ''}
                onChange={handleDealerChange}
              >
                <option value="">-- Select a Dealer --</option>
                {dealers.map((dealer) => (
                  <option key={dealer.id} value={dealer.id}>
                    {dealer.name} ({dealer.dealer_code}) - {dealer.city || 'HQ'}
                  </option>
                ))}
              </select>
            )}
          </div>

          <button
            type="button"
            className="cart-toggle-btn"
            onClick={onOpenCart}
            aria-label="View Shopping Cart"
          >
            <span className="cart-icon">🛒</span>
            <span className="cart-badge-count">{cartCount}</span>
          </button>
        </div>
      </div>

      {!selectedDealer && !loading && (
        <div className="dealer-alert-banner">
          ⚠️ <strong>No Dealer Selected:</strong> Please choose your dealership from the dropdown above to view pricing and create orders.
        </div>
      )}
    </header>
  );
};
