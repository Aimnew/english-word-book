import random
import sqlite3
import os
import requests

# Список простых английских слов по категориям
simple_words = {
    "animals": ["cat", "dog", "fish", "duck", "goat", "cow", "horse"],
    "food": ["soup", "milk", "juice", "bread", "cheese", "cake", "honey"],
    "family": ["mom", "dad", "brother", "uncle", "aunt", "grandma", "grandpa"],
    "body parts": ["eye", "nose", "mouth", "ear", "hand", "leg", "head"],
    "nature": ["forest", "river", "mountain", "field", "sky", "snow", "rain"],
    "objects": ["table", "chair", "house", "ball", "window", "door", "book"],
    "colors": ["blue", "red", "white", "black", "yellow", "green", "pink"],
    "actions": ["eat", "drink", "sleep", "walk", "run", "sing", "wash"]
}

def generate_image(word, category):
    image_url = f"https://via.placeholder.com/200x200.png?text={word}"
    image_path = f"static/images/{word}.jpg"
    
    try:
        response = requests.get(image_url)
        response.raise_for_status()  # Вызовет исключние для неуспешных запросов
        with open(image_path, 'wb') as file:
            file.write(response.content)
        print(f"Image successfully saved for '{word}' at {image_path}")
        return f"/static/images/{word}.jpg"
    except Exception as e:
        print(f"Error generating image for '{word}': {str(e)}")
        return None  # Возвращаем None вместо пути к placeholder

def initialize_database():
    conn = sqlite3.connect('words_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS words
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         word TEXT UNIQUE,
         category TEXT,
         image_path TEXT)
    ''')
    
    # Проверяем, есть ли уже данные в таблице
    cursor.execute("SELECT COUNT(*) FROM words")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("Initializing database with words and images...")
        for category, words in simple_words.items():
            for word in words:
                image_path = generate_image(word, category)
                if image_path:
                    try:
                        cursor.execute("INSERT INTO words (word, category, image_path) VALUES (?, ?, ?)", (word, category, image_path))
                    except sqlite3.IntegrityError:
                        print(f"Word '{word}' already exists in the database")
                else:
                    print(f"Skipping '{word}' due to image generation failure")
        print("Database initialization complete.")
    else:
        print("Database already contains data. Skipping initialization.")
    
    conn.commit()
    conn.close()

def get_random_words(count=10):
    conn = sqlite3.connect('words_database.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT word, category, image_path FROM words ORDER BY RANDOM() LIMIT {count}")
    random_words = cursor.fetchall()
    conn.close()
    words = [{"word": word, "category": category, "image_path": image_path} for word, category, image_path in random_words]
    for word in words:
        print(f"Word: {word['word']}, Image path: {word['image_path']}")
    return words

if __name__ == "__main__":
    initialize_database()