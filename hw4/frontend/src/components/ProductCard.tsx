import { Link } from 'react-router-dom'
import { formatPrice, type ProductCardData } from '../api'
import { StarBurst } from './Retro'

type CardProduct = Pick<ProductCardData, 'product_id' | 'name' | 'price' | 'description' | 'image_url' | 'total_stock'>

export default function ProductCard({ product }: { product: CardProduct }) {
  const soldOut = product.total_stock === 0

  return (
    <Link to={`/products/${product.product_id}`} className="product-card">
      <div className="product-card-image">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        {soldOut && <span className="badge stamp">Sold out</span>}
        {!soldOut && product.price < 40 && <span className="blink-badge">UNDER $40!</span>}
        <span className="card-price-burst">
          <StarBurst size="sm">{formatPrice(product.price).replace('.00', '')}</StarBurst>
        </span>
      </div>
      <div className="product-card-body">
        <h2>{product.name}</h2>
        <p className="product-card-price">{formatPrice(product.price)}</p>
        <p className="product-card-desc">{product.description}</p>
      </div>
    </Link>
  )
}
