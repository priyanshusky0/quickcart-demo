"""Seed a realistic amount of data on first start.

Load-test accounts: loadtest1@quickcart.dev … loadtest200@quickcart.dev,
password "loadtest-pass".
"""
import os
import random

from sqlalchemy import func, insert, select

from .auth import hash_password
from .db import SessionLocal
from .models import Order, OrderItem, Product, User

N_PRODUCTS = int(os.getenv("SEED_PRODUCTS", "20000"))
N_USERS = int(os.getenv("SEED_USERS", "200"))
CATEGORIES = ["books", "electronics", "kitchen", "garden", "toys", "sports", "beauty", "grocery",
              "office", "music", "games", "outdoor"]
ADJ = ["Classic", "Smart", "Compact", "Deluxe", "Eco", "Pro", "Mini", "Ultra", "Vintage", "Portable"]
NOUN = ["Lamp", "Kettle", "Notebook", "Speaker", "Backpack", "Chair", "Headphones", "Mug", "Drone",
        "Blender", "Jacket", "Puzzle", "Camera", "Watch", "Planter"]


def run() -> None:
    rnd = random.Random(42)
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Product)):
            return
        db.execute(insert(Product), [{
            "name": f"{rnd.choice(ADJ)} {rnd.choice(NOUN)} {i}",
            "category": rnd.choice(CATEGORIES),
            "description": f"A {rnd.choice(ADJ).lower()} {rnd.choice(NOUN).lower()} for everyday use. SKU {i:06d}.",
            "price": round(rnd.uniform(3, 400), 2), "stock": rnd.randint(0, 500),
        } for i in range(1, N_PRODUCTS + 1)])
        pw = hash_password("loadtest-pass")      # one hash for all seed users keeps seeding fast
        db.execute(insert(User), [{"email": f"loadtest{i}@quickcart.dev", "name": f"Load Test {i}",
                                   "password_hash": pw} for i in range(1, N_USERS + 1)])
        db.commit()
        user_ids = list(db.scalars(select(User.id)))
        for uid in user_ids:
            for _ in range(rnd.randint(3, 8)):
                order = Order(user_id=uid, total=0, status="paid")
                db.add(order)
                db.flush()
                total = 0.0
                for _ in range(rnd.randint(1, 4)):
                    pid, qty, price = rnd.randint(1, N_PRODUCTS), rnd.randint(1, 3), round(rnd.uniform(3, 400), 2)
                    db.add(OrderItem(order_id=order.id, product_id=pid, quantity=qty, unit_price=price))
                    total += qty * price
                order.total = round(total, 2)
        db.commit()
