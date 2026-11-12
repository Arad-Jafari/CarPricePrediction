import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, lazy, Suspense, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { Link, Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, CarFront, Check, ChevronDown,
  CircleHelp, Eye, EyeOff, Gauge, History, LayoutDashboard, LogOut, Menu, MessageCircle,

  Pencil, Plus, Search, ShieldCheck, Sparkles, Trash2, X
} from 'lucide-react'
import { api, clearAccessToken, setAccessToken } from './services/api'
import { createPredictionSchema } from './services/featureValidation'
import type { CarInput, Feature, Prediction, User } from './types'

const PredictionHistoryChart = lazy(() => import('./components/PredictionHistoryChart'))
const PRICE_REFERENCE_MAE_TOMAN = 116_716_294

type AuthContextValue = {
  user: User | null
  ready: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  setUser: (user: User | null) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('Authentication context is missing')
  return value
}

function App() {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let active = true
    api<User>('/auth/me')
      .then((profile) => { if (active) setUser(profile) })
      .catch(() => { if (active) { clearAccessToken(); setUser(null) } })
      .finally(() => { if (active) setReady(true) })
    return () => { active = false }
  }, [])

  const authValue = useMemo<AuthContextValue>(() => ({
    user,
    ready,
    setUser,
    async signIn(email, password) {
      const result = await api<{ access_token: string; user: User }>('/auth/login', {
        method: 'POST', body: JSON.stringify({ email, password }), retryAuth: false
      })
      queryClient.clear()
      setAccessToken(result.access_token)
      setUser(result.user)
    },
    async signOut() {
      try { await api('/auth/logout', { method: 'POST' }) }
      finally { clearAccessToken(); queryClient.clear(); setUser(null) }
    }
  }), [user, ready, queryClient])

  return (
    <AuthContext.Provider value={authValue}>
      <Routes>
        <Route path="/" element={<HomeRoute />} />
        <Route path="/login" element={<AuthPage mode="login" />} />
        <Route path="/register" element={<AuthPage mode="register" />} />
        <Route path="/model" element={<PublicModelPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/predict" element={<PredictionPage />} />
            <Route path="/predictions/history" element={<HistoryPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:conversationId" element={<ChatPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthContext.Provider>
  )
}

function HomeRoute() {
  const { user, ready } = useAuth()
  return ready && user ? <Navigate to="/dashboard" replace /> : <LandingPage />
}

function ProtectedRoute() {
  const { user, ready } = useAuth()
  if (!ready) return <FullScreenLoading />
  return user ? <Outlet /> : <Navigate to="/login" replace />
}

function AppShell() {
  const { user, signOut } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const navigate = useNavigate()
  const sidebarRef = useRef<HTMLElement>(null)
  const mobileToggleRef = useRef<HTMLButtonElement>(null)
  const links = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/predict', label: 'New prediction', icon: Plus },
    { to: '/predictions/history', label: 'Prediction history', icon: History },
    { to: '/compare', label: 'Compare', icon: Activity },
    { to: '/chat', label: 'Valuation chat', icon: MessageCircle },
  ]

  async function logout() {
    await signOut()
    navigate('/login')
  }

  useEffect(() => {
    if (!mobileOpen) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setMobileOpen(false)
        mobileToggleRef.current?.focus()
        return
      }
      if (event.key !== 'Tab') return

      const focusable = sidebarRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not(:disabled)'
      )
      if (!focusable?.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    sidebarRef.current?.querySelector<HTMLElement>('a[href], button:not(:disabled)')?.focus()
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [mobileOpen])

  function closeMobileSidebar(restoreFocus = false) {
    setMobileOpen(false)
    if (restoreFocus) mobileToggleRef.current?.focus()
  }

  return (
    <div className={`workspace${sidebarCollapsed ? ' workspace-sidebar-collapsed' : ''}`}>
      {mobileOpen && <button type="button" className="mobile-backdrop" aria-label="Close navigation backdrop" onClick={() => closeMobileSidebar(true)} />}
      <aside ref={sidebarRef} id="primary-sidebar" className={`sidebar${sidebarCollapsed ? ' sidebar-collapsed' : ''}${mobileOpen ? ' sidebar-open' : ''}`} aria-label="Primary navigation">
        <Link to="/dashboard" className="brand-lockup" aria-label="206 / estimate home" title="206 / estimate" onClick={() => closeMobileSidebar()}>
          <span className="brand-mark"><CarFront size={21} strokeWidth={2.2} /></span>
          <span><strong>206 / estimate</strong><small>Vehicle intelligence</small></span>
        </Link>
        <div className="sidebar-caption">Workspace</div>
        <nav className="side-nav" aria-label="Main navigation">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} aria-label={to === '/chat' ? `${label}, coming soon` : label} title={to === '/chat' ? `${label}, coming soon` : label} onClick={() => closeMobileSidebar()} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              <Icon size={18} /><span>{label}</span>{to === '/predict' && <span className="nav-shortcut">+</span>}{to === '/chat' && <span className="nav-status">Soon</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-caption lower-caption">Insights</div>
        <NavLink to="/model" aria-label="How it works" title="How it works" onClick={() => closeMobileSidebar()} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <CircleHelp size={18} /><span>How it works</span>
        </NavLink>
        <div className="sidebar-spacer" />
        <div className="sidebar-note">
          <span className="note-icon"><ShieldCheck size={17} /></span>
          <div><strong>Private by design</strong><p>Your predictions stay in your account.</p></div>
        </div>
        <div className="sidebar-user">
          <span className="avatar">{initials(user?.full_name)}</span>
          <span className="sidebar-user-name"><strong>{user?.full_name}</strong><small>{user?.email}</small></span>
          <button className="icon-button" aria-label="Log out" title="Log out" onClick={() => void logout()}><LogOut size={17} /></button>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <button
            type="button"
            className="sidebar-toggle icon-button"
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!sidebarCollapsed}
            aria-controls="primary-sidebar"
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
          ><Menu size={20} /></button>
          <button
            ref={mobileToggleRef}
            type="button"
            className="mobile-menu icon-button"
            aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'}
            aria-expanded={mobileOpen}
            aria-controls="primary-sidebar"
            onClick={() => setMobileOpen((open) => !open)}
          >{mobileOpen ? <X size={20} /> : <Menu size={20} />}</button>
          <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{pageTitle()}</strong></div>
          <div className="topbar-right">
            <span className="model-badge" aria-label="Peugeot 206 model active"><span /> <span className="model-badge-full">Peugeot 206 · model active</span><span className="model-badge-short">206 · active</span></span>
            <NavLink to="/profile" className="topbar-avatar" aria-label="Profile">{initials(user?.full_name)}</NavLink>
          </div>
        </header>
        <div className="page-content"><Outlet /></div>
      </main>
    </div>
  )
}

function LandingPage() {
  const { user } = useAuth()
  const predictionPath = user ? '/predict' : '/register'
  return (
    <main className="landing">
      <nav className="landing-nav">
        <Link to="/" className="brand-lockup"><span className="brand-mark"><CarFront size={21} /></span><span><strong>206 / estimate</strong><small>Vehicle intelligence</small></span></Link>
        <div className="landing-nav-actions">{user ? <><Link className="text-link" to="/dashboard">Dashboard</Link><Link className="button button-dark button-small" to={predictionPath}>New estimate <ArrowRight size={15} /></Link></> : <><Link className="text-link" to="/login">Sign in</Link><Link className="button button-dark button-small" to="/register">Create account <ArrowRight size={15} /></Link></>}</div>
      </nav>
      <section className="hero-section">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-dot" /> A focused estimate for one iconic car</div>
          <h1>A clearer view of your <em>206's value.</em></h1>
          <p>Get a data-driven price estimate based on the Peugeot 206 listings represented in our training data. No guesswork disguised as certainty—just a useful starting point.</p>
          <div className="hero-actions"><Link to={predictionPath} className="button button-dark">Start a prediction <ArrowRight size={17} /></Link><Link to="/model" className="button button-outline">See how it works</Link></div>
          <div className="hero-trust"><span><ShieldCheck size={16} /> Personal prediction history</span><span><Activity size={16} /> Real trained model</span></div>
        </div>
        <div className="hero-visual">
          <div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" />
          <div className="hero-car-card">
            <div className="car-card-top"><span className="live-tag"><i /> MODEL SCOPE</span><span className="car-card-year">206</span></div>
            <div className="landing-car-mark" role="img" aria-label="Peugeot 206 estimate coverage graphic"><span>206</span><small>PEUGEOT</small></div>
            <div className="car-card-footer"><div><span className="micro-label">VEHICLE COVERAGE</span><strong>Peugeot 206 only</strong></div><div><span className="micro-label">ESTIMATION BASIS</span><strong>764 cleaned listings</strong></div><span className="circle-arrow"><ArrowUpRight size={19} /></span></div>
          </div>
          <div className="floating-stat"><span className="stat-icon"><Gauge size={17} /></span><div><strong>6 input signals</strong><small>Matched to training data</small></div><Check size={16} className="stat-check" /></div>
          <div className="floating-stamp"><Sparkles size={14} /> ESTIMATE, NOT GUARANTEE</div>
        </div>
      </section>
      <section className="landing-strip"><div><span className="strip-number">01</span><strong>Enter the car details</strong><span>Only fields the model was trained on.</span></div><div><span className="strip-number">02</span><strong>Get an instant estimate</strong><span>Generated by the saved regression model.</span></div><div><span className="strip-number">03</span><strong>Keep your work private</strong><span>Your history belongs to your account.</span></div></section>
      <footer className="landing-footer"><span>206 / estimate</span><span>Independent machine-learning estimate · Currency denomination not specified in source data</span><Link to="/model">Model details <ArrowRight size={14} /></Link></footer>
    </main>
  )
}

function PublicModelPage() {
  const { user } = useAuth()
  return <main className="public-model-page"><nav className="landing-nav"><Link to="/" className="brand-lockup"><span className="brand-mark"><CarFront size={21} /></span><span><strong>206 / estimate</strong><small>Vehicle intelligence</small></span></Link><div className="landing-nav-actions">{user ? <><Link className="text-link" to="/dashboard">Dashboard</Link><Link className="button button-dark button-small" to="/predict">New estimate <ArrowRight size={14} /></Link></> : <><Link className="text-link" to="/login">Sign in</Link><Link className="button button-dark button-small" to="/register">Create account <ArrowRight size={14} /></Link></>}</div></nav><ModelPage /><footer className="public-model-footer"><Link to="/">← Back to overview</Link><span>Currency denomination not specified in source data.</span></footer></main>
}

function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState('')
  const [notice] = useState((location.state as { registered?: boolean } | null)?.registered ? 'Account created. Sign in with your new credentials.' : '')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const register = mode === 'register'
  const formSchema = register
    ? z.object({
        full_name: z.string().trim().min(2, 'Enter your full name.').max(120),
        email: z.email('Enter a valid email address.'),
        password: z.string().min(12, 'Use at least 12 characters.').max(256),
        password_confirmation: z.string().min(12, 'Confirm the 12-character password.').max(256)
      }).refine((value) => value.password === value.password_confirmation, {
        path: ['password_confirmation'], message: 'Passwords do not match.'
      })
    : z.object({ email: z.email('Enter a valid email address.'), password: z.string().min(1, 'Enter your password.') })
  const { register: field, handleSubmit, formState: { errors, isSubmitting } } = useForm<Record<string, string>>()

  async function submit(values: Record<string, string>) {
    setError('')
    const parsed = formSchema.safeParse(values)
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? 'Check your details.')
      return
    }
    try {
      if (register) {
        await api<User>('/auth/register', { method: 'POST', body: JSON.stringify(parsed.data), retryAuth: false })
        // Registration does not implicitly establish a session.
        navigate('/login', { state: { registered: true } })
      } else {
        await signIn(parsed.data.email, parsed.data.password)
        navigate('/dashboard')
      }
    } catch (reason) { setError(errorMessage(reason)) }
  }

  return (
    <main className="auth-page">
      <div className="auth-brand"><Link to="/" className="brand-lockup"><span className="brand-mark"><CarFront size={21} /></span><span><strong>206 / estimate</strong><small>Vehicle intelligence</small></span></Link><Link to="/" className="back-home">Back to home <ArrowRight size={14} /></Link></div>
      <div className="auth-layout">
        <div className="auth-panel">
          <div className="eyebrow"><span className="eyebrow-dot" /> YOUR PERSONAL WORKSPACE</div>
          <h1>{register ? 'Start with the details.' : 'Welcome back.'}</h1>
          <p className="auth-intro">{register ? 'Create an account to save and revisit your Peugeot 206 estimates.' : 'Sign in to pick up where you left off.'}</p>
          {error && <div className="form-alert" role="alert">{error}</div>}
          {notice && <div className="form-success" role="status">{notice}</div>}
          <form onSubmit={handleSubmit(submit)} className="form-stack">
            {register && <label className="field-label">Full name<input {...field('full_name')} placeholder="Your name" autoComplete="name" /><FieldError message={errors.full_name?.message} /></label>}
            <label className="field-label">Email address<input {...field('email')} type="email" placeholder="you@example.com" autoComplete="email" /><FieldError message={errors.email?.message} /></label>
            <label className="field-label field-with-action">
              <span>Password</span>
              <div className="password-input-wrap">
                <input {...field('password')} type={showPassword ? 'text' : 'password'} placeholder={register ? 'At least 12 characters' : 'Your password'} autoComplete={register ? 'new-password' : 'current-password'} />
                <button type="button" className="password-toggle" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword((current) => !current)}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button>
              </div>
              <FieldError message={errors.password?.message} />
            </label>
            {register && <label className="field-label field-with-action">
              <span>Confirm password</span>
              <div className="password-input-wrap">
                <input {...field('password_confirmation')} type={showConfirmPassword ? 'text' : 'password'} placeholder="Repeat password" autoComplete="new-password" />
                <button type="button" className="password-toggle" aria-label={showConfirmPassword ? 'Hide password' : 'Show password'} onClick={() => setShowConfirmPassword((current) => !current)}>{showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button>
              </div>
              <FieldError message={errors.password_confirmation?.message} />
            </label>}
            <button className="button button-dark button-wide" disabled={isSubmitting}>{isSubmitting ? <Spinner /> : register ? 'Create account' : 'Sign in'} {!isSubmitting && <ArrowRight size={16} />}</button>
          </form>
          <p className="auth-switch">{register ? 'Already have an account?' : 'New to 206 / estimate?'} <Link to={register ? '/login' : '/register'}>{register ? 'Sign in' : 'Create an account'}</Link></p>
          <div className="auth-assurance"><ShieldCheck size={16} /><span>Private estimates, protected account, no shared history.</span></div>
        </div>
        <div className="auth-aside"><div className="auth-aside-mark" aria-hidden="true">206</div><div className="aside-topline"><span>PEUGEOT 206</span><span>MODEL SCOPE / 01</span></div><div className="aside-copy"><span className="micro-label">A focused tool for a familiar car</span><h2>Six real inputs.<br /><em>One grounded estimate.</em></h2><p>The model uses the car details found in its training data. It won't claim more certainty—or broader coverage—than it has.</p></div><div className="aside-bottom"><div><span>39</span><small>transformed signals</small></div><div><span>764</span><small>cleaned listings</small></div><div><span>LR</span><small>linear regression</small></div></div></div>
      </div>
      <div className="auth-footnote">Source price denomination is not stated by the training data.</div>
    </main>
  )
}

function DashboardPage() {
  const { user } = useAuth()
  const predictionsQuery = useQuery({ queryKey: ['predictions', 1], queryFn: () => api<PageResult<Prediction>>('/predictions?page=1&page_size=8') })
  const predictions = predictionsQuery.data?.items ?? []
  const latest = predictions[0]
  const chartData = [...predictions].reverse().map((entry) => ({
    date: new Date(entry.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    price: entry.predicted_price
  }))

  return (
    <div className="page-stack">
      <section className="welcome-row">
        <div><div className="eyebrow"><span className="eyebrow-dot" /> Peugeot 206 workspace</div><h1>Good to see you, {user?.full_name.split(' ')[0]}.</h1><p>Your saved estimates and vehicle insights, all in one place.</p></div>
        <Link to="/predict" className="button button-dark"><Plus size={17} /> New prediction</Link>
      </section>
      {predictionsQuery.isError && <ErrorBanner message="Some dashboard data could not be loaded. Please refresh to try again." />}
      <section className="dashboard-estimate panel" aria-labelledby="dashboard-estimate-title">
        <div className="dashboard-estimate-content">
          <div className="dashboard-estimate-heading"><h2 id="dashboard-estimate-title">Latest estimate</h2>{latest && <span className="estimate-date">{formatDate(latest.created_at)}</span>}</div>
          {predictionsQuery.isLoading ? <Skeleton className="dashboard-estimate-skeleton" /> : latest ? <><PriceReference price={latest.predicted_price} variant="dashboard" /><p className="dashboard-estimate-unit">{latest.prediction_unit || 'Source price units; currency denomination unknown.'}</p><Link to="/predict" className="quiet-link">Create another estimate <ArrowRight size={14} /></Link></> : <div className="dashboard-estimate-empty"><p>Your first Peugeot 206 estimate will appear here.</p><Link to="/predict" className="button button-dark"><Plus size={16} /> Get an estimate</Link></div>}
        </div>
      </section>
      <section className="stat-grid">
        <StatCard label="Predictions saved" value={predictionsQuery.isLoading ? '—' : predictionsQuery.data?.total ?? predictions.length} hint="In your account" icon={<Activity size={18} />} />
        <StatCard label="AI chat" value={<span className="stat-coming-soon">Coming soon</span>} hint="Not available yet" icon={<MessageCircle size={18} />} />
        <div className="stat-card model-stat"><div className="stat-top"><span className="stat-label">Active model</span><span className="online-mark"><i /> Ready</span></div><strong>Peugeot 206</strong><span className="stat-hint">Linear Regression · {latest?.model_version ?? 'trained model'}</span></div>
      </section>
      <section className="dashboard-grid">
        <div className="panel chart-panel">
          <div className="panel-heading"><h2>Prediction history</h2><Link to="/predictions/history" className="quiet-link">View all <ArrowRight size={14} /></Link></div>
          {predictionsQuery.isLoading ? <Skeleton className="chart-skeleton" /> : chartData.length > 1 ? <><div className="chart-caption"><span className="chart-key" /> Model estimates in source price units</div><Suspense fallback={<Skeleton className="chart-skeleton" />}><PredictionHistoryChart data={chartData} /></Suspense><p className="chart-disclaimer">Your past model outputs—not historical market prices.</p></> : <EmptyState icon={<Activity size={20} />} title="Your timeline starts here" text="Create a prediction to see your personal estimate history." action={<Link className="button button-outline button-small" to="/predict">Make a prediction <ArrowRight size={14} /></Link>} />}
        </div>
        <div className="panel recent-panel"><div className="panel-heading"><h2>Recent estimates</h2><Link to="/predictions/history" className="icon-link" aria-label="View history"><ArrowUpRight size={17} /></Link></div>
          {predictionsQuery.isLoading ? <Skeleton className="rows-skeleton" /> : predictions.length ? <div className="recent-list">{predictions.slice(0, 4).map((item) => <Link to={`/predictions/history?id=${item.id}`} key={item.id} className="recent-item"><span className="recent-car"><CarFront size={17} /></span><span className="recent-item-copy"><strong>Peugeot 206 · {item.input_data.trim}</strong><small>{formatDate(item.created_at)}</small></span><span className="recent-price">{formatNumber(item.predicted_price)}<small>source units</small></span></Link>)}</div> : <EmptyState icon={<CarFront size={19} />} title="No estimates yet" text="Add a car's supported details to get started." action={<Link className="quiet-link" to="/predict">Create prediction <ArrowRight size={14} /></Link>} />}
          <Link to="/predict" className="add-prediction-row"><span><Plus size={16} /> Start a new estimate</span><ArrowRight size={15} /></Link>
        </div>
      </section>
      <section className="dashboard-bottom">
        <div className="panel conversations-panel coming-soon-panel"><div className="panel-heading"><span className="availability-badge">Coming soon</span><h2>AI conversations</h2></div>
          <p>Conversation tools are not available yet. This section will be ready when AI chat is fully developed.</p>
        </div>
        <div className="scope-card"><span className="scope-icon"><ShieldCheck size={19} /></span><span className="micro-label">A NOTE ON SCOPE</span><h3>One car, six inputs.</h3><p>This model was trained on Peugeot 206 listings. Predictions are estimates and should not be treated as appraisals.</p><Link to="/model">Explore model details <ArrowRight size={14} /></Link></div>
      </section>
    </div>
  )
}

function PredictionPage() {
  const queryClient = useQueryClient()
  const location = useLocation()
  const initialValues = (location.state as { input?: Record<string, unknown> } | null)?.input
  const [result, setResult] = useState<Prediction | null>(null)
  const featureQuery = useQuery({ queryKey: ['model-features'], queryFn: () => api<FeatureResponse>('/model/features') })
  const mutation = useMutation({
    mutationFn: (input: CarInput) => api<Prediction>('/predictions', { method: 'POST', body: JSON.stringify(input) }),
    onSuccess: (prediction) => {
      setResult(prediction)
      queryClient.invalidateQueries({ queryKey: ['predictions'] })
    }
  })
  const features = getFeatures(featureQuery.data)

  return (
    <div className="page-stack">
      <PageIntro eyebrow="PREDICTION STUDIO" title="Describe your 206." text="Enter the same details used by the trained model. Fields and choices come from the verified training contract." />
      {featureQuery.isLoading && <Skeleton className="form-skeleton" />}
      {featureQuery.isError && <ErrorBanner message="Could not load the verified model input fields." />}
      {features.length > 0 && <div className="prediction-layout">
        <div className="panel prediction-form-panel">
          <div className="form-panel-title"><span className="form-panel-icon"><CarFront size={19} /></span><div><strong>Vehicle details</strong><small>Peugeot 206 · all fields required</small></div></div>
          <DynamicPredictionForm features={features} onSubmit={(values) => { setResult(null); mutation.mutate(values) }} isLoading={mutation.isPending} initialValues={initialValues} />
          {mutation.isError && <ErrorBanner message={errorMessage(mutation.error)} />}
        </div>
        <div className={`result-panel ${result ? 'result-ready' : ''}`}>
          {!result ? <div className="result-placeholder"><span className="result-orb"><Gauge size={22} /></span><span className="micro-label">YOUR ESTIMATE</span><h2>Ready when you are.</h2><p>Complete each supported field to receive a prediction from the saved model.</p><div className="result-divider" /><div className="result-fact"><span>MODEL</span><strong>Linear Regression</strong></div><div className="result-fact"><span>INPUTS</span><strong>{features.length} verified attributes</strong></div><div className="result-fact"><span>SCOPE</span><strong>Peugeot 206 listings only</strong></div></div>
            : <div className="result-content"><span className="result-orb"><Check size={21} /></span><span className="micro-label">Prediction saved</span><h2>Your estimate</h2><PriceReference price={result.predicted_price} /><p className="unit-warning">{result.prediction_unit || 'Source price units; currency denomination unknown.'}</p><div className="result-divider" /><div className="saved-badge"><Check size={14} /> Saved to your private history</div><p className="result-timestamp">{formatDate(result.created_at)}</p><Link to="/predictions/history" className="quiet-link">View prediction history <ArrowRight size={14} /></Link><div className="result-disclaimer"><ShieldCheck size={15} /><span>This is a model estimate, not a professional appraisal or guaranteed sale price.</span></div></div>}
        </div>
      </div>}
      <p className="training-domain-note"><ShieldCheck size={15} /> Numeric limits reflect observed training data. The source does not specify the mileage unit or target currency.</p>
    </div>
  )
}

function PriceReference({ price, variant }: { price: number; variant?: 'dashboard' }) {
  return <div className={`price-reference ${variant === 'dashboard' ? 'price-reference-dashboard' : ''}`} role="group" aria-label="Estimated price and average-error reference range">
    <strong className="price-reference-value">{formatNumber(price)}</strong>
    <div className="price-range-track" aria-hidden="true"><span className="price-range-fill" /><span className="price-range-marker" /></div>
    <div className="price-range-labels">
      <span className="price-range-endpoint"><small>Lower reference</small><strong>{formatNumber(price - PRICE_REFERENCE_MAE_TOMAN)}</strong><small>Toman</small></span>
      <span className="price-range-endpoint price-range-upper"><small>Upper reference</small><strong>{formatNumber(price + PRICE_REFERENCE_MAE_TOMAN)}</strong><small>Toman</small></span>
    </div>
    <p className="price-range-caption">Reference range based on the model's average absolute error (MAE) of {formatNumber(PRICE_REFERENCE_MAE_TOMAN)} Toman. Not a guaranteed prediction interval.</p>
  </div>
}

function DynamicPredictionForm({ features, onSubmit, isLoading, initialValues }: { features: Feature[]; onSubmit: (input: CarInput) => void; isLoading: boolean; initialValues?: Record<string, unknown> }) {
  const defaults = Object.fromEntries(features.map((feature) => {
    const value = initialValues?.[feature.name]
    return [feature.name, value ?? (feature.type === 'integer' ? feature.minimum ?? '' : feature.supported_values?.[0] ?? '')]
  }))
  const [validationMessage, setValidationMessage] = useState('')
  const { register, handleSubmit, control, formState: { errors } } = useForm<Record<string, unknown>>({ defaultValues: defaults })

  const schema = createPredictionSchema(features)

  function submit(values: Record<string, unknown>) {
    const parsed = schema.safeParse(values)
    if (!parsed.success) {
      setValidationMessage(parsed.error.issues[0]?.message ?? 'Check the entered values.')
      return
    }
    setValidationMessage('')
    onSubmit(parsed.data as CarInput)
  }

  return <form className="prediction-form" onSubmit={handleSubmit(submit)}>
    <div className="field-grid">
      {features.map((feature, index) => {
        const message = (errors[feature.name]?.message as string | undefined)
        const description = index < 2 && feature.minimum !== undefined && feature.maximum !== undefined
          ? `Observed range: ${feature.minimum.toLocaleString()}–${feature.maximum.toLocaleString()}${feature.unit ? ` ${feature.unit}` : ''}`
          : feature.name === 'color' && feature.constraint_note
            ? 'Less common training colors are grouped as Other.'
            : undefined
        return <label className="field-label" key={feature.name}><span>{feature.display_label ?? humanize(feature.name)}<i className="required-star">*</i></span>
          {feature.type === 'integer'
            ? <input type="number" step="1" min={feature.minimum} max={feature.maximum} inputMode="numeric" placeholder={feature.minimum?.toString()} aria-describedby={`${feature.name}-hint`} {...register(feature.name, { valueAsNumber: true, required: true })} />
            : <Controller control={control} name={feature.name} render={({ field: controlField }) => <span className="select-wrap"><select {...controlField} value={String(controlField.value ?? '')} required>{(feature.supported_values ?? []).map((value) => <option value={value} key={value}>{value}</option>)}</select><ChevronDown size={16} /></span>} />}
          {description && <small className="field-hint" id={`${feature.name}-hint`}>{description}</small>}
          <FieldError message={message} />
        </label>
      })}
    </div>
    {validationMessage && <div className="inline-error" role="alert">{validationMessage}</div>}
    <div className="form-footer"><span><ShieldCheck size={15} /> Details validated against the model's training range</span><button className="button button-dark" disabled={isLoading}>{isLoading ? <><Spinner /> Calculating</> : <>Generate estimate <ArrowRight size={16} /></>}</button></div>
  </form>
}

function HistoryPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [selectedPrediction, setSelectedPrediction] = useState<Prediction | null>(null)
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<'desc' | 'asc'>('desc')
  const query = useQuery({ queryKey: ['predictions', page, sort], queryFn: () => api<PageResult<Prediction>>(`/predictions?page=${page}&page_size=10&sort=${sort}`) })
  const remove = useMutation({ mutationFn: (id: string) => api(`/predictions/${id}`, { method: 'DELETE' }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['predictions'] }) })
  const clearAll = useMutation({ mutationFn: () => api('/predictions', { method: 'DELETE' }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['predictions'] }) })
  const predictions = query.data?.items ?? []
  return <div className="page-stack"><PageIntro eyebrow="YOUR ARCHIVE" title="Prediction history." text="A private record of the estimates you've made. These are model outputs, not historical market prices." action={predictions.length > 0 ? <button className="button button-outline button-small" onClick={() => { if (window.confirm('Delete your entire prediction history?')) clearAll.mutate() }} disabled={clearAll.isPending}><Trash2 size={15} /> Clear history</button> : undefined} />
    <div className="history-toolbar"><span>{query.data?.total ?? 0} saved prediction{query.data?.total === 1 ? '' : 's'}</span><label className="sort-control">Sort by <select value={sort} onChange={(event) => { setSort(event.target.value as 'desc' | 'asc'); setPage(1) }}><option value="desc">Newest first</option><option value="asc">Oldest first</option></select><ChevronDown size={14} /></label></div>
    {query.isLoading ? <Skeleton className="history-skeleton" /> : query.isError ? <ErrorBanner message="Prediction history could not be loaded." /> : predictions.length ? <div className="panel history-table-wrap"><table className="history-table"><thead><tr><th>VEHICLE</th><th>ESTIMATE · SOURCE UNITS</th><th>CREATED</th><th>VEHICLE DETAILS</th><th>ACTIONS</th></tr></thead><tbody>{predictions.map((item) => <tr key={item.id}><td><span className="table-car"><CarFront size={16} /> Peugeot 206</span><small className="table-secondary">Model {item.model_version}</small></td><td><strong className="table-price">{formatNumber(item.predicted_price)}</strong><small className="table-secondary">Currency denomination unknown</small></td><td>{formatDate(item.created_at)}</td><td><div className="detail-chips"><span>{item.input_data.trim}</span><span>{item.input_data.year}</span><span>{formatNumber(item.input_data.mileage)} mileage</span></div></td><td><div className="table-actions"><button className="icon-button" title="View prediction details" aria-label="View prediction details" onClick={() => setSelectedPrediction(item)}><Search size={15} /></button><button className="icon-button" title="Reuse these inputs" aria-label="Reuse these inputs" onClick={() => navigate('/predict', { state: { input: item.input_data } })}><Pencil size={15} /></button><button className="icon-button danger-hover" title="Delete prediction" aria-label="Delete prediction" onClick={() => { if (window.confirm('Delete this prediction?')) remove.mutate(item.id) }}><Trash2 size={15} /></button></div></td></tr>)}</tbody></table><div className="pagination"><button className="button button-outline button-small" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</button><span>Page {page} of {Math.max(1, Math.ceil((query.data?.total ?? 0) / (query.data?.page_size ?? 10)))}</span><button className="button button-outline button-small" disabled={page * (query.data?.page_size ?? 10) >= (query.data?.total ?? 0)} onClick={() => setPage((current) => current + 1)}>Next</button></div></div> : <EmptyState icon={<History size={22} />} title="Nothing here yet" text="Your saved predictions will appear here after your first estimate." action={<Link to="/predict" className="button button-dark button-small">Create an estimate <ArrowRight size={14} /></Link>} />}
    {remove.isError && <ErrorBanner message={errorMessage(remove.error)} />}
    {selectedPrediction && <div className="dialog-backdrop" role="presentation" onClick={() => setSelectedPrediction(null)}><section className="prediction-dialog panel" role="dialog" aria-modal="true" aria-labelledby="prediction-dialog-title" onClick={(event) => event.stopPropagation()}><button className="icon-button dialog-close" aria-label="Close details" onClick={() => setSelectedPrediction(null)}><X size={17} /></button><span className="micro-label">SAVED MODEL OUTPUT</span><h2 id="prediction-dialog-title">Peugeot 206 estimate</h2><strong className="dialog-price">{formatNumber(selectedPrediction.predicted_price)}</strong><p className="unit-warning">{selectedPrediction.prediction_unit} · {formatDate(selectedPrediction.created_at)}</p><div className="dialog-fields">{INPUT_LABELS.map(([key, label]) => <div key={key}><span>{label}</span><strong>{String(selectedPrediction.input_data[key])}</strong></div>)}</div><button className="button button-dark" onClick={() => navigate('/predict', { state: { input: selectedPrediction.input_data } })}><Pencil size={15} /> Reuse these inputs</button></section></div>}
  </div>
}

function ComparePage() {
  const query = useQuery({ queryKey: ['predictions', 'compare'], queryFn: () => api<PageResult<Prediction>>('/predictions?page=1&page_size=100&sort=desc') })
  const items = query.data?.items ?? []
  const [leftId, setLeftId] = useState('')
  const [rightId, setRightId] = useState('')
  const left = items.find((item) => item.id === leftId)
  const right = items.find((item) => item.id === rightId)
  const difference = left && right ? right.predicted_price - left.predicted_price : null
  return <div className="page-stack"><PageIntro eyebrow="SCENARIO REVIEW" title="Compare two estimates." text="Review two saved model outputs side by side. This comparison describes predictions, not proven causal effects." />
    {query.isLoading ? <Skeleton className="history-skeleton" /> : query.isError ? <ErrorBanner message="Could not load predictions for comparison." /> : items.length < 2 ? <EmptyState icon={<Activity size={21} />} title="Two estimates make a comparison" text="Save at least two predictions to compare their inputs and outputs." action={<Link to="/predict" className="button button-dark button-small">Create prediction <ArrowRight size={14} /></Link>} /> : <>
      <div className="compare-selectors"><PredictionSelect label="Scenario A" value={leftId} items={items} onChange={setLeftId} exclude={rightId} /><PredictionSelect label="Scenario B" value={rightId} items={items} onChange={setRightId} exclude={leftId} /></div>
      {left && right && <div className="panel compare-panel"><div className="compare-head"><span className="micro-label">MODEL OUTPUTS · SOURCE PRICE UNITS</span><h2>Two saved Peugeot 206 estimates</h2></div><div className="compare-values"><CompareCard item={left} label="SCENARIO A" /><div className="compare-divider"><span>VS</span></div><CompareCard item={right} label="SCENARIO B" /></div><div className="compare-bars" aria-label="Visual comparison of the two predicted prices">{[[left, 'Scenario A'], [right, 'Scenario B']].map(([item, label]) => <div className="compare-bar-row" key={label as string}><span>{label as string}</span><div><i style={{ width: `${(item as Prediction).predicted_price / Math.max(left.predicted_price, right.predicted_price) * 100}%` }} /></div><strong>{formatNumber((item as Prediction).predicted_price)}</strong></div>)}</div><div className="difference-row"><span>Difference between outputs</span><strong className={difference! >= 0 ? 'positive' : 'negative'}>{difference! >= 0 ? '+' : '−'}{formatNumber(Math.abs(difference!))} <small>{difference! >= 0 ? <ArrowUpRight size={15} /> : <ArrowDownRight size={15} />}</small></strong></div><div className="compare-inputs"><h3>Input differences</h3>{INPUT_LABELS.map(([key, label]) => left.input_data[key] !== right.input_data[key] && <div className="input-diff" key={key}><span>{label}</span><span>{String(left.input_data[key])}</span><ArrowRight size={13} /><span>{String(right.input_data[key])}</span></div>)}</div><p className="chart-disclaimer">A difference between model outputs does not establish that one input change caused the price difference.</p></div>}
    </>}
  </div>
}

function ChatPage() {
  return <div className="chat-page"><section className="chat-coming-soon panel" aria-labelledby="chat-coming-soon-title">
    <span className="result-orb"><MessageCircle size={22} /></span>
    <span className="availability-badge">Coming soon</span>
    <h1 id="chat-coming-soon-title">AI conversations are not ready yet.</h1>
    <p>This part of the application is still being developed. Conversation and AI chat features will be available here in a future update.</p>
  </section></div>
}

function ProfilePage() {
  const { user, setUser, signOut } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState(user?.full_name ?? '')
  const [message, setMessage] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [passwordSaved, setPasswordSaved] = useState(false)
  const [passwordValues, setPasswordValues] = useState({ current_password: '', new_password: '', password_confirmation: '' })
  const update = useMutation({ mutationFn: () => api<User>('/users/me', { method: 'PATCH', body: JSON.stringify({ full_name: name }) }), onSuccess: (updated) => { setUser(updated); setMessage('Profile updated.'); queryClient.invalidateQueries() } })
  const deleteAccount = useMutation({ mutationFn: () => api('/users/me', { method: 'DELETE' }), onSuccess: async () => { clearAccessToken(); setUser(null); await signOut().catch(() => undefined); navigate('/') } })
  const changePassword = useMutation({ mutationFn: () => api('/users/me/password', { method: 'POST', body: JSON.stringify(passwordValues) }), onSuccess: () => { setPasswordError(''); setPasswordSaved(true); setPasswordValues({ current_password: '', new_password: '', password_confirmation: '' }) }, onError: (reason) => { setPasswordSaved(false); setPasswordError(errorMessage(reason)) } })
  return <div className="page-stack"><PageIntro eyebrow="ACCOUNT SETTINGS" title="Your profile." text="Manage the account that owns your predictions and conversations." />
    <div className="profile-layout"><div className="panel profile-panel"><div className="profile-avatar">{initials(user?.full_name)}</div><span className="micro-label">PERSONAL DETAILS</span><h2>Account information</h2><form className="form-stack" onSubmit={(event) => { event.preventDefault(); update.mutate() }}><label className="field-label">Full name<input value={name} onChange={(event) => setName(event.target.value)} minLength={2} maxLength={120} required /></label><label className="field-label">Email address<input value={user?.email ?? ''} readOnly /><small className="field-hint">Email changes aren't available from this profile yet.</small></label><div className="profile-actions"><button className="button button-dark" disabled={update.isPending}>{update.isPending ? <Spinner /> : <Check size={16} />} Save changes</button>{message && <span className="success-text">{message}</span>}{update.isError && <FieldError message={errorMessage(update.error)} />}</div></form>
      <div className="profile-security-form"><div className="security-divider" /><span className="micro-label">CHANGE PASSWORD</span><form className="form-stack" onSubmit={(event) => { event.preventDefault(); setPasswordSaved(false); setPasswordError(''); if (passwordValues.new_password.length < 12) { setPasswordError('Use at least 12 characters for your new password.'); return } if (passwordValues.new_password !== passwordValues.password_confirmation) { setPasswordError('New passwords do not match.'); return } changePassword.mutate() }}><label className="field-label">Current password<input type="password" autoComplete="current-password" value={passwordValues.current_password} onChange={(event) => setPasswordValues({ ...passwordValues, current_password: event.target.value })} required /></label><label className="field-label">New password<input type="password" autoComplete="new-password" value={passwordValues.new_password} onChange={(event) => setPasswordValues({ ...passwordValues, new_password: event.target.value })} minLength={12} required /></label><label className="field-label">Confirm new password<input type="password" autoComplete="new-password" value={passwordValues.password_confirmation} onChange={(event) => setPasswordValues({ ...passwordValues, password_confirmation: event.target.value })} required /></label>{passwordError && <FieldError message={passwordError} />}{passwordSaved && <span className="success-text">Password changed successfully.</span>}<button className="button button-outline button-small" disabled={changePassword.isPending}>{changePassword.isPending ? <Spinner /> : <ShieldCheck size={15} />} Update password</button></form></div></div>
      <div className="panel security-panel"><span className="security-icon"><ShieldCheck size={19} /></span><span className="micro-label">ACCOUNT SECURITY</span><h2>Your data stays yours.</h2><p>Predictions and conversations are private to this account. The backend checks ownership on each protected request.</p><div className="security-divider" /><div className="security-row"><span>Authentication</span><strong>Secure session</strong></div><div className="security-row"><span>Password management</span><strong>Update in profile</strong></div><button className="button button-outline button-small logout-button" onClick={async () => { await signOut(); navigate('/login') }}><LogOut size={15} /> Log out</button></div>
    </div>
    <div className="danger-zone"><div><span className="micro-label">DANGER ZONE</span><h3>Delete your account</h3><p>This permanently removes your account, predictions, and conversations.</p></div><button className="button button-danger" onClick={() => { if (window.confirm('Permanently delete your account and all associated data?')) deleteAccount.mutate() }} disabled={deleteAccount.isPending}><Trash2 size={15} /> Delete account</button></div>
  </div>
}

function ModelPage() {
  const { user } = useAuth()
  const query = useQuery({ queryKey: ['model-info'], queryFn: () => api<ModelInfo>('/model/info') })
  const featuresQuery = useQuery({ queryKey: ['model-features'], queryFn: () => api<FeatureResponse>('/model/features') })
  const info = query.data
  const features = getFeatures(featuresQuery.data)
  return <div className="page-stack">
    <section className="model-hero" aria-labelledby="model-hero-title">
      <img className="model-hero-image" src="/peugeot-206-model.webp" alt="Silver 2002 Peugeot 206 LX hatchback" fetchPriority="high" />
      <span className="model-photo-credit">Photo by <a href="https://commons.wikimedia.org/wiki/User:Vauxford" target="_blank" rel="noreferrer">Vauxford</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer">CC BY-SA 4.0</a></span>
      <div className="model-hero-copy">
        <span className="model-hero-kicker">Peugeot 206 · model overview</span>
        <h1 id="model-hero-title">A closer look at your 206 estimate.</h1>
        <p>A focused price estimator built around the Peugeot 206 listings represented in its training data.</p>
        <div className="model-hero-facts"><span><strong>One</strong> supported vehicle</span><span><strong>Six</strong> verified inputs</span></div>
        <Link to={user ? '/predict' : '/register'} className="button button-light">Get a Peugeot 206 estimate <ArrowRight size={16} /></Link>
      </div>
    </section>
    {query.isError && <ErrorBanner message="Could not retrieve model metadata." />}
    <section className="model-summary-grid"><div className="model-summary-card"><span className="summary-icon"><CarFront size={18} /></span><span className="micro-label">Supported vehicle</span><strong>{info?.vehicle_model ?? 'Peugeot 206'}</strong><p>The dataset contains listings identified as Peugeot 206. This tool is not validated for other cars.</p></div><div className="model-summary-card"><span className="summary-icon"><Activity size={18} /></span><span className="micro-label">Model type</span><strong>{info?.model_type ?? 'Linear Regression'}</strong><p>A regression model estimates a numeric price from the fields listed below.</p></div><div className="model-summary-card"><span className="summary-icon"><ShieldCheck size={18} /></span><span className="micro-label">Output unit</span><strong>Unspecified source units</strong><p>The data does not document the currency denomination. No currency conversion is applied.</p></div></section>
    <div className="panel method-panel"><div className="panel-heading"><div><span className="micro-label">Inference flow</span><h2>From car details to estimate</h2></div><span className="pipeline-count">6 inputs <ArrowRight size={13} /> 39 encoded signals</span></div><div className="pipeline-steps">{['Validate the six raw car fields', 'Apply saved color grouping and fitted encoder', 'Run the saved Linear Regression estimator', 'Store your output in your private history'].map((step, index) => <div className="pipeline-step" key={step}><span>{String(index + 1).padStart(2, '0')}</span><p>{step}</p></div>)}</div></div>
    <div className="panel baseline-panel"><div className="panel-heading"><div><span className="micro-label">EARLIER REPORTED EVALUATION</span><h2>Linear Regression baseline</h2></div><span className="baseline-score">91.04% <small>custom score</small></span></div><div className="baseline-metrics"><div><span>MAE</span><strong>{formatNumber(PRICE_REFERENCE_MAE_TOMAN)}</strong></div><div><span>MSE</span><strong>2.28394 × 10<sup>16</sup></strong></div><div><span>RMSE</span><strong>151,127,104</strong></div><div><span>R²</span><strong>0.8945</strong></div></div><p className="baseline-caveat">These results were supplied by the project owner for an earlier 20% holdout baseline. They are not stored in the repository or independently reproduced, and predate the latest preprocessing changes. The 91.04% figure is 100 − MAE / mean(actual) × 100, a custom summary rather than a standard regression accuracy metric. Do not interpret these as confirmed performance of the current saved artifacts.</p></div>
    <div className="panel feature-reference"><div className="panel-heading"><div><span className="micro-label">VERIFIED INPUT CONTRACT</span><h2>Fields the model actually uses</h2></div></div><div className="feature-list">{features.map((feature) => <div className="feature-row" key={feature.name}><div><strong>{feature.display_label ?? humanize(feature.name)}</strong><small><code>{feature.name}</code>{feature.unit ? ` · ${feature.unit}` : ''}</small></div><div className="feature-values">{feature.supported_values ? feature.supported_values.map((value) => <span className="detail-tag" key={value}>{value}</span>) : <span className="observed-range">Observed training range: {feature.minimum}–{feature.maximum}</span>}</div></div>)}</div></div>
    <div className="model-limitation"><ShieldCheck size={17} /><div><strong>Limitations to keep in mind</strong><p>There are 764 cleaned training listings. Evaluation metrics were not saved as model metadata, so this site makes no accuracy or confidence claim. A model estimate is not a professional appraisal or guaranteed sale price.</p></div></div>
  </div>
}

function PageIntro({ eyebrow, title, text, action }: { eyebrow: string; title: string; text: string; action?: React.ReactNode }) {
  return <section className="page-intro"><div><div className="eyebrow"><span className="eyebrow-dot" /> {eyebrow}</div><h1>{title}</h1><p>{text}</p></div>{action}</section>
}

function StatCard({ label, value, hint, icon }: { label: string; value: React.ReactNode; hint: string; icon: React.ReactNode }) {
  return <div className="stat-card"><div className="stat-top"><span className="stat-label">{label}</span><span className="stat-icon">{icon}</span></div><strong>{value}</strong><span className="stat-hint">{hint}</span></div>
}

function PredictionSelect({ label, value, items, onChange, exclude }: { label: string; value: string; items: Prediction[]; onChange: (value: string) => void; exclude: string }) {
  return <label className="field-label compare-select"><span>{label}</span><span className="select-wrap"><select value={value} onChange={(event) => onChange(event.target.value)}><option value="">Select a saved estimate</option>{items.filter((item) => item.id !== exclude).map((item) => <option value={item.id} key={item.id}>{formatDate(item.created_at)} · {item.input_data.trim} · {formatNumber(item.predicted_price)}</option>)}</select><ChevronDown size={16} /></span></label>
}

function CompareCard({ item, label }: { item: Prediction; label: string }) {
  return <div className="compare-value-card"><span className="micro-label">{label}</span><strong>{formatNumber(item.predicted_price)}</strong><span className="compare-date">{formatDate(item.created_at)}</span><div className="compare-summary"><span>{item.input_data.trim}</span><span>{item.input_data.transmission}</span><span>{item.input_data.body_status}</span><span>{item.input_data.color}</span><span>Year {item.input_data.year}</span><span>{formatNumber(item.input_data.mileage)} mileage</span></div></div>
}

function EmptyState({ icon, title, text, action }: { icon: React.ReactNode; title: string; text: string; action?: React.ReactNode }) {
  return <div className="empty-state"><span className="empty-icon">{icon}</span><strong>{title}</strong><p>{text}</p>{action}</div>
}

function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner" role="alert"><X size={15} /><span>{message}</span></div>
}

function FieldError({ message }: { message?: unknown }) {
  return message ? <small className="field-error">{String(message)}</small> : null
}

function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-label="Loading" />
}

function Spinner() {
  return <span className="spinner" aria-label="Loading" />
}

function FullScreenLoading() {
  return <div className="full-loading"><span className="brand-mark"><CarFront size={20} /></span><Spinner /><span>Preparing your workspace</span></div>
}

function initials(name?: string) {
  return name?.split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'U'
}

function pageTitle() {
  const path = window.location.pathname
  if (path === '/dashboard') return 'Dashboard'
  if (path === '/predict') return 'New prediction'
  if (path.startsWith('/predictions')) return 'Prediction history'
  if (path === '/compare') return 'Compare predictions'
  if (path.startsWith('/chat')) return 'Valuation chat'
  if (path === '/profile') return 'Profile'
  if (path === '/model') return 'How it works'
  return 'Workspace'
}

function humanize(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatNumber(value: number) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)
}

function formatDate(value: string) {
  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  return 'Something went wrong. Please try again.'
}

type PageResult<T> = { items: T[]; total: number; page?: number; page_size?: number; pages?: number; has_more?: boolean }
type FeatureResponse = { features?: Feature[]; input_features?: Feature[]; items?: Feature[] } | Feature[]
type ModelInfo = { vehicle_model?: string; model_type?: string; model_version?: string; chat_assistant_available?: boolean; target?: { name: string; unit?: string | null } }
const INPUT_LABELS: Array<[keyof CarInput, string]> = [['year', 'Year'], ['mileage', 'Mileage'], ['trim', 'Trim'], ['transmission', 'Transmission'], ['body_status', 'Body condition'], ['color', 'Color']]

function getFeatures(response?: FeatureResponse): Feature[] {
  if (!response) return []
  if (Array.isArray(response)) return response
  return response.features ?? response.input_features ?? response.items ?? []
}

export default App
