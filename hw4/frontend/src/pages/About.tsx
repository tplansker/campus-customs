import { Link } from 'react-router-dom'
import Bulldog from '../components/Bulldog'

export default function About() {
  return (
    <>
      <section className="page-header">
        <p className="eyebrow">About Us</p>
        <h1>Meet Campus Customs!</h1>
        <p className="lead">
          We're a spirited little New Haven shop that thinks Yale pride should be easy to wear, and even easier to
          find.
        </p>
      </section>

      <section className="prose">
        <h2>Our story</h2>
        <p>
          Campus Customs started with a simple idea: every Bulldog deserves gear that feels like theirs. Whether you're
          repping your residential college, cheering on a team, or shopping for the proudest parent in the stands, you
          should be able to find it fast and love it for years.
        </p>
        <p>
          So we keep things simple: real photos, honest prices, and live stock for every size, so you never fall for a
          hoodie that's already gone.
        </p>

        <h2>What we make</h2>
        <p>
          More than 100 styles of hoodies, crewnecks, tees, quarter-zips, fleeces, and jackets, in sizes XS through
          XXL. There's gear for residential colleges, graduate and professional schools, varsity sports, and the whole
          Yale family. Yes, there's a Yale Grandpa crewneck.
        </p>

        <h2>Meet Handsome Dan</h2>
        <div className="about-dan">
          <Bulldog size={64} title="Handsome Dan" />
          <p>
            Our bulldog shopping assistant knows every size we have in stock. IM him from the button in the corner to
            find a gift, check your size, or compare prices. If your size is sold out, he'll put you on the restock
            list.
          </p>
        </div>

        <h2>Come visit us</h2>
        <p>
          We're open 24/7 right here on the World Wide Web. Start with <Link to="/products">the full shop</Link>, or
          just ask Handsome Dan. Boola Boola!
        </p>
      </section>
    </>
  )
}
