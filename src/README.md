# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Sign up for activities

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application:

   ```
   python app.py
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/auth/login`                                                     | Log in as a teacher and receive a bearer token                      |
| POST   | `/auth/logout`                                                    | Revoke the current teacher session                                  |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Teacher-only: sign up a student for an activity                     |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Teacher-only: unregister a student                              |

## Teacher Accounts

Copy `src/teachers.example.json` to `src/teachers.json` and replace the example username and hash. The real credentials file is ignored by Git. Password hashes use PBKDF2-HMAC-SHA256 with 310,000 iterations; generate one with:

```sh
python3 -c 'import hashlib,secrets; p=input("Teacher password: ").encode(); s=secrets.token_bytes(16); print("pbkdf2_sha256$310000$" + s.hex() + "$" + hashlib.pbkdf2_hmac("sha256", p, s, 310000).hex())'
```

The file format is:

```json
{
   "teachers": [
      {
         "username": "teacher1",
         "password_hash": "pbkdf2_sha256$310000$<salt-hex>$<hash-hex>"
      }
   ]
}
```

You can set `TEACHER_CREDENTIALS_FILE` to use a credentials file outside `src/`. Teacher sessions expire after eight hours or when the teacher logs out. Activity lists and participant rosters remain publicly viewable; signup and unregister requests require a teacher bearer token.

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.
