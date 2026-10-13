# VIKMO DealerDesk

**Track**: AI/ML Track (`aiml`)

This project implements a backend for a distributor of motorcycle and car parts. It handles core inventory and ordering, AI-powered dealer assistance (GenAI), and sales forecasting (ML).

## Setup & Running

This project strictly requires PostgreSQL for its concurrency rules and does not support SQLite. It requires the following environment variables:
- `DATABASE_URL` (required, must be a PostgreSQL connection string)
- `GEMINI_API_KEY` (required for Dealer Assistant)

To run the project locally:

```bash
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py seed_data
python manage.py runserver 0.0.0.0:8000 --noreload
```

## Running Tests

To run the smoke tests for the AI/ML track:

```bash
python smoke_test.py --base-url http://localhost:8000 --track aiml
```

To run all Django unit tests across all apps:

```bash
python manage.py test
```

## AI / ML details

**LLM Provider**: Google Gemini
**Model**: `gemini-2.5-flash`

## Optional Parts Attempted
- **Supplier Catalogue Sync (`sync/`)**: Implemented `/api/sync/supplier/` endpoint to ingest external supplier parts (`supplier_mock/`), reconcile against local `Product` and `Inventory` records, and handle cursor pagination and idempotency safely.
- **Frontend Portal (`frontend/`)**: Built a complete dealer portal web application using React + Vite + TypeScript (Part E bonus).

## Frontend (Dealer Portal)

A responsive single-page web app built with React, Vite, and TypeScript that connects directly to the DealerDesk API.

### How to Run

1. Make sure the backend server is running on `http://localhost:8000`:
   ```bash
   python manage.py runserver 0.0.0.0:8000 --noreload
   ```
2. In a separate terminal, navigate to the `frontend` folder and launch the Vite dev server:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
3. Open your browser at: **`http://localhost:5173`**

*Note: The frontend dev server proxies all `/api` requests to `http://localhost:8000`. You can override the target API URL by setting `VITE_API_BASE`.*

### Screens & Features

1. **Dealer Picker (Top Navigation Bar)**:
   - Loads dealers from `GET /api/dealers/`.
   - Allows choosing the active dealership, persisting choice in `localStorage`.
   - Adapts orders, pricing, and assistant context to the active dealer.
   - Prompts user if no dealer is selected.
2. **OEM Parts Catalogue (`/`)**:
   - Product browsing with search query (`?search=`), category filter, vehicle fitment filter, and pagination.
   - Displays real-time stock indicators (in stock, low stock warning, out of stock).
   - Quantity selector and "Add to Cart" functionality.
3. **Cart & Draft Order Drawer**:
   - Slide-over drawer with item management (quantity increment/decrement, remove item, clear cart).
   - One-click "Create Draft Order" via `POST /api/orders/`.
   - Sends unique `Idempotency-Key` UUID per attempt (reused on retry upon failure).
   - Automatically redirects to the created order's detail page.
4. **Order Detail (`/orders/:orderNumber`)**:
   - Displays order number, dealer metadata, creation/update timestamps, and visual status stepper.
   - Full line items table with unit price, line subtotal, 18% GST tax, and line total.
   - Exact backend string representations for monetary values (no JavaScript float rounding discrepancies).
   - Status-aware action controls:
     - **DRAFT**: "Confirm Order", "Edit Items" (inline quantity editing via `PUT /api/orders/:orderNumber/`), "Cancel Order".
     - **CONFIRMED**: "Dispatch Order", "Cancel Order" (restores reserved stock).
     - **DISPATCHED**: "Mark Delivered".
     - **DELIVERED / CANCELLED**: Terminal status banners.
5. **Orders List (`/orders`)**:
   - View and filter orders by dealer and status (`DRAFT`, `CONFIRMED`, `DISPATCHED`, `DELIVERED`, `CANCELLED`).
   - Server-side pagination and direct navigation to order details.
6. **GenAI Dealer Assistant Chat (`/assistant`)**:
   - Conversational assistant powered by `POST /api/assistant/chat/` with session ID persisted in `sessionStorage`.
   - Interactive cited SKU chips with quick part preview modal and 1-click cart addition.
   - Action notifications with direct links to created draft orders.
   - Expandable tool calls inspection accordion (`search_parts`, `check_stock`, `create_draft_order`).
   - Pre-built suggested prompts and loading indicators.
7. **Reorder Suggestions & Demand Forecasting (`/reorder`)**:
   - Fetches replenishment suggestions from `GET /api/reorder-suggestions/`.
   - Summary KPI cards for inventory health and stock-out risks.
   - Highlights items where `reorder_qty > 0`.
   - Quick individual and batch ("Add All Needed") cart replenishment.
   - Interactive 4-week demand forecast visualizer modal powered by `GET /api/forecast/:sku/`.
8. **Typed Error Handling**:
   - Intercepts backend error payloads (`{ error: { code, message, details } }`).
   - Rich alert banners specifically formatting `INSUFFICIENT_STOCK` (HTTP 409) with itemized requested vs available quantities.

## Video Walkthrough
[Insert Unlisted YouTube/Loom Link Here]

## Assumptions
- The forecasting script is run offline and writes to `ml/forecast.csv`, which is then read directly by the API.
- The assistant is instructed to fetch live data using tool calls rather than relying solely on the context window. 
- All money formatting strictly returns strings with two decimals (`ROUND_HALF_UP`) as required by the API contract.
