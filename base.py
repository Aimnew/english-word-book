from fastapi import FastAPI, HTTPException, Depends, Form, Response, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBearer, OAuth2PasswordBearer
from pydantic import BaseModel
from typing import List, Optional
from generate_words import get_random_words, initialize_database as initialize_words_database
from gtts import gTTS
import uvicorn
import signal
import sys
import sqlite3
from datetime import datetime, timedelta
from jose import JWTError, jwt

app = FastAPI()

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Настройки для JWT
SECRET_KEY = "your-secret-key"  # Замените на свой секретный ключ
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Модели данных
class Word(BaseModel):
    word: str
    category: str
    image_path: str
    audio_path: str

class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    age: Optional[int] = None
    image_path: Optional[str] = None

class ExamResult(BaseModel):
    username: str
    score: int
    total: int
    timestamp: str

# Предопределенные пользователи
predefined_users = {
    f"test{i}": User(username=f"test{i}", full_name=f"Test User {i}")
    for i in range(1, 11)
}

def get_user(username: str):
    return predefined_users.get(username)

# Функции для работы с базой данных экзаменов
def save_exam_result(username: str, score: int, total: int):
    conn = sqlite3.connect('exam_results.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_results
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         username TEXT,
         score INTEGER,
         total INTEGER,
         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
    ''')
    cursor.execute("INSERT INTO exam_results (username, score, total) VALUES (?, ?, ?)",
                   (username, score, total))
    conn.commit()
    print(f"Exam result saved for user {username}: score {score}/{total}")
    conn.close()

def get_exam_results():
    conn = sqlite3.connect('exam_results.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username, MAX(score) as best_score, total, MAX(timestamp) as latest_timestamp FROM exam_results GROUP BY username ORDER BY best_score DESC")
    results = cursor.fetchall()
    conn.close()
    print("Fetched exam results:", results)
    return [ExamResult(username=r[0], score=r[1], total=r[2], timestamp=r[3]) for r in results]

# Вспомогательные функции
def generate_audio(word):
    tts = gTTS(text=word, lang='en')
    audio_path = f"static/audio/{word}.mp3"
    tts.save(audio_path)
    return f"/static/audio/{word}.mp3"

def check_exam_results_db():
    conn = sqlite3.connect('exam_results.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exam_results")
    results = cursor.fetchall()
    conn.close()
    print("Current exam results in database:", results)

def signal_handler(sig, frame):
    print('\nShutting down the server...')
    sys.exit(0)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = get_user(username)
        if user is None:
            raise credentials_exception
        print(f"Authenticated user: {username}")
        return user
    except JWTError as e:
        print(f"JWT Error: {str(e)}")
        raise credentials_exception

# Роуты
@app.get("/")
async def root():
    response = FileResponse("static/login.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    print(f"Login attempt: username={username}, password={password}")
    user = get_user(username)
    if user and username == password:
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": username}, expires_delta=access_token_expires
        )
        print(f"Login successful for user: {username}")
        print(f"Generated access token: {access_token}")
        return {"access_token": access_token, "token_type": "bearer"}
    print(f"Login failed for user: {username}")
    raise HTTPException(status_code=400, detail="Incorrect username or password")

@app.get("/index")
async def index():
    response = FileResponse("static/index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/user_info")
async def user_info(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    token = authorization.split()[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = get_user(username)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return {
            "username": user.username,
            "full_name": user.full_name,
            "image_path": user.image_path or "/static/images/default_avatar.jpg"
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/words", response_model=List[Word])
async def get_words(current_user: User = Depends(get_current_user)):
    words = get_random_words()
    print(f"Retrieved words for user {current_user.username}: {words}")
    word_objects = []
    for word in words:
        audio_path = generate_audio(word['word'])
        word_objects.append(Word(word=word['word'], category=word['category'], 
                                 image_path=word['image_path'], audio_path=audio_path))
    return word_objects

@app.post("/exam")
async def take_exam(answers: List[str], current_user: User = Depends(get_current_user)):
    words = get_random_words()
    correct_answers = sum(1 for answer, word in zip(answers, words) if answer.lower() == word['word'].lower())
    total = len(words)
    save_exam_result(current_user.username, correct_answers, total)
    return {"score": correct_answers, "total": total}

@app.get("/exam_results", response_model=List[ExamResult])
async def exam_results(current_user: User = Depends(get_current_user)):
    return get_exam_results()

if __name__ == "__main__":
    initialize_words_database()
    check_exam_results_db()
    signal.signal(signal.SIGINT, signal_handler)
    uvicorn.run(app, host="0.0.0.0", port=8000)