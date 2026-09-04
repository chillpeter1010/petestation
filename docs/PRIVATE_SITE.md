# Petehub private site

Petehub now requires an approved local account for every application page and data API. Passwords are stored as salted scrypt hashes in the ignored runtime database `data/auth/petehub_auth.sqlite3`; the browser receives only an HttpOnly session cookie.

## Account flow

1. A visitor opens `/register` and requests an account.
2. The account remains `pending` and cannot sign in.
3. An administrator opens `/admin/accounts` and approves or disables the account.
4. Disabling an account immediately revokes all of its sessions.

Create or reset an administrator without writing a plaintext password to source control:

```powershell
cd C:\intern\project_transfer\backend
python scripts\bootstrap_admin.py <username>
```

## Local and temporary remote access

Build the Nuxt production server while a development server is running:

```powershell
cd C:\intern\project_transfer\frontend
$env:NUXT_IGNORE_LOCK = "1"
$env:NUXT_BUILD_DIR = ".nuxt-build"
npm run build
```

Start or reuse FastAPI and Nuxt, then create an HTTPS tunnel through localhost.run using Windows' built-in SSH client:

```powershell
cd C:\intern\project_transfer
.\start-private-site.ps1
```

The current URL is printed by the script and recorded in `.logs/private-site-url.txt`. The anonymous tunnel URL is temporary and can change after a tunnel restart. The computer must remain powered on and signed in. Opening an existing `127.0.0.1` tab does not rewrite its address; copy the recorded HTTPS URL into the browser.

Install automatic startup after Windows sign-in:

```powershell
.\install-private-site-startup.ps1
```

## Permanent hostname

A stable hostname requires a domain and a managed tunnel provider account, such as a Cloudflare account with a named tunnel. After those are available, replace the anonymous SSH tunnel with the provider's authenticated connector and set `AUTH_COOKIE_SECURE=true` in `backend/.env`. Keep the public hostname pointed only at Nuxt; Nuxt proxies `/api` to FastAPI over localhost.

Do not expose ports 3000 or 8000 directly through the router. For defense in depth, put Cloudflare Access in front of the hostname and restrict it to approved email addresses in addition to Petehub's own login.
