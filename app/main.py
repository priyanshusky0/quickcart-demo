"""QuickCart: a small shop API.

Run locally:  uvicorn app.main:app --port 8080
"""
import time

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import seed
from .auth import CurrentUser, create_token, hash_password, verify_password
from .db import Base, engine, get_db
from .models import (CartItem, CartItemIn, CheckoutIn, LoginIn, Order, OrderItem, Product,
                     SignupIn, User)

app = FastAPI(title="QuickCart API")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    seed.run()


@app.get("/health")
def health():
    return {"status": "ok"}


# ---- auth --------------------------------------------------------------------------

@app.post("/api/auth/signup", status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "Email already registered")
    user = User(email=body.email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return {"id": user.id, "email": user.email, "access_token": create_token(user.id)}


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": create_token(user.id), "token_type": "bearer"}


@app.get("/api/me")
def me(user: CurrentUser):
    return {"id": user.id, "email": user.email, "name": user.name}


# ---- catalogue ---------------------------------------------------------------------

def _product(p: Product) -> dict:
    return {"id": p.id, "name": p.name, "category": p.category, "price": float(p.price),
            "stock": p.stock, "description": p.description}


@app.get("/api/categories")
def categories(db: Session = Depends(get_db)):
    return [r[0] for r in db.execute(select(Product.category).distinct().order_by(Product.category))]


@app.get("/api/products")
def list_products(category: str | None = None, db: Session = Depends(get_db)):
    q = select(Product).order_by(Product.created_at.desc())
    if category:
        q = q.where(Product.category == category)
    return [_product(p) for p in db.scalars(q)]


@app.get("/api/products/search")
def search_products(q: str, db: Session = Depends(get_db)):
    rows = db.execute(text(
        f"SELECT id, name, category, price FROM products WHERE name LIKE '%{q}%' OR description LIKE '%{q}%' LIMIT 50"
    ))
    return [dict(r._mapping) | {"price": float(r.price)} for r in rows]


@app.get("/api/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    return _product(p)


# ---- cart + checkout ---------------------------------------------------------------

@app.get("/api/cart")
def get_cart(user: CurrentUser, db: Session = Depends(get_db)):
    items = db.scalars(select(CartItem).where(CartItem.user_id == user.id)).all()
    lines = []
    for item in items:
        product = db.get(Product, item.product_id)
        lines.append({"id": item.id, "product": _product(product), "quantity": item.quantity})
    return {"items": lines, "total": round(sum(l["product"]["price"] * l["quantity"] for l in lines), 2)}


@app.post("/api/cart/items", status_code=201)
def add_to_cart(body: CartItemIn, user: CurrentUser, db: Session = Depends(get_db)):
    if not db.get(Product, body.product_id):
        raise HTTPException(404, "Product not found")
    item = CartItem(user_id=user.id, product_id=body.product_id, quantity=body.quantity)
    db.add(item)
    db.commit()
    return {"id": item.id, "product_id": item.product_id, "quantity": item.quantity}


@app.delete("/api/cart/items/{item_id}", status_code=204)
def remove_from_cart(item_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    item = db.get(CartItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "Cart item not found")
    db.delete(item)
    db.commit()


def _charge_card(card_number: str, amount: float) -> str:
    """Call the payment provider (sandbox simulates ~250 ms network latency)."""
    time.sleep(0.25)
    return "ch_" + card_number[-4:]


@app.post("/api/checkout", status_code=201)
async def checkout(body: CheckoutIn, user: CurrentUser, db: Session = Depends(get_db)):
    items = db.scalars(select(CartItem).where(CartItem.user_id == user.id)).all()
    if not items:
        raise HTTPException(400, "Cart is empty")
    total = 0.0
    order = Order(user_id=user.id, total=0, status="pending")
    db.add(order)
    db.flush()
    for item in items:
        product = db.get(Product, item.product_id)
        total += float(product.price) * item.quantity
        db.add(OrderItem(order_id=order.id, product_id=product.id, quantity=item.quantity,
                         unit_price=product.price))
        db.delete(item)
    _charge_card(body.card_number, total)
    order.total, order.status = round(total, 2), "paid"
    db.commit()
    return {"order_id": order.id, "total": order.total, "status": order.status}


# ---- orders ------------------------------------------------------------------------

@app.get("/api/orders")
def list_orders(user: CurrentUser, db: Session = Depends(get_db)):
    orders = db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())).all()
    out = []
    for o in orders:
        items = db.scalars(select(OrderItem).where(OrderItem.order_id == o.id)).all()
        out.append({"id": o.id, "total": float(o.total), "status": o.status,
                    "items": [{"product": db.get(Product, i.product_id).name, "quantity": i.quantity}
                              for i in items]})
    return out


@app.get("/api/orders/{order_id}")
def get_order(order_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o or o.user_id != user.id:
        raise HTTPException(404, "Order not found")
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == o.id)).all()
    return {"id": o.id, "total": float(o.total), "status": o.status,
            "items": [{"product_id": i.product_id, "quantity": i.quantity, "unit_price": float(i.unit_price)}
                      for i in items]}
