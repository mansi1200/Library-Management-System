# create_users.py
# Run this script to manually create the default users

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean

# Setup SQLite database
DATABASE_URL = "sqlite:///./library.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# User model
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    full_name = Column(String)
    is_admin = Column(Boolean, default=False)

# Create tables
Base.metadata.create_all(bind=engine)

# Create default users
def create_default_users():
    db = SessionLocal()
    try:
        # Clear existing users
        db.query(User).delete()
        db.commit()
        
        # Create admin user
        admin = User(
            username="admin",
            password="admin",
            full_name="Administrator",
            is_admin=True
        )
        db.add(admin)
        
        # Create regular user
        user = User(
            username="user",
            password="user",
            full_name="Regular User",
            is_admin=False
        )
        db.add(user)
        
        db.commit()
        
        print("Default users created successfully!")
        print("Admin: username='admin', password='admin'")
        print("User: username='user', password='user'")
        
        # Verify
        users = db.query(User).all()
        print("\nUsers in database:")
        for user in users:
            print(f"- {user.username} (Admin: {user.is_admin})")
            
    except Exception as e:
        print(f"Error creating users: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_default_users()