import React, { createContext, useContext, useState, useEffect, useRef } from 'react';

export interface CartItem {
  sku: string;
  name: string;
  price: string;
  quantity: number;
  stock: number;
}

interface CartContextType {
  items: CartItem[];
  addToCart: (product: { sku: string; name: string; price: string; stock?: number }, quantity?: number) => void;
  updateQuantity: (sku: string, quantity: number) => void;
  removeFromCart: (sku: string) => void;
  clearCart: () => void;
  cartCount: number;
  cartTotalEstimated: string;
  /** A fresh UUID idempotency key, regenerated whenever cart items change. */
  idempotencyKey: string;
  /** Reset the key manually (e.g. after a successful order). */
  resetIdempotencyKey: () => void;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

const CART_STORAGE_KEY = 'vikmo_cart_items';

function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `key-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Restore cart from sessionStorage on mount
  const [items, setItems] = useState<CartItem[]>(() => {
    try {
      const saved = sessionStorage.getItem(CART_STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [idempotencyKey, setIdempotencyKey] = useState<string>(generateUUID);

  // Track whether this is the initial mount (skip key reset on initial load)
  const isInitialMount = useRef(true);

  // Persist cart to sessionStorage on every change
  useEffect(() => {
    sessionStorage.setItem(CART_STORAGE_KEY, JSON.stringify(items));

    // Reset the idempotency key whenever cart items change (but not on initial load)
    if (isInitialMount.current) {
      isInitialMount.current = false;
    } else {
      setIdempotencyKey(generateUUID());
    }
  }, [items]);

  const addToCart = (product: { sku: string; name: string; price: string; stock?: number }, quantity = 1) => {
    if (quantity <= 0) return;
    setItems((prev) => {
      const existing = prev.find((i) => i.sku === product.sku);
      if (existing) {
        return prev.map((i) =>
          i.sku === product.sku
            ? { ...i, quantity: i.quantity + quantity }
            : i
        );
      }
      return [
        ...prev,
        {
          sku: product.sku,
          name: product.name,
          price: product.price,
          quantity,
          stock: product.stock ?? 999,
        },
      ];
    });
  };

  const updateQuantity = (sku: string, quantity: number) => {
    if (quantity <= 0) {
      removeFromCart(sku);
      return;
    }
    setItems((prev) =>
      prev.map((item) => (item.sku === sku ? { ...item, quantity } : item))
    );
  };

  const removeFromCart = (sku: string) => {
    setItems((prev) => prev.filter((item) => item.sku !== sku));
  };

  const clearCart = () => {
    setItems([]);
    sessionStorage.removeItem(CART_STORAGE_KEY);
  };

  const resetIdempotencyKey = () => {
    setIdempotencyKey(generateUUID());
  };

  const cartCount = items.reduce((acc, item) => acc + item.quantity, 0);

  const cartTotalVal = items.reduce((acc, item) => {
    const p = parseFloat(item.price) || 0;
    return acc + p * item.quantity;
  }, 0);
  const cartTotalEstimated = cartTotalVal.toFixed(2);

  return (
    <CartContext.Provider
      value={{
        items,
        addToCart,
        updateQuantity,
        removeFromCart,
        clearCart,
        cartCount,
        cartTotalEstimated,
        idempotencyKey,
        resetIdempotencyKey,
      }}
    >
      {children}
    </CartContext.Provider>
  );
};

export function useCart(): CartContextType {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within a CartProvider');
  }
  return context;
}
