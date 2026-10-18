import { useEffect, useRef, useState, type FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import { Link, matchPath, useLocation, useNavigate } from 'react-router-dom'
import {
  ApiError,
  fetchChatHistory,
  formatPrice,
  sendChatMessage,
  type ChatMessage,
  type PageContext,
  type PageResults,
  type ProductCardData,
} from '../api'
import { useAuth } from '../useAuth'
import { usePageResults } from '../usePageResults'
import Bulldog from './Bulldog'

const MAX_CHAT_CARDS = 4 // mini cards inside a bubble; the rest go on the page
const GUEST_HISTORY_TURNS = 10 // a guest's recent turns, sent with each message (nothing is stored)

// App.tsx remounts this component (key = user id) on login/logout, so state never leaks between users.
export default function ChatWidget() {
  const { user, loading: authLoading } = useAuth()
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [historyState, setHistoryState] = useState<'idle' | 'loading' | 'loaded' | 'error'>('idle')
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const { show, results } = usePageResults()
  const navigate = useNavigate()
  const location = useLocation()

  // What the shopper is looking at right now; sent with every message.
  function pageContext(): PageContext {
    const detail = matchPath('/products/:productId', location.pathname)
    const showingResults = location.pathname === '/products' && results
    return {
      path: location.pathname,
      product_id: detail?.params.productId,
      results_heading: showingResults ? results.heading : undefined,
      visible_product_ids: showingResults ? results.products.slice(0, 12).map((p) => p.product_id) : undefined,
    }
  }

  // Put search matches on the Products page as full product cards.
  function showOnPage(results: PageResults) {
    show(results)
    if (location.pathname !== '/products') navigate('/products')
    // On phones the panel covers the page, so get out of the way.
    if (window.matchMedia('(max-width: 760px)').matches) setOpen(false)
  }

  // Results for a message: what the agent sent live, or (for reloaded history) the saved
  // products when there are more than fit in the bubble.
  function resultsFor(index: number, m: ChatMessage): PageResults | null {
    if (m.pageResults) return m.pageResults
    if (!m.products || m.products.length <= MAX_CHAT_CARDS) return null
    const asked = messages.slice(0, index).reverse().find((x) => x.role === 'user')
    return { heading: 'Products from chat', query: asked?.content ?? '', products: m.products }
  }

  const greeting: ChatMessage = {
    role: 'assistant',
    content: `Woof, hi${user ? ` ${user.first_name}` : ''}! I'm **Handsome Dan**, the Campus Customs bulldog. Ask me about products, sizes, colors, or stock. Boola Boola!`,
  }

  // AIM-style screen names (1996 vibes). Dan's is fixed; the shopper's comes from their account.
  const DAN_SN = 'HandsomeDan96'
  const mySn = user ? `${user.first_name}${user.last_name}`.replace(/\s+/g, '') || 'Bulldog' : 'Guest1996'

  // One-tap starter questions; on a product page they're about that item.
  const onProductPage = !!matchPath('/products/:productId', location.pathname)
  const starters = onProductPage
    ? ['Is this in stock in my size?', 'What colors does this come in?', 'Show me similar items']
    : ['What hoodies do you have?', 'Gift ideas for a Yale dad', 'T-shirts under $35']

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages, sending, open])

  useEffect(() => {
    if (open && !authLoading) inputRef.current?.focus()
  }, [open, authLoading])

  function loadHistory() {
    setHistoryState('loading')
    fetchChatHistory()
      .then((h) => {
        setMessages(h)
        setHistoryState('loaded')
      })
      .catch(() => setHistoryState('error'))
  }

  function toggle() {
    const next = !open
    setOpen(next)
    if (next && user && historyState === 'idle') loadHistory() // guests have no saved history
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    void send(input)
  }

  async function send(raw: string) {
    const text = raw.trim()
    if (!text || sending) return

    const guestHistory = user
      ? []
      : messages.slice(-GUEST_HISTORY_TURNS).map(({ role, content }) => ({ role, content }))
    setMessages((m) => [...m, { role: 'user', content: text }])
    setInput('')
    setError('')
    setSending(true)
    try {
      const reply = await sendChatMessage(text, pageContext(), guestHistory)
      setMessages((m) => [...m, reply])
      if (reply.pageResults) showOnPage(reply.pageResults)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Message failed to send. Please try again.')
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  return (
    <div className="chat">
      {open && (
        <section id="chat-panel" className="chat-panel" aria-label="Shopping assistant">
          <header className="chat-header">
            <div className="chat-header-title">
              <span className="chat-avatar">
                <Bulldog size={30} />
              </span>
              <div>
                <h2>
                  <span className="sr-only">Handsome Dan. </span>Instant Message with {DAN_SN}
                </h2>
                <p>Handsome Dan · Campus Customs assistant · products, sizes &amp; stock</p>
              </div>
            </div>
            <button className="chat-close" aria-label="Close chat" onClick={() => setOpen(false)}>
              ✕
            </button>
          </header>

          {authLoading ? null : (
            <>
              {!user && (
                <p className="chat-guest-note">
                  Chatting as a guest.{' '}
                  <Link to="/login" onClick={() => setOpen(false)}>
                    Log in
                  </Link>{' '}
                  to save this conversation.
                </p>
              )}
              <div className="chat-messages" ref={listRef} aria-live="polite">
                {historyState === 'loading' && <p className="chat-status">Loading your conversation…</p>}
                {historyState === 'error' && (
                  <p className="chat-status">
                    Couldn't load earlier messages.{' '}
                    <button className="link-button" onClick={loadHistory}>
                      Retry
                    </button>
                  </p>
                )}
                <div className="chat-turn assistant">
                  <div className="chat-bubble assistant">
                    <span className="sn sn-dan">{DAN_SN}:</span>
                    <ReactMarkdown>{greeting.content}</ReactMarkdown>
                  </div>
                </div>
                {messages.map((m, i) => {
                  const pageResults = m.role === 'assistant' ? resultsFor(i, m) : null
                  const cards = (m.products?.length ? m.products : (m.pageResults?.products ?? [])).slice(
                    0,
                    MAX_CHAT_CARDS,
                  )
                  return (
                    <div key={i} className={`chat-turn ${m.role}`}>
                      <div className={`chat-bubble ${m.role}`}>
                        <span className={`sn ${m.role === 'assistant' ? 'sn-dan' : 'sn-me'}`}>
                          {m.role === 'assistant' ? DAN_SN : mySn}:
                        </span>
                        {m.role === 'assistant' ? <ReactMarkdown>{m.content}</ReactMarkdown> : ` ${m.content}`}
                      </div>
                      {m.role === 'assistant' && cards.length > 0 && (
                        <ul className="chat-products">
                          {cards.map((p) => (
                            <ChatProductCard key={p.product_id} product={p} />
                          ))}
                        </ul>
                      )}
                      {pageResults && (
                        <button type="button" className="chat-page-link" onClick={() => showOnPage(pageResults)}>
                          View all {pageResults.products.length} on the page →
                        </button>
                      )}
                    </div>
                  )
                })}
                {sending && <p className="chat-bubble assistant typing">{DAN_SN} is typing…</p>}
              </div>

              {error && (
                <p className="chat-error" role="alert">
                  {error}
                </p>
              )}

              {!sending && (messages.length === 0 || onProductPage) && (
                <div className="chat-starters" aria-label="Suggested questions">
                  {starters.map((q) => (
                    <button key={q} type="button" className="chat-starter" onClick={() => void send(q)}>
                      {q}
                    </button>
                  ))}
                </div>
              )}

              <form className="chat-form" onSubmit={handleSubmit}>
                <label htmlFor="chat-input" className="sr-only">
                  Message
                </label>
                <input
                  id="chat-input"
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about a hoodie, size, color…"
                  autoComplete="off"
                  maxLength={2000}
                />
                <button type="submit" className="btn btn-primary" disabled={!input.trim() || sending}>
                  Send ➤
                </button>
              </form>
            </>
          )}
        </section>
      )}

      <button
        className="chat-launcher"
        aria-expanded={open}
        aria-controls="chat-panel"
        aria-label={open ? 'Close chat' : 'Chat with Handsome Dan'}
        title={open ? 'Close chat' : 'Chat with Handsome Dan'}
        onClick={toggle}
      >
        {open ? <span className="chat-launcher-close">✕</span> : <Bulldog size={40} ink="#00356b" face="#ffffff" />}
      </button>
    </div>
  )
}

function ChatProductCard({ product }: { product: ProductCardData }) {
  const inStock = product.inventory.filter((s) => s.quantity > 0).map((s) => s.size)
  return (
    <li>
      <Link to={`/products/${product.product_id}`} className="chat-product">
        <img src={product.image_url} alt="" loading="lazy" />
        <div>
          <p className="chat-product-name">{product.name}</p>
          <p className="chat-product-meta">
            <span className="chat-product-price">{formatPrice(product.price)}</span>
            {' · '}
            {inStock.length ? inStock.join(' ') : 'Sold out'}
          </p>
        </div>
      </Link>
    </li>
  )
}
