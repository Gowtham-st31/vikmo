export interface Dealer {
  id: number;
  dealer_code: string;
  name: string;
  city?: string;
  phone?: string;
  email?: string;
  gstin?: string;
  credit_limit?: string;
}

export interface Product {
  sku: string;
  name: string;
  category: string;
  brand: string;
  vehicle_fitment: string;
  price: string;
  stock: number;
  description?: string;
}

export interface OrderItem {
  sku: string;
  name: string;
  quantity: number;
  unit_price: string;
  line_subtotal: string;
  line_tax: string;
  line_total: string;
}

export type OrderStatus = 'DRAFT' | 'CONFIRMED' | 'DISPATCHED' | 'DELIVERED' | 'CANCELLED';

export interface Order {
  order_number: string;
  dealer_id: number;
  status: OrderStatus;
  items: OrderItem[];
  subtotal: string;
  tax_total: string;
  grand_total: string;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiErrorDetail {
  sku?: string;
  requested?: number;
  available?: number;
  supplier_sku?: string;
  reason?: string;
  [key: string]: any;
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: ApiErrorDetail[] | any;
  };
}

export interface AssistantToolCall {
  name: string;
  arguments: Record<string, any>;
}

export interface AssistantAction {
  type: string;
  order_number?: string;
  [key: string]: any;
}

export interface AssistantResponse {
  reply: string;
  cited_skus: string[];
  tool_calls: AssistantToolCall[];
  actions: AssistantAction[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  cited_skus?: string[];
  tool_calls?: AssistantToolCall[];
  actions?: AssistantAction[];
  isError?: boolean;
}

export interface ReorderSuggestion {
  sku: string;
  product_name?: string;
  current_stock: number;
  lead_time_weeks: number;
  lead_time_demand: number;
  safety_stock: number;
  reorder_point: number;
  reorder_qty: number;
}

export interface ForecastWeek {
  week_start: string;
  forecast_units: number;
}

export interface ForecastResponse {
  sku: string;
  forecast: ForecastWeek[];
}
