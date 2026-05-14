from app.database import SessionLocal
from app.seed import init_db

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        from app.models import User

        for u in db.query(User).order_by(User.id):
            print(f"{u.username}\t{u.full_name}\t{u.role.value}")
    finally:
        db.close()
