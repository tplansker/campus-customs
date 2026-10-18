// Shapes returned by backend/main.py.
export type StockLevel = { size: string; quantity: number }

export type Product = {
  product_id: string
  name: string
  garment_type: string
  description: string
  colors: string[]
  search_tags: string[]
  image_url: string
  price: number
  total_stock: number
  sizes_in_stock?: string[] // from GET /api/products (Products page size filter)
}

export type ProductDetail = Product & { inventory: StockLevel[] }

export type ProductCardData = Omit<Product, 'search_tags'> & { inventory: StockLevel[] }

// Search matches the agent asked the website to show on the page (POST /api/chat → page_results).
export type PageResults = { heading: string; query: string; products: ProductCardData[] }

export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  products?: ProductCardData[]
  pageResults?: PageResults
}

type ChatReply = { reply: string; products: ProductCardData[]; page_results: PageResults | null }

export type User = { id: number; first_name: string; last_name: string; email: string }

export type RegisterInput = {
  first_name: string
  last_name: string
  email: string
  password: string
  confirm_password: string
}

export class NotFoundError extends Error {}

// Error whose message comes from the backend's {"detail": "..."} and is safe to show.
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (res.status === 404) throw new NotFoundError('Not found')
  if (!res.ok) throw new Error(`Request failed (${res.status})`)
  return res.json() as Promise<T>
}

async function postJson<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    const detail = typeof data?.detail === 'string' ? data.detail : 'Something went wrong. Please try again.'
    throw new ApiError(res.status, detail)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

export const fetchProducts = () => getJson<Product[]>('/api/products')

export const fetchProduct = (id: string) =>
  getJson<ProductDetail>(`/api/products/${encodeURIComponent(id)}`)

// Session lives in an HttpOnly cookie set by the backend; the browser sends it automatically.
export async function fetchCurrentUser(): Promise<User | null> {
  const res = await fetch('/api/auth/me')
  if (res.status === 401) return null
  if (!res.ok) throw new Error(`Request failed (${res.status})`)
  return res.json()
}

export const loginRequest = (email: string, password: string) =>
  postJson<User>('/api/auth/login', { email, password })

export const registerRequest = (input: RegisterInput) => postJson<User>('/api/auth/register', input)

export const logoutRequest = () => postJson<void>('/api/auth/logout')

// Where the shopper is when they send a message, so "do you have this in pink?" resolves.
export type PageContext = {
  path: string
  product_id?: string
  results_heading?: string
  visible_product_ids?: string[]
}

// Logged in: the backend loads earlier turns from chat_messages and saves this one.
// Guest: nothing is saved, so the widget sends its recent turns as `history`.
export async function sendChatMessage(
  message: string,
  page: PageContext,
  guestHistory: { role: 'user' | 'assistant'; content: string }[] = [],
): Promise<ChatMessage> {
  const data = await postJson<ChatReply>('/api/chat', { message, page, history: guestHistory })
  return {
    role: 'assistant',
    content: data.reply,
    products: data.products,
    pageResults: data.page_results ?? undefined,
  }
}

export async function fetchChatHistory(): Promise<ChatMessage[]> {
  const res = await fetch('/api/chat/history')
  if (res.status === 401) return []
  if (!res.ok) throw new Error(`Request failed (${res.status})`)
  const rows: { role: 'user' | 'assistant'; content: string; products: ProductCardData[] }[] = await res.json()
  return rows.map(({ role, content, products }) => ({ role, content, products }))
}

export const formatPrice = (price: number) =>
  price.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

// "Notify me when it's back" for a sold-out size (logged-in customers).
export type RestockSignup = {
  product_id: string
  name: string
  size: string
  status: 'added' | 'already_on_list' | 'in_stock' | 'not_offered'
  message: string
}

export const restockRequest = (product_id: string, size: string) =>
  postJson<RestockSignup>('/api/restock', { product_id, size })
