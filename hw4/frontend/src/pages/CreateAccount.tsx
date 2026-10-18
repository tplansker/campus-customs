import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { ApiError, type RegisterInput } from '../api'
import { useAuth } from '../useAuth'

const MIN_PASSWORD_LENGTH = 10 // matches backend/passwords.py

const EMPTY: RegisterInput = {
  first_name: '',
  last_name: '',
  email: '',
  password: '',
  confirm_password: '',
}

export default function CreateAccount() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (user && !submitting) return <Navigate to="/" replace />

  const update = (e: ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))

  const mismatch = form.confirm_password !== '' && form.password !== form.confirm_password

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    // Quick checks here for fast feedback; the backend enforces the same rules.
    if (form.password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`)
      return
    }
    if (form.password !== form.confirm_password) {
      setError("Passwords don't match.")
      return
    }
    setSubmitting(true)
    try {
      await register(form)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server. Please try again.')
      setSubmitting(false)
    }
  }

  return (
    <section className="auth-card">
      <h1>Create Account</h1>
      <form onSubmit={handleSubmit}>
        <div className="field-row">
          <div>
            <label htmlFor="ca-first">First name</label>
            <input
              id="ca-first"
              name="first_name"
              autoComplete="given-name"
              required
              value={form.first_name}
              onChange={update}
            />
          </div>
          <div>
            <label htmlFor="ca-last">Last name</label>
            <input
              id="ca-last"
              name="last_name"
              autoComplete="family-name"
              required
              value={form.last_name}
              onChange={update}
            />
          </div>
        </div>

        <label htmlFor="ca-email">Email</label>
        <input
          id="ca-email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={form.email}
          onChange={update}
        />

        <label htmlFor="ca-password">Password</label>
        <input
          id="ca-password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          required
          aria-describedby="ca-password-hint"
          value={form.password}
          onChange={update}
        />
        <p id="ca-password-hint" className="field-hint">
          At least {MIN_PASSWORD_LENGTH} characters. Avoid common passwords and don't use your name or email.
        </p>

        <label htmlFor="ca-confirm">Confirm password</label>
        <input
          id="ca-confirm"
          name="confirm_password"
          type="password"
          autoComplete="new-password"
          required
          aria-invalid={mismatch}
          aria-describedby={mismatch ? 'ca-confirm-hint' : undefined}
          value={form.confirm_password}
          onChange={update}
        />
        {mismatch && (
          <p id="ca-confirm-hint" className="field-hint field-hint-error">
            Passwords don't match.
          </p>
        )}

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Create Account'}
        </button>
      </form>
      <p className="muted">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </section>
  )
}
