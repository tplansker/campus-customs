import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, fetchProduct, formatPrice, NotFoundError, restockRequest, type ProductDetail as Detail } from '../api'
import { useAuth } from '../useAuth'
import { StarBurst } from '../components/Retro'
import { usePageResults } from '../usePageResults'

export default function ProductDetail() {
  const { productId = '' } = useParams()
  // Results are tagged with the id they belong to, so navigating to another
  // product shows the loading state until its own fetch finishes.
  const [result, setResult] = useState<{ id: string; product?: Detail; error?: string }>()

  useEffect(() => {
    fetchProduct(productId)
      .then((product) => setResult({ id: productId, product }))
      .catch((e) =>
        setResult({
          id: productId,
          error:
            e instanceof NotFoundError
              ? "We couldn't find that product."
              : "We couldn't load this product. Is the backend running?",
        }),
      )
  }, [productId])

  const current = result?.id === productId ? result : undefined
  const product = current?.product
  const error = current?.error

  // Chat results stay on the Products page, so "back" returns to them.
  const { results } = usePageResults()
  const back = (
    <Link to="/products" className="back-link">
      {results ? `← Back to “${results.heading}”` : '← All products'}
    </Link>
  )

  if (error) {
    return (
      <>
        {back}
        <section className="empty-state" role="alert">
          <p>{error}</p>
        </section>
      </>
    )
  }

  if (!product) {
    return (
      <>
        {back}
        <section className="empty-state" aria-live="polite">
          <p className="muted">Loading product…</p>
        </section>
      </>
    )
  }

  return (
    <>
      {back}
      <article className="product-detail">
        <div className="product-detail-image">
          <img src={product.image_url} alt={product.name} />
        </div>

        <div className="product-detail-info">
          <p className="eyebrow">{product.garment_type}</p>
          <h1>{product.name}</h1>
          <div className="detail-price-row">
            <StarBurst size="lg">{formatPrice(product.price).replace('.00', '')}</StarBurst>
            {product.total_stock > 0 && product.inventory.some((s) => s.quantity > 0 && s.quantity <= 5) && (
              <span className="blink-badge static">HURRY! SOME SIZES ALMOST GONE!</span>
            )}
          </div>
          <p className="product-detail-desc">{product.description}</p>

          <h2>Colors</h2>
          <ul className="chips">
            {product.colors.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>

          <h2>Sizes &amp; stock</h2>
          {product.inventory.length === 0 ? (
            <p className="muted">No size information yet.</p>
          ) : (
            <ul className="sizes">
              {product.inventory.map((s) => (
                <li key={s.size} className={s.quantity === 0 ? 'out' : undefined}>
                  <span className="size">{s.size}</span>
                  <span className="qty">
                    {s.quantity === 0 ? 'Sold out' : s.quantity <= 5 ? `Only ${s.quantity} left` : `${s.quantity} in stock`}
                  </span>
                  {s.quantity === 0 && <NotifyMe productId={product.product_id} size={s.size} />}
                </li>
              ))}
            </ul>
          )}
        </div>
      </article>
    </>
  )
}

// Restock waitlist button for one sold-out size (same backend as Handsome Dan's join_restock_waitlist).
function NotifyMe({ productId, size }: { productId: string; size: string }) {
  const { user } = useAuth()
  const [state, setState] = useState<'idle' | 'saving' | 'done' | 'error'>('idle')
  const [note, setNote] = useState('')

  if (!user) {
    return (
      <Link to="/login" className="notify-btn" title="Log in to get notified when this size is back">
        Log in to get notified
      </Link>
    )
  }
  if (state === 'done') {
    return (
      <span className="notify-done" role="status">
        <span className="pow">WOOF!</span>✓ {note}
      </span>
    )
  }

  async function join() {
    setState('saving')
    try {
      const r = await restockRequest(productId, size)
      setNote(r.status === 'already_on_list' ? 'Already on the list' : r.status === 'added' ? "You're on the list" : r.message)
      setState('done')
    } catch (err) {
      setNote(err instanceof ApiError ? err.message : 'Please try again.')
      setState('error')
    }
  }

  return (
    <>
      <button type="button" className="notify-btn" onClick={join} disabled={state === 'saving'}>
        {state === 'saving' ? 'Saving…' : 'Notify me'}
      </button>
      {state === 'error' && (
        <span className="notify-error" role="alert">
          {note}
        </span>
      )}
    </>
  )
}
