import React from 'react';

interface PaginationProps {
  currentPage: number;
  totalCount: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  disabled?: boolean;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalCount,
  pageSize,
  onPageChange,
  disabled = false,
}) => {
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  if (totalPages <= 1) return null;

  return (
    <div className="pagination-container">
      <div className="pagination-info">
        Showing Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong> ({totalCount} items total)
      </div>
      <div className="pagination-buttons">
        <button
          type="button"
          className="btn btn-sm btn-secondary"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={disabled || currentPage <= 1}
        >
          ← Previous
        </button>
        <span className="pagination-badge">
          {currentPage} / {totalPages}
        </span>
        <button
          type="button"
          className="btn btn-sm btn-secondary"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={disabled || currentPage >= totalPages}
        >
          Next →
        </button>
      </div>
    </div>
  );
};
