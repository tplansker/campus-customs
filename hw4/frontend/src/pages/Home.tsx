import { Link } from 'react-router-dom'

// Each card opens the Products page filtered to that collection (see COLLECTIONS in Products.tsx).
const COLLECTION_CARDS = [
  {
    id: 'colleges',
    title: 'Residential Colleges',
    tagline: 'Rep your college in style: crewnecks, tees, quarter-zips, and fleeces for Saybrook, Pierson, Morse, and more.',
  },
  {
    id: 'sports',
    title: 'Sports & Teams',
    tagline: 'From hockey to sailing to squash, cheer on the Bulldogs in team hoodies, crewnecks, and tees.',
  },
  {
    id: 'family',
    title: 'Yale Family',
    tagline: "Yale Mom, Yale Dad, Yale Grandpa, and the whole gang: gear for everyone who's proud of their Bulldog.",
  },
]

export default function Home() {
  return (
    <>
      <section className="hero">
        <p className="eyebrow">Boola Boola! · Campus Customs · New Haven</p>
        <h1>Yale Gear for Every Bulldog!</h1>
        <p className="lead">
          Hoodies, crewnecks, tees, and quarter-zips for every residential college, every team, and every proud Yale
          mom, dad, and grandpa. Not sure what's in your size? IM Handsome Dan and he'll sniff it out. Proudly 100%
          Harvard-free!
        </p>
        <div className="hero-actions">
          <Link to="/products" className="btn btn-primary">
            Shop All
          </Link>
          <Link to="/about" className="btn btn-ghost">
            Our Story
          </Link>
        </div>
      </section>

      <section className="grid-3" aria-label="Featured collections">
        {COLLECTION_CARDS.map((c) => (
          <article key={c.id} className="card">
            <h2>{c.title}</h2>
            <p>{c.tagline}</p>
            <Link to={`/products?collection=${c.id}`} className="card-link">
              Shop {c.title} →
            </Link>
          </article>
        ))}
      </section>

    </>
  )
}
