import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../useAuth'
import Bulldog from './Bulldog'

const links = [
  { to: '/', label: 'Home' },
  { to: '/products', label: 'Products' },
  { to: '/about', label: 'About Us' },
]

export default function NavBar() {
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    close()
    try {
      await logout()
    } finally {
      navigate('/')
    }
  }

  return (
    <header className="nav">
      <div className="nav-inner">
        <Link to="/" className="brand" onClick={close} aria-label="Campus Customs home">
          <Bulldog size={34} />
          <span className="brand-text">
            <span className="brand-name">
              Campus <span>Customs</span>
            </span>
            <small>Boola Boola!</small>
          </span>
        </Link>

        <button
          className="nav-toggle"
          aria-expanded={open}
          aria-controls="nav-menu"
          aria-label={open ? 'Close menu' : 'Open menu'}
          onClick={() => setOpen((o) => !o)}
        >
          <span aria-hidden="true">{open ? '✕' : '☰'}</span>
        </button>

        <nav id="nav-menu" className={`nav-menu${open ? ' open' : ''}`} aria-label="Main">
          <ul className="nav-links">
            {links.map((l) => (
              <li key={l.to}>
                <NavLink to={l.to} end={l.to === '/'} onClick={close}>
                  {l.label}
                </NavLink>
              </li>
            ))}
          </ul>
          <div className="nav-auth">
            {loading ? null : user ? (
              <>
                <span className="nav-greeting">Hi, {user.first_name}</span>
                <button type="button" className="btn btn-ghost" onClick={handleLogout}>
                  Log Out
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login" onClick={close}>
                  Log In
                </NavLink>
                <NavLink to="/create-account" className="btn btn-primary" onClick={close}>
                  Create Account
                </NavLink>
              </>
            )}
          </div>
        </nav>
      </div>
    </header>
  )
}
