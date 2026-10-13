import type {
  Dealer,
  Product,
  Order,
  PaginatedResponse,
  ApiErrorResponse,
  AssistantResponse,
  ReorderSuggestion,
  ForecastResponse,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export class ApiError extends Error {
  code: string;
  details?: any;
  status: number;

  constructor(code: string, message: string, details?: any, status = 500) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.details = details;
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorCode = 'UNKNOWN_ERROR';
    let errorMessage = `HTTP Error ${res.status}: ${res.statusText}`;
    let errorDetails: any = null;

    try {
      const data = (await res.json()) as ApiErrorResponse;
      if (data?.error) {
        errorCode = data.error.code || errorCode;
        errorMessage = data.error.message || errorMessage;
        errorDetails = data.error.details;
      }
    } catch {
      // Body was not JSON
    }

    throw new ApiError(errorCode, errorMessage, errorDetails, res.status);
  }

  // Handle empty bodies (204 No Content, etc.)
  if (res.status === 204) {
    return {} as T;
  }

  return (await res.json()) as T;
}

// ----------------- Dealers -----------------
export async function getDealers(page = 1, pageSize = 50): Promise<PaginatedResponse<Dealer>> {
  return request<PaginatedResponse<Dealer>>(`/api/dealers/?page=${page}&page_size=${pageSize}`);
}

export async function getDealer(id: number): Promise<Dealer> {
  return request<Dealer>(`/api/dealers/${id}/`);
}

// ----------------- Products / Catalogue -----------------
export async function getProducts(params: {
  search?: string;
  category?: string;
  vehicle?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResponse<Product>> {
  const searchParams = new URLSearchParams();
  if (params.search) searchParams.set('search', params.search);
  if (params.category) searchParams.set('category', params.category);
  if (params.vehicle) searchParams.set('vehicle', params.vehicle);
  if (params.page) searchParams.set('page', params.page.toString());
  if (params.page_size) searchParams.set('page_size', params.page_size.toString());

  const qs = searchParams.toString();
  return request<PaginatedResponse<Product>>(`/api/products/${qs ? `?${qs}` : ''}`);
}

export async function getProduct(sku: string): Promise<Product> {
  return request<Product>(`/api/products/${encodeURIComponent(sku)}/`);
}

// ----------------- Orders -----------------
export async function getOrders(params: {
  dealer_id?: number;
  status?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<PaginatedResponse<Order>> {
  const searchParams = new URLSearchParams();
  if (params.dealer_id) searchParams.set('dealer_id', params.dealer_id.toString());
  if (params.status) searchParams.set('status', params.status);
  if (params.page) searchParams.set('page', params.page.toString());
  if (params.page_size) searchParams.set('page_size', params.page_size.toString());

  const qs = searchParams.toString();
  return request<PaginatedResponse<Order>>(`/api/orders/${qs ? `?${qs}` : ''}`);
}

export async function getOrder(orderNumber: string): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/`);
}

export async function createDraftOrder(
  body: { dealer_id: number; items: { sku: string; quantity: number }[] },
  idempotencyKey?: string
): Promise<Order> {
  const headers: Record<string, string> = {};
  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  return request<Order>('/api/orders/', {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
}

export async function updateOrderItems(
  orderNumber: string,
  items: { sku: string; quantity: number }[]
): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/`, {
    method: 'PUT',
    body: JSON.stringify({ items }),
  });
}

export async function confirmOrder(orderNumber: string): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/confirm/`, {
    method: 'POST',
  });
}

export async function dispatchOrder(orderNumber: string): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/dispatch/`, {
    method: 'POST',
  });
}

export async function deliverOrder(orderNumber: string): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/deliver/`, {
    method: 'POST',
  });
}

export async function cancelOrder(orderNumber: string): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/cancel/`, {
    method: 'POST',
  });
}

// ----------------- Assistant -----------------
export async function chatAssistant(body: {
  session_id: string;
  dealer_id: number;
  message: string;
}): Promise<AssistantResponse> {
  return request<AssistantResponse>('/api/assistant/chat/', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ----------------- Forecasting & Reorder -----------------
export async function getReorderSuggestions(): Promise<{ results: ReorderSuggestion[] }> {
  return request<{ results: ReorderSuggestion[] }>('/api/reorder-suggestions/');
}

export async function getForecast(sku: string): Promise<ForecastResponse> {
  return request<ForecastResponse>(`/api/forecast/${encodeURIComponent(sku)}/`);
}
