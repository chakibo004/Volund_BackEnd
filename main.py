from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import requests
import json
from dotenv import load_dotenv
from pymongo import MongoClient
from jose import JWTError, jwt
from datetime import datetime, timedelta
import bcrypt
import difflib
import openai
import uuid
from bson import ObjectId
from fastapi.encoders import jsonable_encoder

load_dotenv()

app = FastAPI()

# Add CORS middleware to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

SECRET_KEY = os.getenv("SECRET_KEY")
AI71_API_KEY = os.getenv("AI71_API_KEY")
AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")
MONGO_URI = os.getenv("MONGO_URI")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

app = FastAPI()
AI71_BASE_URL = "https://api.ai71.ai/v1/"

AI_client = openai.OpenAI(
    api_key=AI71_API_KEY,
    base_url=AI71_BASE_URL,
)

client = MongoClient(MONGO_URI)
db = client['discussion_db']
users_collection = db['users']
sessions_collection = db['sessions']

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_jwt_token(token: str):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception



# Models



class User(BaseModel):
    username: str
    password: str

class QueryLocation(BaseModel):
    latitude: float
    longitude: float
    token: str
    session_id: Optional[str] = None
    question: Optional[str] = ""

class QueryPlace(BaseModel):
    place_name: str
    token: str
    session_id: Optional[str] = None
    question: Optional[str] = ""



# Password hashing and authentication



def authenticate_user(username: str, password: str):
    user = users_collection.find_one({"username": username})
    if user and bcrypt.checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):
        return True
    return False

def object_id_to_str(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def create_user(username: str, password: str):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = {
        "username": username,
        "password": hashed_password
    }
    users_collection.insert_one(user)

# Amadeus API integration

def get_amadeus_access_token():
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_CLIENT_ID,
        "client_secret": AMADEUS_CLIENT_SECRET
    }
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        raise Exception(f"Failed to get access token: {response.text}")

def count_tokens(text: str) -> int:
    return len(text.split())

def truncate_context(context: str, max_tokens: int = 500) -> str:
    tokens = context.split()
    if len(tokens) > max_tokens:
        tokens = tokens[-max_tokens:]
    return ' '.join(tokens)

# Tourism, fauna and flora data fetching

def fetch_tourism_data(latitude, longitude):
    access_token = get_amadeus_access_token()
    url = "https://test.api.amadeus.com/v1/shopping/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "radius": 1,
        "limit": 5
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get('data', [])[:20]

def fetch_gbif_data_for_location(latitude, longitude, radius_km):
    url = "https://api.gbif.org/v1/occurrence/search"
    params = {
        "decimalLatitude": latitude,
        "decimalLongitude": longitude,
        "radius": radius_km * 1000,
        "limit": 10
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json().get('results', [])

def classify_gbif_data(gbif_data):
    fauna = []
    flora = []
    for record in gbif_data:
        kingdom = record.get('kingdom')
        species = record.get('species', 'Unknown Species')
        media = record.get('media', [])
        image = media[0]['identifier'] if media else ''
        if kingdom == 'Animalia':
            fauna.append({"species": species, "image": image})
        elif kingdom == 'Plantae':
            flora.append({"species": species, "image": image})
    return {"fauna": fauna, "flora": flora}

def summarize_data(fauna_flora_data, tourism_data):
    summary = {
        "fauna": fauna_flora_data.get("fauna", []),
        "flora": fauna_flora_data.get("flora", []),
        "tourism_activities": tourism_data
    }
    return summary

# Session management and interactions

def save_session(username: str, summary: dict, initial_query: str):
    session_id = uuid.uuid4().hex
    session_data = {
        "session_id": session_id,
        "username": username,
        "summary": summary,
        "interactions": [{"query": initial_query, "response": ""}],
        "location_query_executed": False,
        "timestamp": datetime.utcnow()
    }
    sessions_collection.insert_one(session_data)
    return session_id

def update_session(session_id: str, query: str, response: str):
    session_data = sessions_collection.find_one({"session_id": session_id})
    if not session_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session not found")

    sessions_collection.update_one(
        {"session_id": session_id},
        {
            "$push": {
                "interactions": {
                    "query": query,
                    "response": response
                }
            },
            "$set": {"timestamp": datetime.utcnow()}
        }
    )

def get_session(session_id: str):
    session = sessions_collection.find_one({"session_id": session_id})
    if session:
        session['_id'] = object_id_to_str(session['_id'])
    return session

def get_sessions_for_user(username: str):
    return list(sessions_collection.find({"username": username}))

def load_data_from_json_file(filename):
    try:
        with open(filename, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []

# Main AI query function

def query_ai(session_id: str, token: str, query: str):
    username = verify_jwt_token(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    session_data = get_session(session_id)
    
    if not session_data:
        session_id = save_session(username, summary={}, initial_query=query)
        session_data = get_session(session_id)
        context = f"User: {query}"
    else:
        context = "\n".join([f"\nUser: {interaction['query']}\nAI: {interaction['response']}" 
                             for interaction in session_data.get("interactions", [])])
        context += f"\nUser: {query}"

        fauna_info = session_data.get("summary", {}).get("fauna", [])
        flora_info = session_data.get("summary", {}).get("flora", [])
        
        if fauna_info:
            fauna_species = ', '.join([species['species'] for species in fauna_info])
            context += f"\nFauna: {fauna_species}"
        if flora_info:
            flora_species = ', '.join([species['species'] for species in flora_info])
            context += f"\nFlora: {flora_species}"
    
    context = truncate_context(context, max_tokens=700)
    print(context)
    
    messages = [
        {"role": "system", "content": "You are a knowledgeable assistant about fauna, flora, and tourism activities. Always consider the full context of the conversation"},
        {"role": "user", "content": context}
    ]

    response = AI_client.chat.completions.create(
        model="tiiuae/falcon-180b-chat",
        messages=messages,
    )

    ai_response_content = response.choices[0].message.content
    update_session(session_id, query, ai_response_content)
    return ai_response_content



# Routes



@app.post("/sign_up")
async def sign_up(user: User):
    if users_collection.find_one({"username": user.username}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    create_user(user.username, user.password)
    return {"status": "success", "message": "User registered successfully"}

@app.post("/login")
async def login(user: User):
    if not authenticate_user(user.username, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"status": "success", "access_token": access_token, "token_type": "bearer"}

@app.post("/query_location")
async def query_location(query: QueryLocation):
    username = verify_jwt_token(query.token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    session_data = get_session(query.session_id)
    if not session_data:
        session_id = None
    else:
        session_id = query.session_id

    if session_id and session_data.get("location_query_executed", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Location query already executed for this session")

    try:
        gbif_data = fetch_gbif_data_for_location(query.latitude, query.longitude, radius_km=1)
        classified_data = classify_gbif_data(gbif_data)
        tourism_data = fetch_tourism_data(query.latitude, query.longitude)

        summary = summarize_data(classified_data, tourism_data)

        fauna_info = summary.get("fauna", [])
        flora_info = summary.get("flora", [])
        tourism_activities = summary.get("tourism_activities", [])

        fauna_species = ', '.join([species['species'] for species in fauna_info]) if fauna_info else 'No fauna information available'
        flora_species = ', '.join([species['species'] for species in flora_info]) if flora_info else 'No flora information available'
        tourism_activity_names = ', '.join([activity['name'] for activity in tourism_activities]) if tourism_activities else 'No tourism activities available'

        if not query.question:
            query.question = "Can you provide more details about this location?"

        ai_query_content = f"""
        Here's the information about the location:
        - Latitude: {query.latitude}
        - Longitude: {query.longitude}
        - Fauna: {fauna_species}
        - Flora: {flora_species}
        - Tourism Activities: {tourism_activity_names}

        Question: {query.question}
        """

        ai_query_content = truncate_context(ai_query_content, max_tokens=500)
        print(ai_query_content)
        ai_response_content = query_ai(query.session_id, query.token, ai_query_content)

        if session_id is None:
            session_id = save_session(username, {}, initial_query=query.question)
        
        update_session(session_id, query.question, ai_response_content)
        session_data = get_session(session_id)

        session_data["location_query_executed"] = True

        json_filename = f"session_{session_id}_data.json"
        with open(json_filename, "w") as json_file:
            json.dump(summary, json_file)

        return {"response": ai_response_content, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Query execution failed: {e}")
    
@app.post("/query_place")
async def query_place(query: QueryPlace):
    username = verify_jwt_token(query.token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    session_id = query.session_id
    if not session_id or not get_session(session_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session not found")

    json_filename = f"session_{session_id}_data.json"
    try:
        with open(json_filename, "r") as file:
            session_data = json.load(file)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session data not found")

    tourism_data = session_data.get("tourism_activities", [])

    place_names = [place["name"] for place in tourism_data]
    best_match = difflib.get_close_matches(query.place_name, place_names, n=1, cutoff=0.6)
    if not best_match:
        return {"status": "error", "message": "Place not found"}

    place_info = next((place for place in tourism_data if place["name"] == best_match[0]), None)

    if not query.question:
        query.question = f"Can you provide more details about {best_match[0]}? I would like to know more about this location."

    ai_query_content = f"Discuss about {place_info}. {query.question}"

    ai_query_content = truncate_context(ai_query_content, max_tokens=500)
    print(ai_query_content)
    ai_response_content = query_ai(session_id, query.token, ai_query_content)

    return {"response": ai_response_content, "session_id": session_id}

@app.post("/query_ai")
async def query_ai_with_session(query: str, token: str, session_id: Optional[str] = None):
    username = verify_jwt_token(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    if not session_id or not get_session(session_id):
        session_id = save_session(username, {}, "")

    ai_response_content = query_ai(session_id, token, query)

    return {"response": ai_response_content, "session_id": session_id}

@app.get("/session-history/")
async def get_session_history(token: str):
    username = verify_jwt_token(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    sessions = get_sessions_for_user(username)
    organized_sessions = []
    for session in sessions:
        conversation = []
        for interaction in session.get("interactions", []):
            conversation.append({"query": interaction["query"], "response": interaction["response"]})
        organized_sessions.append({"session_id": session["session_id"], "conversation": conversation})

    return {"sessions": organized_sessions}

@app.get("/session-history/{session_id}")
async def get_session_history_by_id(session_id: str, token: str):
    username = verify_jwt_token(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    session_data = get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session_data.get("username") != username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this session is forbidden")
    conversation = []
    for interaction in session_data.get("interactions", []):
        conversation.append({"query": interaction["query"], "response": interaction["response"]})

    return {"session_id": session_id, "conversation": conversation}

@app.get("/get_all_places/{session_id}")
async def get_all_places(session_id: str, token: str):
    username = verify_jwt_token(token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    session_data = get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session_data.get("username") != username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this session is forbidden")
    
    json_filename = f"session_{session_id}_data.json"
    try:
        with open(json_filename, "r") as file:
            session_data = json.load(file)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session data not found")
    
    tourism_data = session_data.get("tourism_activities", [])
    places = []
    for place in tourism_data:
        place_info = {
            "name": place.get("name"),
            "longitude": place.get("geoCode", {}).get("longitude"),
            "latitude": place.get("geoCode", {}).get("latitude"),
            "pictures": place.get("pictures", [])
        }
        places.append(place_info)
    
    return {"places": places, "session_id": session_id}
