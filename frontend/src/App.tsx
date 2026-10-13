import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { DealerProvider } from './context/DealerContext';
import { CartProvider } from './context/CartContext';
import { Navbar } from './components/Navbar';
import { CartDrawer } from './components/CartDrawer';
import { CataloguePage } from './pages/CataloguePage';
import { OrdersListPage } from './pages/OrdersListPage';
import { OrderDetailPage } from './pages/OrderDetailPage';
import { AssistantPage } from './pages/AssistantPage';
import { ReorderPage } from './pages/ReorderPage';

export const App: React.FC = () => {
  const [isCartOpen, setIsCartOpen] = useState(false);

  return (
    <BrowserRouter>
      <DealerProvider>
        <CartProvider>
          <div className="app-layout">
            <Navbar onOpenCart={() => setIsCartOpen(true)} />

            <main className="main-content">
              <Routes>
                <Route path="/" element={<CataloguePage />} />
                <Route path="/orders" element={<OrdersListPage />} />
                <Route path="/orders/:orderNumber" element={<OrderDetailPage />} />
                <Route path="/assistant" element={<AssistantPage />} />
                <Route path="/reorder" element={<ReorderPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>

            <CartDrawer isOpen={isCartOpen} onClose={() => setIsCartOpen(false)} />
          </div>
        </CartProvider>
      </DealerProvider>
    </BrowserRouter>
  );
};

export default App;
