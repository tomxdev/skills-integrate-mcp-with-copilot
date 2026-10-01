"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

SESSION_DURATION_SECONDS = 8 * 60 * 60
teacher_sessions = {}


class TeacherLogin(BaseModel):
    username: str
    password: str


def load_teacher_credentials():
    credentials_path = Path(os.environ.get(
        "TEACHER_CREDENTIALS_FILE", current_dir / "teachers.json"
    ))
    try:
        with credentials_path.open(encoding="utf-8") as credentials_file:
            data = json.load(credentials_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Teacher credentials are unavailable or invalid") from error

    teachers = data.get("teachers") if isinstance(data, dict) else None
    if not isinstance(teachers, list):
        raise ValueError("Teacher credentials must contain a teachers list")

    credentials = {}
    for teacher in teachers:
        if not isinstance(teacher, dict):
            raise ValueError("Invalid teacher credential entry")
        username = teacher.get("username")
        password_hash = teacher.get("password_hash")
        if not isinstance(username, str) or not username or not isinstance(password_hash, str):
            raise ValueError("Invalid teacher credential entry")
        credentials[username] = password_hash
    return credentials


def verify_password(password, encoded_hash):
    try:
        algorithm, iterations, salt, expected_hash = encoded_hash.split("$", 3)
        iterations = int(iterations)
        salt_bytes = bytes.fromhex(salt)
        expected_bytes = bytes.fromhex(expected_hash)
    except (ValueError, TypeError):
        return False

    if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 2_000_000:
        return False
    actual_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt_bytes, iterations
    )
    return hmac.compare_digest(actual_hash, expected_bytes)


def require_teacher(authorization: str | None = Header(default=None)):
    scheme, separator, token = (authorization or "").partition(" ")
    session = teacher_sessions.get(token) if separator and scheme.lower() == "bearer" else None
    if session is None or session[1] <= time.time():
        if token:
            teacher_sessions.pop(token, None)
        raise HTTPException(
            status_code=401,
            detail="Teacher login required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session[0]


@app.post("/auth/login")
def teacher_login(credentials: TeacherLogin):
    try:
        teacher_hash = load_teacher_credentials().get(credentials.username)
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    if teacher_hash is None or not verify_password(credentials.password, teacher_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    now = time.time()
    teacher_sessions.update({
        token: session
        for token, session in teacher_sessions.items()
        if session[1] > now
    })
    token = secrets.token_urlsafe(32)
    teacher_sessions[token] = (credentials.username, now + SESSION_DURATION_SECONDS)
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": credentials.username,
        "expires_in": SESSION_DURATION_SECONDS,
    }


@app.post("/auth/logout")
def teacher_logout(
    authorization: str | None = Header(default=None),
    teacher: str = Depends(require_teacher),
):
    _, _, token = (authorization or "").partition(" ")
    teacher_sessions.pop(token, None)
    return {"message": "Logged out"}

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, teacher: str = Depends(require_teacher)):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, teacher: str = Depends(require_teacher)):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
