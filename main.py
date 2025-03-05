# app.py
from fastapi import FastAPI, Depends, HTTPException, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from datetime import datetime, timedelta
from typing import Optional
import os
import sqlite3
import secrets
from pydantic import BaseModel
import uvicorn

# Setup FastAPI app
app = FastAPI(title="Library Management System")
security = HTTPBasic()
templates = Jinja2Templates(directory="templates")
# app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup SQLite database
DATABASE_URL = "sqlite:///./library.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    full_name = Column(String)
    is_admin = Column(Boolean, default=False)
    
class Membership(Base):
    __tablename__ = "memberships"
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    contact_name = Column(String)
    contact_address = Column(String)
    aadhar_card = Column(String, unique=True)
    start_date = Column(Date)
    end_date = Column(Date)
    membership_type = Column(String)  # 6 months, 1 year, 2 years
    
class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    author = Column(String)
    is_movie = Column(Boolean, default=False)
    genre = Column(String)
    serial_number = Column(String, unique=True)
    status = Column(String, default="Available")  # Available, Issued
    
class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"))
    member_id = Column(Integer, ForeignKey("memberships.id"))
    issue_date = Column(Date)
    return_date = Column(Date)
    actual_return_date = Column(Date, nullable=True)
    fine_amount = Column(Float, default=0.0)
    fine_paid = Column(Boolean, default=False)
    remarks = Column(String, nullable=True)
    
    book = relationship("Book")
    member = relationship("Membership")

# Create all tables
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication
def get_current_user(credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or user.password != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("start.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # Print to console for debugging
    print(f"Login attempt: username={username}, password={password}")
    
    user = db.query(User).filter(User.username == username).first()
    
    # Debug: Check if user exists
    if user:
        print(f"User found: {user.username}, is_admin: {user.is_admin}")
        print(f"Stored password: {user.password}")
    else:
        print("User not found in database")
    
    if not user or user.password != password:
        return templates.TemplateResponse(
            "login.html", 
            {"request": request, "error": "Invalid username or password"}
        )
    
    # In a real app, you'd use sessions, but for simplicity, we'll use basic auth
    return RedirectResponse(url="/book-categories", status_code=303)


@app.get("/book-categories", response_class=HTMLResponse)
async def book_categories(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("book_categories.html", {"request": request, "is_admin": user.is_admin})

@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance_menu(request: Request, user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return templates.TemplateResponse("maintenance_menu.html", {"request": request})

@app.get("/reports", response_class=HTMLResponse)
async def reports_menu(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("reports_menu.html", {"request": request})

@app.get("/transactions", response_class=HTMLResponse)
async def transactions_menu(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("transactions_menu.html", {"request": request})

# Maintenance routes (admin only)
@app.get("/maintenance/manage", response_class=HTMLResponse)
async def maintenance_manage(request: Request, user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return templates.TemplateResponse("maintenance_manage.html", {"request": request})

@app.get("/maintenance/memberships", response_class=HTMLResponse)
async def memberships_list(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    memberships = db.query(Membership).all()
    return templates.TemplateResponse("memberships.html", {"request": request, "memberships": memberships})

@app.get("/maintenance/add-membership", response_class=HTMLResponse)
async def add_membership_form(request: Request, user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return templates.TemplateResponse("add_membership.html", {"request": request})

@app.post("/maintenance/add-membership")
async def add_membership(
    first_name: str = Form(...),
    last_name: str = Form(...),
    contact_name: str = Form(...),
    contact_address: str = Form(...),
    aadhar_card: str = Form(...),
    membership_type: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    start_date = datetime.now().date()
    
    if membership_type == "6 months":
        end_date = start_date + timedelta(days=180)
    elif membership_type == "1 year":
        end_date = start_date + timedelta(days=365)
    elif membership_type == "2 years":
        end_date = start_date + timedelta(days=730)
    
    membership = Membership(
        first_name=first_name,
        last_name=last_name,
        contact_name=contact_name,
        contact_address=contact_address,
        aadhar_card=aadhar_card,
        start_date=start_date,
        end_date=end_date,
        membership_type=membership_type
    )
    
    db.add(membership)
    db.commit()
    
    return RedirectResponse(url="/reports/master-memberships", status_code=303)

@app.get("/maintenance/update-membership/{membership_id}", response_class=HTMLResponse)
async def update_membership_form(membership_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    membership = db.query(Membership).filter(Membership.id == membership_id).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    
    return templates.TemplateResponse("update_membership.html", {"request": request, "membership": membership})

@app.post("/maintenance/update-membership/{membership_id}")
async def update_membership(
    membership_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    contact_name: str = Form(...),
    contact_address: str = Form(...),
    membership_type: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    membership = db.query(Membership).filter(Membership.id == membership_id).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    
    membership.first_name = first_name
    membership.last_name = last_name
    membership.contact_name = contact_name
    membership.contact_address = contact_address
    
    # Update membership duration
    if membership_type == "6 months":
        membership.end_date = membership.start_date + timedelta(days=180)
    elif membership_type == "1 year":
        membership.end_date = membership.start_date + timedelta(days=365)
    elif membership_type == "2 years":
        membership.end_date = membership.start_date + timedelta(days=730)
    
    membership.membership_type = membership_type
    
    db.commit()
    
    return RedirectResponse(url="/reports/master-memberships", status_code=303)

@app.get("/maintenance/books", response_class=HTMLResponse)
async def books_list(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    books = db.query(Book).all()
    return templates.TemplateResponse("books.html", {"request": request, "books": books})

@app.get("/maintenance/add-book", response_class=HTMLResponse)
async def add_book_form(request: Request, user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return templates.TemplateResponse("add_book.html", {"request": request})

@app.post("/maintenance/add-book")
async def add_book(
    title: str = Form(...),
    author: str = Form(...),
    is_movie: bool = Form(False),
    genre: str = Form(...),
    serial_number: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    book = Book(
        title=title,
        author=author,
        is_movie=is_movie,
        genre=genre,
        serial_number=serial_number
    )
    
    db.add(book)
    db.commit()
    
    if is_movie:
        return RedirectResponse(url="/reports/master-movies", status_code=303)
    else:
        return RedirectResponse(url="/reports/master-books", status_code=303)

@app.get("/maintenance/update-book/{book_id}", response_class=HTMLResponse)
async def update_book_form(book_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book/Movie not found")
    
    return templates.TemplateResponse("update_book.html", {"request": request, "book": book})

@app.post("/maintenance/update-book/{book_id}")
async def update_book(
    book_id: int,
    title: str = Form(...),
    author: str = Form(...),
    is_movie: bool = Form(False),
    genre: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book/Movie not found")
    
    book.title = title
    book.author = author
    book.is_movie = is_movie
    book.genre = genre
    
    db.commit()
    
    if is_movie:
        return RedirectResponse(url="/reports/master-movies", status_code=303)
    else:
        return RedirectResponse(url="/reports/master-books", status_code=303)

@app.get("/maintenance/users", response_class=HTMLResponse)
async def users_list(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    users = db.query(User).all()
    return templates.TemplateResponse("users.html", {"request": request, "users": users})

@app.get("/maintenance/add-user", response_class=HTMLResponse)
async def add_user_form(request: Request, user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return templates.TemplateResponse("add_user.html", {"request": request})

@app.post("/maintenance/add-user")
async def add_user(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    is_admin: bool = Form(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    new_user = User(
        username=username,
        password=password,
        full_name=full_name,
        is_admin=is_admin
    )
    
    db.add(new_user)
    db.commit()
    
    return RedirectResponse(url="/reports/pending-issues", status_code=303)

@app.get("/maintenance/update-user/{user_id}", response_class=HTMLResponse)
async def update_user_form(user_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    user_to_update = db.query(User).filter(User.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found")
    
    return templates.TemplateResponse("update_user.html", {"request": request, "user_to_update": user_to_update})

@app.post("/maintenance/update-user/{user_id}")
async def update_user(
    user_id: int,
    username: str = Form(...),
    full_name: str = Form(...),
    is_admin: bool = Form(False),
    password: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    user_to_update = db.query(User).filter(User.id == user_id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_to_update.username = username
    user_to_update.full_name = full_name
    user_to_update.is_admin = is_admin
    
    if password:
        user_to_update.password = password
    
    db.commit()
    
    return RedirectResponse(url="/maintenance/users", status_code=303)

# Reports routes (both user and admin)
@app.get("/reports/active-issues", response_class=HTMLResponse)
async def active_issues(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = datetime.now().date()
    active = db.query(Transaction).filter(Transaction.actual_return_date == None).all()
    return templates.TemplateResponse("active_issues.html", {"request": request, "transactions": active, "today": today})

@app.get("/reports/master-memberships", response_class=HTMLResponse)
async def master_memberships(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = db.query(Membership).all()
    return templates.TemplateResponse("master_memberships.html", {"request": request, "memberships": memberships, "user": user})

@app.get("/reports/master-movies", response_class=HTMLResponse)
async def master_movies(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    movies = db.query(Book).filter(Book.is_movie == True).all()
    return templates.TemplateResponse("master_movies.html", {"request": request, "movies": movies, "user": user})

@app.get("/reports/master-books", response_class=HTMLResponse)
async def master_books(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    books = db.query(Book).filter(Book.is_movie == False).all()
    return templates.TemplateResponse("master_books.html", {"request": request, "books": books, "user": user})

@app.get("/reports/overdue", response_class=HTMLResponse)
async def overdue_returns(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = datetime.now().date()
    overdue = db.query(Transaction).filter(Transaction.return_date < today, Transaction.actual_return_date == None).all()
    return templates.TemplateResponse("overdue.html", {"request": request, "transactions": overdue, "today": today})

@app.get("/reports/pending-issues", response_class=HTMLResponse)
async def pending_issues(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # This would typically be a separate table for issue requests pending approval
    # For simplicity, we'll simulate this with a dummy data approach
    return templates.TemplateResponse("pending_issues.html", {"request": request, "pending_requests": []})

# Transactions routes (both user and admin)
@app.get("/transactions/check-availability", response_class=HTMLResponse)
async def check_availability_form(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("check_availability.html", {"request": request})

@app.post("/transactions/check-availability")
async def check_availability(
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not title and not author:
        return RedirectResponse(url="/transactions/check-availability?error=Please provide either title or author", status_code=303)
    
    query = db.query(Book)
    
    if title:
        query = query.filter(Book.title.like(f"%{title}%"))
    
    if author:
        query = query.filter(Book.author.like(f"%{author}%"))
    
    books = query.all()
    
    return templates.TemplateResponse(
        "availability_results.html", 
        {"request": Request, "books": books}
    )

@app.get("/transactions/issue-book", response_class=HTMLResponse)
async def issue_book_form(request: Request, user: User = Depends(get_current_user), book_id: Optional[int] = None, db: Session = Depends(get_db)):
    book = None
    if book_id:
        book = db.query(Book).filter(Book.id == book_id).first()
    
    memberships = db.query(Membership).all()
    today_date = datetime.now().date()
    max_return_date = today_date + timedelta(days=15)
    
    return templates.TemplateResponse("issue_book.html", {
        "request": request, 
        "book": book, 
        "memberships": memberships, 
        "today_date": today_date.strftime("%Y-%m-%d"),
        "max_return_date": max_return_date.strftime("%Y-%m-%d")
    })

@app.post("/transactions/issue-book")
async def issue_book(
    book_id: int = Form(...),
    member_id: int = Form(...),
    issue_date: str = Form(...),  # Format: YYYY-MM-DD
    return_date: str = Form(...),  # Format: YYYY-MM-DD
    remarks: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    book = db.query(Book).filter(Book.id == book_id).first()
    
    if not book or book.status != "Available":
        return RedirectResponse(url="/transactions/issue-book?error=Book not available", status_code=303)
    
    # Validate dates
    issue_date_obj = datetime.strptime(issue_date, "%Y-%m-%d").date()
    return_date_obj = datetime.strptime(return_date, "%Y-%m-%d").date()
    today = datetime.now().date()
    max_return_date = issue_date_obj + timedelta(days=15)
    
    if issue_date_obj < today:
        return RedirectResponse(url="/transactions/issue-book?error=Issue date cannot be in the past", status_code=303)
    
    if return_date_obj > max_return_date:
        return RedirectResponse(url="/transactions/issue-book?error=Return date cannot be more than 15 days from issue date", status_code=303)
    
    # Update book status
    book.status = "Issued"
    
    # Create transaction
    transaction = Transaction(
        book_id=book_id,
        member_id=member_id,
        issue_date=issue_date_obj,
        return_date=return_date_obj,
        remarks=remarks
    )
    
    db.add(transaction)
    db.commit()
    
    return RedirectResponse(url="/reports/active-issues", status_code=303)

@app.get("/transactions/return-book", response_class=HTMLResponse)
async def return_book_form(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    active_transactions = db.query(Transaction).filter(Transaction.actual_return_date == None).all()
    today_date = datetime.now().date().strftime("%Y-%m-%d")
    return templates.TemplateResponse("return_book.html", {"request": request, "transactions": active_transactions, "today_date": today_date})

@app.post("/transactions/return-book")
async def return_book(
    transaction_id: int = Form(...),
    actual_return_date: str = Form(...),  # Format: YYYY-MM-DD
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    if not transaction:
        return RedirectResponse(url="/transactions/return-book?error=Transaction not found", status_code=303)
    
    # Calculate fine if any (Rs. 10 per day)
    return_date = transaction.return_date
    actual_date = datetime.strptime(actual_return_date, "%Y-%m-%d").date()
    
    if actual_date > return_date:
        days_late = (actual_date - return_date).days
        fine = days_late * 10.0  # Rs. 10 per day
        transaction.fine_amount = fine
    
    transaction.actual_return_date = actual_date
    
    # If there's a fine, redirect to fine payment
    if transaction.fine_amount > 0:
        db.commit()
        return RedirectResponse(url=f"/transactions/pay-fine/{transaction.id}", status_code=303)
    
    # Update book status
    book = db.query(Book).filter(Book.id == transaction.book_id).first()
    book.status = "Available"
    
    db.commit()
    
    return RedirectResponse(url="/reports/active-issues", status_code=303)

@app.get("/transactions/pay-fine/{transaction_id}", response_class=HTMLResponse)
async def pay_fine_form(request: Request, transaction_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    if not transaction:
        return RedirectResponse(url="/transactions/return-book?error=Transaction not found", status_code=303)
    
    return templates.TemplateResponse("pay_fine.html", {"request": request, "transaction": transaction})

@app.post("/transactions/pay-fine/{transaction_id}")
async def pay_fine(
    transaction_id: int,
    fine_paid: bool = Form(False),
    remarks: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    if not transaction:
        return RedirectResponse(url="/transactions/return-book?error=Transaction not found", status_code=303)
    
    transaction.fine_paid = fine_paid
    
    if remarks:
        transaction.remarks = remarks
    
    # Update book status only if fine is paid or there is no fine
    if fine_paid or transaction.fine_amount == 0:
        book = db.query(Book).filter(Book.id == transaction.book_id).first()
        book.status = "Available"
    
    db.commit()
    
    return RedirectResponse(url="/reports/active-issues", status_code=303)

# Initialize database with admin user if it doesn't exist
def init_db():
    print("Initializing database...")
    db = SessionLocal()
    try:
        # Check if admin exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            print("Creating admin user")
            admin = User(
                username="admin",
                password="admin",
                full_name="Administrator",
                is_admin=True
            )
            db.add(admin)
            db.commit()
        else:
            print("Admin user already exists")
            
        # Check if regular user exists
        regular_user = db.query(User).filter(User.username == "user").first()
        if not regular_user:
            print("Creating regular user")
            regular_user = User(
                username="user",
                password="user",
                full_name="Regular User",
                is_admin=False
            )
            db.add(regular_user)
            db.commit()
        else:
            print("Regular user already exists")
            
        # Print all users for verification
        users = db.query(User).all()
        print("All users in database:")
        for user in users:
            print(f"- {user.username} (Admin: {user.is_admin})")
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        db.close()

# Run the app
if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)