// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { clearAccessToken, getAccessToken } from './services/api'

const user = { id: 'user-1', full_name: 'Demo Driver', email: 'demo@example.com' }

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter><App /></BrowserRouter>
    </QueryClientProvider>
  )
}

describe('application authentication routes', () => {
  beforeEach(() => {
    clearAccessToken()
    document.cookie = 'csrf_token=; Max-Age=0; path=/'
    window.history.replaceState({}, '', '/login')
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ error: { code: 'unauthorized', message: 'Authentication required.' } }, 401)))
  })

  afterEach(() => {
    cleanup()
    clearAccessToken()
    document.cookie = 'csrf_token=; Max-Age=0; path=/'
    vi.unstubAllGlobals()
  })

  it('shows the sign-in form on the public login route', async () => {
    renderApp()
    expect(await screen.findByRole('heading', { name: 'Welcome back.' })).toBeTruthy()
    expect(screen.getByLabelText('Email address')).toBeTruthy()
    expect(screen.getByLabelText('Password')).toBeTruthy()
    expect(screen.queryByRole('img', { name: /Peugeot 206 hatchback photographed/ })).toBeNull()
    expect(screen.queryByRole('link', { name: /Photo: Vauxford/ })).toBeNull()
  })

  it('redirects an unauthenticated dashboard visit to login', async () => {
    window.history.replaceState({}, '', '/dashboard')
    renderApp()
    expect(await screen.findByRole('heading', { name: 'Welcome back.' })).toBeTruthy()
  })

  it('shows an unavailable notice instead of chat controls', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/auth/me')) return jsonResponse(user)
      return jsonResponse({ error: { code: 'not_found', message: 'Not found.' } }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState({}, '', '/chat')
    renderApp()

    expect(await screen.findByRole('heading', { name: 'AI conversations are not ready yet.' })).toBeTruthy()
    expect(screen.getByText('Coming soon')).toBeTruthy()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByRole('button', { name: /start a conversation/i })).toBeNull()
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/conversations'))).toBe(false)
  })

  it('collapses the desktop sidebar while keeping its expand control available', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/auth/me')) return jsonResponse(user)
      if (String(input).includes('/predictions')) return jsonResponse({ items: [], total: 0, page: 1, page_size: 8 })
      return jsonResponse({ error: { code: 'not_found', message: 'Not found.' } }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState({}, '', '/dashboard')
    renderApp()

    await screen.findByRole('heading', { name: 'Good to see you, Demo.' })
    const sidebar = screen.getByRole('complementary', { name: 'Primary navigation' })
    const collapseButton = screen.getByRole('button', { name: 'Collapse sidebar' })
    expect(collapseButton.getAttribute('aria-controls')).toBe('primary-sidebar')
    expect(collapseButton.getAttribute('aria-expanded')).toBe('true')

    fireEvent.click(collapseButton)
    expect(screen.getByRole('button', { name: 'Expand sidebar' }).getAttribute('aria-expanded')).toBe('false')
    expect(sidebar.classList.contains('sidebar-collapsed')).toBe(true)
    expect(sidebar.parentElement?.classList.contains('workspace-sidebar-collapsed')).toBe(true)

    fireEvent.click(screen.getByRole('button', { name: 'Expand sidebar' }))
    expect(screen.getByRole('button', { name: 'Collapse sidebar' }).getAttribute('aria-expanded')).toBe('true')
    expect(sidebar.classList.contains('sidebar-collapsed')).toBe(false)
  })

  it('opens the mobile drawer, closes on Escape or backdrop, and closes after navigation', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/auth/me')) return jsonResponse(user)
      if (String(input).includes('/predictions')) return jsonResponse({ items: [], total: 0, page: 1, page_size: 8 })
      return jsonResponse({ error: { code: 'not_found', message: 'Not found.' } }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState({}, '', '/dashboard')
    renderApp()

    await screen.findByRole('heading', { name: 'Good to see you, Demo.' })
    const sidebar = screen.getByRole('complementary', { name: 'Primary navigation' })
    const openButton = screen.getByRole('button', { name: 'Open navigation' })
    expect(sidebar.classList.contains('sidebar-open')).toBe(false)
    expect(openButton.getAttribute('aria-expanded')).toBe('false')

    fireEvent.click(openButton)
    expect(screen.getByRole('button', { name: 'Close navigation' }).getAttribute('aria-expanded')).toBe('true')
    expect(sidebar.classList.contains('sidebar-open')).toBe(true)
    expect(document.body.style.overflow).toBe('hidden')
    expect(document.activeElement).toBe(screen.getByRole('link', { name: '206 / estimate home' }))

    fireEvent.keyDown(window, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Log out' }))
    fireEvent.keyDown(window, { key: 'Escape' })
    await waitFor(() => expect(sidebar.classList.contains('sidebar-open')).toBe(false))
    expect(document.body.style.overflow).toBe('')
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Open navigation' }))

    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    fireEvent.click(screen.getByRole('button', { name: 'Close navigation backdrop' }))
    await waitFor(() => expect(sidebar.classList.contains('sidebar-open')).toBe(false))

    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    fireEvent.click(screen.getAllByRole('link', { name: 'New prediction' })[0])
    expect(await screen.findByRole('heading', { name: 'Describe your 206.' })).toBeTruthy()
    expect(sidebar.classList.contains('sidebar-open')).toBe(false)
    expect(document.body.style.overflow).toBe('')
  })

  it('uses a photo-free Peugeot 206 coverage design on the landing page', async () => {
    window.history.replaceState({}, '', '/')
    renderApp()

    expect(await screen.findByRole('img', { name: 'Peugeot 206 estimate coverage graphic' })).toBeTruthy()
    expect(screen.queryByRole('img', { name: 'Photograph of a Peugeot 206 hatchback' })).toBeNull()
    expect(screen.queryByRole('link', { name: /Photo by Vauxford/ })).toBeNull()
  })

  it('features a locally hosted Peugeot 206 photo on the model page', async () => {
    window.history.replaceState({}, '', '/model')
    renderApp()

    expect(await screen.findByRole('heading', { name: 'A closer look at your 206 estimate.' })).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Silver 2002 Peugeot 206 LX hatchback' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Vauxford' })).toBeTruthy()
    expect(screen.getByRole('link', { name: 'CC BY-SA 4.0' })).toBeTruthy()
  })

  it('restores a signed-in session from its refresh cookie after reload', async () => {
    document.cookie = 'csrf_token=csrf-value; path=/'
    let profileRequests = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) {
        profileRequests += 1
        if (new Headers(init?.headers).get('Authorization') === 'Bearer refreshed-token') return jsonResponse(user)
        return jsonResponse({ error: { code: 'unauthorized', message: 'Authentication required.' } }, 401)
      }
      if (url.endsWith('/auth/refresh')) return jsonResponse({ access_token: 'refreshed-token', token_type: 'bearer' })
      if (url.includes('/predictions')) return jsonResponse({ items: [], total: 0, page: 1, page_size: 8 })
      return jsonResponse({ error: { code: 'not_found', message: 'Not found.' } }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState({}, '', '/')
    renderApp()

    expect(await screen.findByRole('heading', { name: 'Good to see you, Demo.' })).toBeTruthy()
    expect(getAccessToken()).toBe('refreshed-token')
    expect(profileRequests).toBe(2)
    const refreshRequest = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/auth/refresh'))
    expect(refreshRequest?.[1]).toEqual(expect.objectContaining({
      credentials: 'include',
      headers: { 'X-CSRF-Token': 'csrf-value' }
    }))
  })

  it('signs in, keeps the access token in memory, and opens the dashboard', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) return jsonResponse({ error: { code: 'unauthorized', message: 'Authentication required.' } }, 401)
      if (url.endsWith('/auth/login')) return jsonResponse({ access_token: 'short-lived-token', token_type: 'bearer', user })
      if (url.includes('/predictions')) return jsonResponse({
        items: [{
          id: 'dashboard-prediction',
          input_data: { trim: 'تیپ 1', year: 1380, mileage: 100000, transmission: 'دنده ای', body_status: 'بدون رنگ', color: 'سفید' },
          predicted_price: 300000000,
          prediction_unit: 'Source price units.',
          model_version: 'test-version',
          created_at: '2026-01-01T00:00:00Z'
        }],
        total: 1,
        page: 1,
        page_size: 8
      })
      if (url.includes('/conversations')) return jsonResponse({ items: [], total: 0 })
      return jsonResponse({ error: { code: 'not_found', message: 'Not found.' } }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderApp()
    await screen.findByRole('heading', { name: 'Welcome back.' })
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: user.email } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-valid-password-123' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))
    expect(await screen.findByRole('heading', { name: 'Good to see you, Demo.' })).toBeTruthy()
    fireEvent.click(screen.getByRole('link', { name: 'How it works' }))
    expect(await screen.findByRole('heading', { name: 'A closer look at your 206 estimate.' })).toBeTruthy()
    expect(screen.getByRole('link', { name: /Get a Peugeot 206 estimate/ }).getAttribute('href')).toBe('/predict')
    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeTruthy()
    expect(getAccessToken()).toBe('short-lived-token')
    const formatPrice = (price: number) => new Intl.NumberFormat().format(price)
    fireEvent.click(screen.getByRole('link', { name: 'Dashboard' }))
    expect(await screen.findByRole('heading', { name: 'Good to see you, Demo.' })).toBeTruthy()
    const dashboardEstimate = await screen.findByRole('region', { name: 'Latest estimate' })
    expect(dashboardEstimate.textContent).toContain(formatPrice(300000000))
    expect(dashboardEstimate.textContent).toContain(formatPrice(183283706))
    expect(dashboardEstimate.textContent).toContain(formatPrice(416716294))
    expect(screen.queryByRole('img', { name: /Peugeot 206 hatchback photographed/ })).toBeNull()
    expect(screen.getByText('Not available yet')).toBeTruthy()
    expect(screen.getByText(/This section will be ready when AI chat is fully developed/)).toBeTruthy()
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/conversations'))).toBe(false)
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/predictions?page=1&page_size=8',
        expect.objectContaining({ headers: expect.any(Headers) })
      )
    })
  })

  it('registers, signs in, loads verified fields, and submits a prediction', async () => {
    const userEventInstance = userEvent.setup()
    const submittedInputs: unknown[] = []
    const features = [
      { name: 'year', display_label: 'Vehicle year (as recorded)', type: 'integer', required: true, minimum: 1380, maximum: 1402, unit: null, supported_values: null, constraint_note: 'Observed training range.' },
      { name: 'mileage', display_label: 'Mileage', type: 'integer', required: true, minimum: 0, maximum: 900000, unit: null, supported_values: null, constraint_note: 'Observed training range.' },
      { name: 'trim', display_label: 'Trim', type: 'string', required: true, minimum: null, maximum: null, unit: null, supported_values: ['تیپ 1'], constraint_note: null },
      { name: 'transmission', display_label: 'Transmission', type: 'string', required: true, minimum: null, maximum: null, unit: null, supported_values: ['دنده ای'], constraint_note: null },
      { name: 'body_status', display_label: 'Body condition', type: 'string', required: true, minimum: null, maximum: null, unit: null, supported_values: ['بدون رنگ'], constraint_note: null },
      { name: 'color', display_label: 'Color', type: 'string', required: true, minimum: null, maximum: null, unit: null, supported_values: ['سفید'], constraint_note: null }
    ]
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) return jsonResponse({ error: { code: 'unauthorized', message: 'Authentication required.' } }, 401)
      if (url.endsWith('/auth/register')) return jsonResponse(user, 201)
      if (url.endsWith('/auth/login')) return jsonResponse({ access_token: 'flow-token', token_type: 'bearer', user })
      if (url.endsWith('/model/features')) return jsonResponse({ features, target: { name: 'price', unit: null, unit_note: 'Source price units.' } })
      if (url.endsWith('/predictions') && init?.method === 'POST') {
        submittedInputs.push(JSON.parse(String(init.body)))
        return jsonResponse({
          id: 'prediction-1',
          input_data: submittedInputs[0],
          predicted_price: 300000000,
          prediction_unit: 'Source price units.',
          model_version: 'test-version',
          created_at: '2026-01-01T00:00:00Z'
        }, 201)
      }
      if (url.includes('/predictions')) return jsonResponse({ items: [], total: 0, page: 1, page_size: 8 })
      if (url.includes('/conversations')) return jsonResponse({ items: [], total: 0 })
      if (url.endsWith('/model/info')) return jsonResponse({ vehicle_model: 'Peugeot 206', model_version: 'test-version', chat_assistant_available: false, target: { name: 'price', unit: null } })
      return jsonResponse({ error: { code: 'not_found', message: 'Not found.' } }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState({}, '', '/register')
    renderApp()

    await userEventInstance.type(await screen.findByLabelText('Full name'), user.full_name)
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: user.email } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-valid-password-123' } })
    expect((screen.getByLabelText('Email address') as HTMLInputElement).value).toBe(user.email)
    await userEventInstance.type(screen.getByLabelText('Confirm password'), 'a-valid-password-123')
    await userEventInstance.click(screen.getByRole('button', { name: /create account/i }))
    await screen.findByRole('heading', { name: 'Welcome back.' })

    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: user.email } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-valid-password-123' } })
    expect((screen.getByLabelText('Email address') as HTMLInputElement).value).toBe(user.email)
    await userEventInstance.click(screen.getByRole('button', { name: /sign in/i }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/login',
      expect.objectContaining({ method: 'POST' })
    ))
    await waitFor(() => expect(getAccessToken()).toBe('flow-token'))
    await screen.findByRole('heading', { name: 'Good to see you, Demo.' })
    await userEventInstance.click(screen.getAllByRole('link', { name: /new prediction/i })[0])
    await screen.findByRole('heading', { name: 'Describe your 206.' })
    await screen.findByRole('button', { name: /generate estimate/i })
    await userEventInstance.click(screen.getByRole('button', { name: /generate estimate/i }))

    expect(await screen.findByText('Prediction saved')).toBeTruthy()
    const formatPrice = (price: number) => new Intl.NumberFormat().format(price)
    expect(screen.getByText(formatPrice(300000000))).toBeTruthy()
    expect(screen.getByText(formatPrice(183283706))).toBeTruthy()
    expect(screen.getByText(formatPrice(416716294))).toBeTruthy()
    expect(screen.getByText(/average absolute error \(MAE\) of 116,716,294 Toman/)).toBeTruthy()
    expect(submittedInputs).toEqual([{
      year: 1380,
      mileage: 0,
      trim: 'تیپ 1',
      transmission: 'دنده ای',
      body_status: 'بدون رنگ',
      color: 'سفید'
    }])
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/predictions',
      expect.objectContaining({ method: 'POST', headers: expect.any(Headers) })
    )
  })
})
