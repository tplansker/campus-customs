import { Link } from 'react-router-dom'
import Bulldog from '../components/Bulldog'

export default function NotFound() {
  return (
    <section className="empty-state">
      <Bulldog size={72} title="Handsome Dan" />
      <h1>Ruff! Page not found</h1>
      <p className="muted">Handsome Dan sniffed everywhere but couldn't find this page.</p>
      <p>
        <Link to="/">Back to home</Link>
      </p>
    </section>
  )
}
