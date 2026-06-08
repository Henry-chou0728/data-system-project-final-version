# Railway Deployment Guide

Railway does not run `docker-compose.yml` directly as one unit. Deploy this project as three Railway services:

- `frontend`: React build served by Nginx.
- `backend`: FastAPI API service.
- `MySQL`: Railway managed MySQL database.

## 1. Push the project to GitHub

Railway deploys GitHub repositories cleanly, especially for monorepos.

Commit and push the repository first.

## 2. Create a Railway project

1. Open Railway.
2. Create a new empty project.
3. Add a MySQL database service:
   - `+ New`
   - `Database`
   - `MySQL`

Railway will create database variables such as `MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, and `MYSQLDATABASE`.

## 3. Add the backend service

Create a new service from the same GitHub repo.

Backend service settings:

```text
Service name: backend
Root Directory: /dbms_final_backend
Dockerfile: Dockerfile
```

Backend variables:

```env
MYSQL_URL=${{MySQL.MYSQL_URL}}
PORT=8000
BIND_HOST=::
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
RUN_CREATE_TABLES=true
RUN_SEED=false
```

Do not set `RUN_SEED=true` for normal production deploys. The seed script clears existing data before inserting demo data.

The backend start script listens on Railway's `PORT` variable automatically.

## 4. Add the frontend service

Create another new service from the same GitHub repo.

Frontend service settings:

```text
Service name: frontend
Root Directory: /graduation-credit-verification-system
Dockerfile: Dockerfile
```

Frontend variables:

```env
PORT=80
BACKEND_HOST=backend.railway.internal
BACKEND_PORT=8000
```

The frontend Nginx config proxies `/api/*` to:

```text
http://${BACKEND_HOST}:8000/
```

If you rename the backend service in Railway, update `nginx.conf` accordingly.

## 5. Generate a public domain

Only generate a public domain for the `frontend` service:

```text
frontend -> Settings -> Networking -> Generate Domain
```

You normally do not need to expose `backend` publicly because the frontend proxies API requests internally.

## 6. Initialize demo data

After backend and MySQL are deployed, run the seed script once.

Option A: Railway shell / command

```bash
python seed.py
```

Option B: temporarily set backend variable:

```env
RUN_SEED=true
```

Deploy once, wait for seed to complete, then set it back:

```env
RUN_SEED=false
```

Demo accounts:

```text
111001001 / password123
111001002 / password123
111001003 / password123
111001004 / password123
```

## 7. Verify

Open the frontend Railway domain.

API health check through the frontend domain:

```text
https://YOUR_FRONTEND_DOMAIN/api/
```

Expected response:

```json
{"message":"Graduation Credit Verification System API is running"}
```

If the frontend loads but API calls fail, check:

- `backend` service name is exactly `backend`.
- `DATABASE_URL` references Railway MySQL variables correctly.
- Backend logs show `Database is ready.`
- Frontend has `PORT=80`.
