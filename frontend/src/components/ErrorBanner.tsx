import React from 'react';
import { ApiError } from '../api';

interface ErrorBannerProps {
  error: Error | ApiError | string | null;
  onDismiss?: () => void;
  onRetry?: () => void;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({ error, onDismiss, onRetry }) => {
  if (!error) return null;

  const isApiError = error instanceof ApiError;
  const message = typeof error === 'string' ? error : error.message;
  const code = isApiError ? (error as ApiError).code : undefined;
  const details = isApiError ? (error as ApiError).details : undefined;

  return (
    <div className="error-banner">
      <div className="error-banner-header">
        <div className="error-banner-icon">⚠️</div>
        <div className="error-banner-content">
          <div className="error-banner-title">
            {code && <span className="error-code-badge">{code}</span>}
            <span className="error-message-text">{message}</span>
          </div>

          {code === 'INSUFFICIENT_STOCK' && Array.isArray(details) && details.length > 0 && (
            <div className="error-stock-breakdown">
              <strong>Shortage Details:</strong>
              <ul>
                {details.map((item: any, idx: number) => (
                  <li key={idx}>
                    <strong>SKU {item.sku}</strong> — Requested: <span className="text-red">{item.requested}</span>, Available in warehouse: <span className="text-yellow">{item.available}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {code !== 'INSUFFICIENT_STOCK' && details && (
            <div className="error-details-text">
              <pre>{typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details)}</pre>
            </div>
          )}
        </div>
      </div>

      <div className="error-banner-actions">
        {onRetry && (
          <button type="button" className="btn btn-sm btn-outline-warning" onClick={onRetry}>
            Retry
          </button>
        )}
        {onDismiss && (
          <button type="button" className="btn-close-sm" onClick={onDismiss} aria-label="Dismiss error">
            ✕
          </button>
        )}
      </div>
    </div>
  );
};
