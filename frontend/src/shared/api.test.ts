import { api, ApiError } from './api'
import { stubApi } from '@/test/utils'

afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('returns parsed JSON', async () => {
    stubApi({ 'GET /runs': [{ run_id: 'a' }] })
    await expect(api('/runs')).resolves.toEqual([{ run_id: 'a' }])
  })
  it('uses the server detail text as the error message', async () => {
    stubApi({
      'POST /forecast/quick-demo': new Response(JSON.stringify({ detail: 'Disabled: use Zoho' }), { status: 410 }),
    })
    await expect(api('/forecast/quick-demo', { method: 'POST' })).rejects.toMatchObject({
      status: 410,
      message: 'Disabled: use Zoho',
    })
  })
  it('falls back to a generic message when the body is not JSON', async () => {
    stubApi({ 'GET /x': new Response('Internal Server Error', { status: 500 }) })
    await expect(api('/x')).rejects.toThrow('/x failed (500)')
  })
  it('sends the user to the login page on 401 (but not for the auth calls themselves)', async () => {
    stubApi({ 'GET /runs': new Response('{}', { status: 401 }), 'GET /auth/me': new Response('{}', { status: 401 }) })
    const loc = { href: '', pathname: '/ui3/matrix' }
    vi.stubGlobal('location', loc)
    await expect(api('/runs')).rejects.toBeInstanceOf(ApiError)
    expect(loc.href).toBe('/login?next=%2Fui3%2Fmatrix')
    loc.href = ''
    await expect(api('/auth/me')).rejects.toBeInstanceOf(ApiError)
    expect(loc.href).toBe('')
  })
})
