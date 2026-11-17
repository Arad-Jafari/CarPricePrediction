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

function sseResponse(events: Array<[string, unknown]>) {
  const encoder = new TextEncoder()
  const body = events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join('')
  return new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(body))
      controller.close()
    }
  }), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
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

  it('shows the assistant landing state with a realistic unavailable status', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/auth/me')) return jsonResponse(user)
      if (String(input).endsWith('/model/info')) return jsonResponse({ vehicle_model: 'Peugeot 206', model_version: 'test-version', chat_assistant_available: false, target: { name: 'price', unit: null } })
      return jsonResponse({ error: { code: 'not_found', message: 'Not found.' } }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState({}, '', '/chat')
    renderApp()

    expect(await screen.findByRole('heading', { name: 'Your Car AI Assistant' })).toBeTruthy()
    expect(await screen.findByText(/local ai unavailable/i)).toBeTruthy()
    expect(screen.getByRole('textbox', { name: /ask your car assistant/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /send/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Explain my latest price estimate' })).toBeTruthy()
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/conversations'))).toBe(false)
  })

  it('creates a conversation and renders progressive backend SSE response events', async () => {
    const streamRequestBodies: unknown[] = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) return jsonResponse(user)
      if (url.endsWith('/model/info')) return jsonResponse({
        vehicle_model: 'Peugeot 206',
        chat_assistant_available: true,
        chat_model: 'gemma3:1b',
        chat_models: ['gemma3:1b', 'qwen2.5:1.5b'],
        target: { name: 'price', unit: null }
      })
      if (url.endsWith('/conversations') && init?.method === 'POST') {
        return jsonResponse({ items: [{ id: 'conversation-1', title: 'Price factors', created_at: '2026-01-01', updated_at: '2026-01-01' }] }, 201)
      }
      if (url.endsWith('/messages/stream')) {
        streamRequestBodies.push(JSON.parse(String(init?.body)))
        return sseResponse([
          ['start', { user_message_id: 'user-message-1', model: 'qwen2.5:1.5b' }],
          ['token', { token: 'A real-time ' }],
          ['token', { token: 'mocked response.' }],
          ['done', { message: { id: 'assistant-message-1', role: 'assistant', content: 'A real-time mocked response.', message_metadata: { status: 'complete' } } }]
        ])
      }
      if (url.endsWith('/conversations/conversation-1/messages')) return jsonResponse({
        items: [
          { id: 'user-message-1', role: 'user', content: 'What affects Peugeot prices?' },
          { id: 'assistant-message-1', role: 'assistant', content: 'A real-time mocked response.', message_metadata: { status: 'complete' } }
        ]
      })
      if (url.includes('/messages')) return jsonResponse({ items: [] })
      if (url.includes('/conversations?')) return jsonResponse({ items: [], total: 0 })
      return jsonResponse({ error: { code: 'not_found', message: 'Not found.' } }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState({}, '', '/chat')
    renderApp()

    await screen.findByRole('heading', { name: 'Your Car AI Assistant' })
    await waitFor(() => expect((screen.getByLabelText('Model') as HTMLSelectElement).disabled).toBe(false))
    fireEvent.change(screen.getByLabelText('Model'), { target: { value: 'qwen2.5:1.5b' } })
    await userEvent.type(screen.getByRole('textbox', { name: /ask your car assistant/i }), 'What affects Peugeot prices?')
    await userEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('A real-time mocked response.')).toBeTruthy()
    expect(streamRequestBodies).toEqual([{ content: 'What affects Peugeot prices?', model: 'qwen2.5:1.5b' }])
    expect(screen.getByRole('button', { name: 'Copy response' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Regenerate response' })).toBeTruthy()
  })

  it('searches and restores a conversation from the floating history panel', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/me')) return jsonResponse(user)
      if (url.endsWith('/model/info')) return jsonResponse({ chat_assistant_available: false, target: { name: 'price', unit: null } })
      if (url.includes('/conversations?')) return jsonResponse({
        items: [{
          id: 'conversation-2',
          title: 'Price discussion',
          created_at: '2026-01-01T10:00:00Z',
          updated_at: '2026-01-02T10:00:00Z',
          last_message_preview: 'Mileage and condition affect estimates.',
          last_message_at: '2026-01-02T10:00:00Z'
        }],
        total: 1
      })
      if (url.endsWith('/conversations/conversation-2/messages')) return jsonResponse({
        items: [{ id: 'restored-1', role: 'user', content: 'How does mileage matter?', created_at: '2026-01-02T10:00:00Z' }]
      })
      return jsonResponse({ error: { code: 'not_found', message: 'Not found.' } }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    window.history.replaceState({}, '', '/chat')
    renderApp()

    await screen.findByRole('heading', { name: 'Your Car AI Assistant' })
    await userEvent.click(screen.getByRole('button', { name: /history/i }))
    expect(await screen.findByText('Mileage and condition affect estimates.')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: /Price discussion/ }))
    expect(await screen.findByText('How does mileage matter?')).toBeTruthy()
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('search='))).toBe(true)
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
    expect(screen.getByText('Unavailable')).toBeTruthy()
    expect(screen.getByRole('link', { name: /Start a conversation/ })).toBeTruthy()
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
