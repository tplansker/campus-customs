import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchProducts, type Product } from '../api'
import ProductCard from '../components/ProductCard'
import { usePageResults } from '../usePageResults'

const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']

// Category buttons, matched against garment_type + name from the catalogue.
const CATEGORIES: { id: string; label: string; match: (text: string) => boolean }[] = [
  { id: 'all', label: 'All', match: () => true },
  { id: 'hoodies', label: 'Hoodies', match: (t) => t.includes('hood') },
  { id: 'crewnecks', label: 'Crewnecks', match: (t) => t.includes('crewneck') && !t.includes('t-shirt') },
  { id: 'tshirts', label: 'T-shirts', match: (t) => t.includes('t-shirt') || t.includes('t shirt') },
  { id: 'quarter-zips', label: 'Quarter-zips', match: (t) => t.includes('quarter-zip') || t.includes('1 4 zip') },
  { id: 'outerwear', label: 'Fleece & jackets', match: (t) => t.includes('fleece') || t.includes('jacket') },
]

// Collections from the home page cards, matched on product names.
const COLLECTIONS: Record<string, { label: string; words: string[] }> = {
  colleges: {
    label: 'Residential Colleges',
    words: ['benjamin franklin', 'berkeley', 'branford', 'davenport', 'ezra stiles', 'grace hopper', 'jonathan edwards',
      'morse', 'pauli murray', 'pierson', 'saybrook', 'silliman', 'timothy dwight', 'trumbull'],
  },
  sports: {
    label: 'Sports & Teams',
    words: ['baseball', 'basketball', 'football', 'hockey', 'soccer', 'tennis', 'golf', 'swimming', 'diving',
      'volleyball', 'lacrosse', 'fencing', 'sailing', 'squash', 'crew left chest', 'track'],
  },
  family: {
    label: 'Yale Family',
    words: ['mom', 'dad', 'grandma', 'grandpa', 'aunt', 'uncle', 'brother', 'sister', 'cousin'],
  },
}

const inCollection = (name: string, words: string[]) =>
  words.some((w) => new RegExp(`\\b${w}\\b`).test(name.toLowerCase()))

const SORTS = [
  { id: 'featured', label: 'Name (A–Z)' },
  { id: 'price-asc', label: 'Price: low to high' },
  { id: 'price-desc', label: 'Price: high to low' },
]

const searchable = (p: Product) =>
  [p.name, p.garment_type, p.description, ...p.colors, ...p.search_tags].join(' ').toLowerCase()

export default function Products() {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [error, setError] = useState('')
  const { results, version, clear } = usePageResults()
  const resultsRef = useRef<HTMLElement>(null)

  // Filters live in the URL (?q=&cat=&size=&sort=) so a filtered view can be shared or bookmarked.
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const cat = params.get('cat') ?? 'all'
  const size = params.get('size') ?? ''
  const sort = params.get('sort') ?? 'featured'
  const collectionId = params.get('collection') ?? ''
  const collection = COLLECTIONS[collectionId]

  function setParam(key: string, value: string, fallback = '') {
    // Build on the address bar itself (updated immediately), not the last render's params,
    // so quick successive changes (category, then size, then sort) don't drop each other.
    const next = new URLSearchParams(window.location.search)
    if (!value || value === fallback) next.delete(key)
    else next.set(key, value)
    setParams(next, { replace: true })
  }

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch(() => setError("We couldn't load the catalogue. Is the backend running?"))
  }, [])

  // New results from the chat: bring them into view.
  useEffect(() => {
    if (results) {
      window.scrollTo({ top: 0, behavior: 'smooth' })
      resultsRef.current?.focus({ preventScroll: true })
    }
  }, [results, version])

  const category = CATEGORIES.find((c) => c.id === cat) ?? CATEGORIES[0]
  const query = q.trim().toLowerCase()

  const filtered = useMemo(() => {
    if (!products) return []
    const list = products.filter((p) => {
      const typeText = `${p.garment_type} ${p.name}`.toLowerCase()
      if (!category.match(typeText)) return false
      if (collection && !inCollection(p.name, collection.words)) return false
      if (size && !(p.sizes_in_stock ?? []).includes(size)) return false
      const words = query.split(/\s+/).filter(Boolean)
      if (words.length) {
        const text = searchable(p)
        if (!words.every((w) => text.includes(w))) return false
      }
      return true
    })
    if (sort === 'price-asc') list.sort((a, b) => a.price - b.price || a.name.localeCompare(b.name))
    else if (sort === 'price-desc') list.sort((a, b) => b.price - a.price || a.name.localeCompare(b.name))
    return list
  }, [products, category, size, sort, query, collection])

  const counts = useMemo(
    () =>
      Object.fromEntries(
        CATEGORIES.map((c) => [c.id, (products ?? []).filter((p) => c.match(`${p.garment_type} ${p.name}`.toLowerCase())).length]),
      ),
    [products],
  )

  const filtersActive = q || cat !== 'all' || size || sort !== 'featured' || collection

  return (
    <>
      <section className="page-header">
        <p className="eyebrow">Shop</p>
        <h1>Products</h1>
        <p className="lead">Hoodies, crewnecks, tees, and quarter-zips for every college, school, and team.</p>
      </section>

      {results ? (
        // Cards the chat agent found: same ProductCard (and same link to the detail page) as the full grid.
        <section
          key={version}
          ref={resultsRef}
          tabIndex={-1}
          className="chat-results"
          aria-label={`Assistant results: ${results.heading}`}
          aria-live="polite"
        >
          <div className="chat-results-header">
            <div>
              <p className="eyebrow">From Handsome Dan</p>
              <h2>{results.heading}</h2>
              <p className="muted">
                {results.products.length} {results.products.length === 1 ? 'match' : 'matches'} for “{results.query}”
              </p>
            </div>
            <button type="button" className="btn btn-ghost" onClick={clear}>
              Show all products
            </button>
          </div>
          {results.products.length === 0 ? (
            <p className="muted">No matching products.</p>
          ) : (
            <div className="product-grid">
              {results.products.map((p) => (
                <ProductCard key={p.product_id} product={p} />
              ))}
            </div>
          )}
        </section>
      ) : error ? (
        <section className="empty-state" role="alert">
          <p>{error}</p>
        </section>
      ) : !products ? (
        <section className="empty-state" aria-live="polite">
          <p className="muted">Loading products…</p>
        </section>
      ) : (
        <section aria-label="Product list">
          <div className="shop-filters" role="search">
            <div className="shop-filters-row">
              <label className="filter-search">
                <span className="sr-only">Search products</span>
                <input
                  type="search"
                  placeholder="Search: bulldog, Saybrook, navy, hockey…"
                  value={q}
                  onChange={(e) => setParam('q', e.target.value)}
                />
              </label>
              <label className="filter-select">
                <span>In stock in</span>
                <select value={size} onChange={(e) => setParam('size', e.target.value)}>
                  <option value="">Any size</option>
                  {SIZES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label className="filter-select">
                <span>Sort</span>
                <select value={sort} onChange={(e) => setParam('sort', e.target.value, 'featured')}>
                  {SORTS.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="category-chips" role="group" aria-label="Category">
              {CATEGORIES.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className={`category-chip${c.id === category.id ? ' active' : ''}`}
                  aria-pressed={c.id === category.id}
                  onClick={() => setParam('cat', c.id, 'all')}
                >
                  {c.label} <span className="chip-count">{counts[c.id]}</span>
                </button>
              ))}
            </div>
          </div>

          {collection && (
            <div className="collection-banner">
              <span>
                Collection: <strong>{collection.label}</strong>
              </span>
              <button type="button" className="link-button" onClick={() => setParam('collection', '')}>
                ✕ Show everything
              </button>
            </div>
          )}

          <div className="result-bar">
            <p className="muted result-count" aria-live="polite">
              {filtered.length} of {products.length} products
              {size && ` in stock in ${size}`}
            </p>
            {filtersActive && (
              <button type="button" className="link-button" onClick={() => setParams({}, { replace: true })}>
                Clear filters
              </button>
            )}
          </div>

          {filtered.length === 0 ? (
            <div className="empty-state">
              <p>No products match those filters.</p>
              <p className="muted">Try another size or category, or ask Handsome Dan in the chat.</p>
            </div>
          ) : (
            <div className="product-grid">
              {filtered.map((p) => (
                <ProductCard key={p.product_id} product={p} />
              ))}
            </div>
          )}
        </section>
      )}
    </>
  )
}
