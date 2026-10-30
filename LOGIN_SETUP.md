# Login (fix 25, 3 Oct 2026)

The app now needs a login. Without one, every page goes to the login screen and every API call is refused.

## First-time setup (once per install)
In the app folder (venv active):
```
python tools\add_user.py
```
Type a user name and a password (at least 6 characters, typed twice). Repeat for each person who needs access.
Restart the app (Ctrl+C, then start it again), open http://localhost:8000/ui and sign in.

| Task | Command |
|---|---|
| Add a user / change a password | `python tools\add_user.py` |
| List users | `python tools\add_user.py --list` |
| Remove a user | `python tools\add_user.py --remove NAME` |
| Log everybody out | delete `data\.session_secret` and restart |

## How it works
* Users are stored in `data\users.json` as salted password hashes (PBKDF2-SHA256), never the password itself.
* After login the browser keeps a signed session cookie for 12 hours; then the login screen appears again.
* 5 wrong passwords from one computer in 5 minutes → that computer waits 5 minutes.
* **Logout** is at the top right of the dashboard, next to the signed-in user name.
* The signing key is `APP_SECRET_KEY` in `.env` if set, otherwise a random key in `data\.session_secret` (created automatically).
* Keep `data\users.json` and `data\.session_secret` out of zips and e-mails, like `.env`.

## Logo
The login page and the top-left of the dashboard show the image in the **`logo`** folder of the project
(a file with "logo" in its name first; .svg, .png, .jpg, .webp). To change it, put the new image in `logo\`
and remove the old one — no restart needed. If the folder is empty, the old "CF" box is shown.
Now: `logo\cashflow-logo.svg`.

## Login-page picture
The left half of the login card shows the picture in the **`background`** folder (a file with "background" in its
name first; .svg, .png, .jpg, .webp). Now: `background\login-background.svg`, a light-blue cash-flow illustration
made for this app (no licence needed). To use another picture, put it in `background\` and remove the old one.
A portrait picture (about 600 × 720 or larger) fits best; it is cropped to fill the panel.

**Pictures that need a credit** (e.g. a free image from Magnific, formerly Freepik, whose free licence requires
"Designed by Magnific" with a link): create `background\credit.txt` with two lines:
```
Designed by Magnific
https://www.magnific.com
```
The credit then appears in the corner of the picture. With a paid Magnific licence no credit is needed.

## Files
`app/auth.py` (new) · `app/main.py` · `static/login.html`, `static/login.css`, `static/auth.js` (new) ·
`logo/cashflow-logo.svg` (new) · `background/login-background.svg` (new) · `tools/add_user.py` (new) · `tests/test_auth.py` (new).
`index.html`, `app.js` and `style.css` are **not** changed: the server adds `auth.js` to the dashboard page, which swaps
in the logo and adds the user name and Logout button. So this fix applies to any install from fix 22 on, with or
without the Refresh & Compare feature (fix 23).
