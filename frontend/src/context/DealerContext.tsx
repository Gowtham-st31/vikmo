import React, { createContext, useContext, useState, useEffect } from 'react';
import type { Dealer } from '../types';
import { getDealers } from '../api';

interface DealerContextType {
  dealers: Dealer[];
  selectedDealer: Dealer | null;
  setSelectedDealer: (dealer: Dealer | null) => void;
  loading: boolean;
  error: string | null;
  refreshDealers: () => Promise<void>;
}

const DealerContext = createContext<DealerContextType | undefined>(undefined);

const STORAGE_KEY = 'vikmo_selected_dealer_id';

export const DealerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [dealers, setDealers] = useState<Dealer[]>([]);
  const [selectedDealer, setSelectedDealerState] = useState<Dealer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDealersList = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getDealers(1, 100);
      setDealers(res.results || []);

      const savedId = localStorage.getItem(STORAGE_KEY);
      if (savedId) {
        const found = res.results.find((d) => d.id === parseInt(savedId, 10));
        if (found) {
          setSelectedDealerState(found);
        } else if (res.results.length > 0) {
          setSelectedDealerState(res.results[0]);
          localStorage.setItem(STORAGE_KEY, res.results[0].id.toString());
        }
      } else if (res.results.length > 0) {
        // default select first dealer if none saved
        setSelectedDealerState(res.results[0]);
        localStorage.setItem(STORAGE_KEY, res.results[0].id.toString());
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load dealers');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDealersList();
  }, []);

  const setSelectedDealer = (dealer: Dealer | null) => {
    setSelectedDealerState(dealer);
    if (dealer) {
      localStorage.setItem(STORAGE_KEY, dealer.id.toString());
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  return (
    <DealerContext.Provider
      value={{
        dealers,
        selectedDealer,
        setSelectedDealer,
        loading,
        error,
        refreshDealers: fetchDealersList,
      }}
    >
      {children}
    </DealerContext.Provider>
  );
};

export function useDealer(): DealerContextType {
  const context = useContext(DealerContext);
  if (!context) {
    throw new Error('useDealer must be used within a DealerProvider');
  }
  return context;
}
