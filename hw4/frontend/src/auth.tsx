import { useEffect, useState, type ReactNode } from 'react'
import { fetchCurrentUser, loginRequest, logoutRequest, registerRequest, type User } from './api'
import { AuthContext, type AuthState } from './useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // Restore the session from the cookie on page load.
  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const value: AuthState = {
    user,
    loading,
    login: async (email, password) => setUser(await loginRequest(email, password)),
    register: async (input) => setUser(await registerRequest(input)),
    logout: async () => {
      await logoutRequest()
      setUser(null)
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

