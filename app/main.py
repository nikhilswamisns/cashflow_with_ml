from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os
from app import db
from app import auth
from app.output.json_api import router
app = FastAPI(title='Cash Flow Forecasting Engine', description='Phase 1 — File-Ingestion Mode. No live Zoho MCP. No bank feed. No LLM in the numeric path. Every number is deterministic, confidence-tagged, and auditable.', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

@app.on_event('startup')
def on_startup():
    db.init_db()
    if LOCAL_NO_LOGIN:
        print('\n  LOGIN DISABLED (CASHFLOW_DISABLE_AUTH=1) for requests from this computer only.\n', flush=True)
    elif not auth.load_users():
        print('\n  NO LOGIN USER SET UP. Create one with:  python tools\\add_user.py\n', flush=True)
from starlette.middleware.base import BaseHTTPMiddleware

class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith('/ui') or request.url.path == '/' or request.url.path == '/login':
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

app.add_middleware(NoCacheStaticMiddleware)

from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse, JSONResponse


# Local development only: CASHFLOW_DISABLE_AUTH=1 skips the login for requests from this computer (127.0.0.1).
LOCAL_NO_LOGIN = os.getenv('CASHFLOW_DISABLE_AUTH', '').strip().lower() in ('1', 'true', 'yes')


class AuthMiddleware(BaseHTTPMiddleware):
    """No page or API call without a logged-in session (app/auth.py). Pages redirect to /login; API calls get 401."""
    async def dispatch(self, request, call_next):
        path = request.url.path
        if path in auth.PUBLIC_PATHS or request.method == 'OPTIONS':
            return await call_next(request)
        if LOCAL_NO_LOGIN and (request.client.host if request.client else '') in ('127.0.0.1', '::1'):
            request.state.user = 'local'
            return await call_next(request)
        user = auth.read_token(request.cookies.get(auth.COOKIE))
        if user:
            request.state.user = user
            return await call_next(request)
        if path.startswith('/api'):
            return JSONResponse({'detail': 'Not logged in'}, status_code=401)
        nxt = path + (('?' + request.url.query) if request.url.query else '')
        return RedirectResponse(url='/login' + (f'?next={nxt}' if path.startswith('/ui') and path != '/ui/' else ''),
                                status_code=303)

app.add_middleware(AuthMiddleware)

static_dir = Path(__file__).parent.parent / 'static'


# ------------------------------------------------------------------ login / logout / logo
@app.get('/login', include_in_schema=False)
def login_page(request: Request):
    if LOCAL_NO_LOGIN and (request.client.host if request.client else '') in ('127.0.0.1', '::1'):
        return RedirectResponse(url='/ui/', status_code=303)
    if auth.read_token(request.cookies.get(auth.COOKIE)):
        return RedirectResponse(url='/ui/', status_code=303)
    html = (static_dir / 'login.html').read_text(encoding='utf-8')
    if not auth.load_users():
        html = html.replace('<!--NO_USERS-->', '<p class="login-note">No user is set up yet. In the app folder run '
                                               '<code>python tools\\add_user.py</code>, then reload this page.</p>')
    credit = auth.background_credit()
    if credit:
        import html as _h
        text, url = _h.escape(credit[0]), _h.escape(credit[1], quote=True)
        html = html.replace('<!--BG_CREDIT-->', f'<a class="login-credit" href="{url}" target="_blank" rel="noopener">{text}</a>'
                            if url else f'<span class="login-credit">{text}</span>')
    return HTMLResponse(html)


@app.post('/api/auth/login', include_in_schema=False)
async def login(request: Request):
    ip = request.client.host if request.client else '?'
    if auth.too_many_fails(ip):
        return JSONResponse({'detail': 'Too many failed attempts. Wait 5 minutes and try again.'}, status_code=429)
    try:
        body = await request.json()
    except Exception:
        body = {}
    user = str(body.get('username') or '').strip().lower()
    if not user or not auth.check_password(user, str(body.get('password') or '')):
        auth.note_fail(ip)
        return JSONResponse({'detail': 'Wrong user name or password.'}, status_code=401)
    auth.clear_fails(ip)
    resp = JSONResponse({'ok': True, 'user': user, 'next': auth.safe_next(body.get('next'))})
    resp.set_cookie(auth.COOKIE, auth.make_token(user), max_age=auth.SESSION_SECONDS, httponly=True,
                    samesite='lax', secure=request.url.scheme == 'https', path='/')
    return resp


@app.post('/api/auth/logout', include_in_schema=False)
def logout_api():
    resp = JSONResponse({'ok': True})
    resp.delete_cookie(auth.COOKIE, path='/')
    return resp


@app.get('/logout', include_in_schema=False)
def logout_page():
    resp = RedirectResponse(url='/login', status_code=303)
    resp.delete_cookie(auth.COOKIE, path='/')
    return resp


@app.get('/api/auth/me', include_in_schema=False)
def me(request: Request):
    return {'user': getattr(request.state, 'user', None)}


@app.get('/brand/logo', include_in_schema=False)
def brand_logo():
    p = auth.logo_path()
    if not p:
        return JSONResponse({'detail': 'No image in the logo folder'}, status_code=404)
    return FileResponse(str(p), media_type=auth.LOGO_TYPES[p.suffix.lower()],
                        headers={'Cache-Control': 'no-cache'})


@app.get('/brand/background', include_in_schema=False)
def brand_background():
    p = auth.background_path()
    if not p:
        return JSONResponse({'detail': 'No image in the background folder'}, status_code=404)
    return FileResponse(str(p), media_type=auth.LOGO_TYPES[p.suffix.lower()],
                        headers={'Cache-Control': 'no-cache'})


# The dashboard page, with the login helper (logo + logout) added. index.html itself is not changed.
@app.get('/ui/', include_in_schema=False)
@app.get('/ui/index.html', include_in_schema=False)
def dashboard():
    html = (static_dir / 'index.html').read_text(encoding='utf-8')
    tag = '<script src="/ui/auth.js?v=1"></script>'
    if 'auth.js' not in html:
        html = html.replace('</body>', f'{tag}\n</body>') if '</body>' in html else html + tag
    ml_tag = '<script src="/ui/ml.js?v=1"></script>'
    if 'ml.js' not in html:
        html = html.replace('</body>', f'{ml_tag}\n</body>') if '</body>' in html else html + ml_tag
    return HTMLResponse(html)


if static_dir.exists():
    app.mount('/ui', StaticFiles(directory=str(static_dir), html=True), name='static')
app.include_router(router, prefix='/api')
from app.ml.api import router as ml_router
app.include_router(ml_router, prefix='/api/ml')

@app.get('/')
def root():
    return RedirectResponse(url='/ui/')
