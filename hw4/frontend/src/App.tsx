import { Route, Routes, useLocation } from 'react-router-dom'
import NavBar from './components/NavBar'
import ChatWidget from './components/ChatWidget'
import { Marquee, RetroFooter, Sparkles } from './components/Retro'
import Home from './pages/Home'
import Products from './pages/Products'
import ProductDetail from './pages/ProductDetail'
import About from './pages/About'
import Login from './pages/Login'
import CreateAccount from './pages/CreateAccount'
import NotFound from './pages/NotFound'
import { useAuth } from './useAuth'
import { PageResultsProvider } from './pageResults'

export default function App() {
  const { user } = useAuth()
  const location = useLocation()

  // Keyed by user so chat results never carry over to the next person who logs in.
  return (
    <PageResultsProvider key={user?.id ?? 'guest'}>
      <Sparkles />
      <Marquee />
      <NavBar />
      {/* Every page sits in a 1996 browser window, complete with a (decorative) location bar. */}
      <div className="browser-window">
        <div className="window-titlebar" aria-hidden="true">
          <span>🌐 Campus Customs Online - Netscape Navigator</span>
          <span className="window-buttons">
            <span>_</span>
            <span>□</span>
            <span>×</span>
          </span>
        </div>
        <div className="window-address" aria-hidden="true">
          <span className="address-label">Location:</span>
          <span className="address-field">http://www.campuscustoms.edu/~handsomedan{location.pathname}</span>
          <span className="netscape-n">N</span>
        </div>
      <main className="page">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:productId" element={<ProductDetail />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<Login />} />
          <Route path="/create-account" element={<CreateAccount />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      </div>
      <RetroFooter />
      <ChatWidget key={user?.id ?? 'guest'} />
    </PageResultsProvider>
  )
}
