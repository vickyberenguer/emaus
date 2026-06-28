# Emaús — Sistema de Relevamiento

## Stack
- **Frontend:** HTML + JS estático → Netlify (`emaus.netlify.app`)
- **Backend:** FastAPI + Mangum → AWS Lambda
- **Base de datos:** TiDB Cloud Starter (MySQL-compatible)

## Setup local

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configurar variables de entorno
cp ../.env.example .env
# Completar .env con credenciales de TiDB y JWT secret

# Correr localmente
uvicorn app.main:app --reload
```

### 2. Base de datos

Ejecutar las migraciones en orden desde DBeaver o el cliente de TiDB:

```
migrations/001_tablas_base.sql
```

### 3. Frontend

Abrir `frontend/index.html` directamente en el navegador, o usar un servidor local:

```bash
cd frontend
python -m http.server 3000
```

## Variables de entorno

Ver `.env.example` para la lista completa.  
**Nunca commitear el archivo `.env`.**

### En producción (Lambda)
Configurar en AWS Lambda → Configuration → Environment variables.

### En Netlify
Configurar `ENV_API_URL` en Netlify → Site settings → Environment variables con la URL del API Gateway.

## Deploy

### Backend → Lambda
```bash
cd backend
pip install -r requirements.txt -t package/
cp -r app package/
cp lambda_handler.py package/
cd package && zip -r ../package.zip .
# Subir package.zip a Lambda
```

### Frontend → Netlify
Push a `main` → Netlify despliega automáticamente.
