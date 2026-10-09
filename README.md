# QuickCart API

Small e-commerce backend: catalogue, search, cart, checkout and order history.

```bash
docker compose up --build        # http://localhost:8080/docs
```

Or without Docker (SQLite):

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8080
```

Seeded test accounts: `loadtest1@quickcart.dev` … `loadtest200@quickcart.dev`, password `loadtest-pass`.

| Endpoint | Description |
|---|---|
| `POST /api/auth/signup`, `POST /api/auth/login` | JSON `{email, password}` → `access_token` |
| `GET /api/products?category=` | Product listing |
| `GET /api/products/search?q=` | Full-text search |
| `GET /api/products/{id}`, `GET /api/categories` | Catalogue |
| `GET /api/cart`, `POST /api/cart/items`, `DELETE /api/cart/items/{id}` | Cart |
| `POST /api/checkout` | Pay for the cart |
| `GET /api/orders`, `GET /api/orders/{id}` | Order history |
