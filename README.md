### I. Setup and Usage Guide

This guide provides step-by-step instructions for setting up the environment, installing dependencies, and launching the application.

#### **1. Clone the Repository**

First, clone the repository where the code is located then install dependencies:

`pip install -r requirements.txt`

#### **2. Launch the Application**

You can start the FastAPI application using Uvicorn. Use the following command to run the application in development mode with automatic reloading:

`uvicorn main:app --reload`

#### **3. Access the API Documentation**

Once the application is running, you can access the automatically generated API documentation at:

* **Swagger UI:** `http://127.0.0.1:8000/docs`

### II. API Routes Documentation

This documentation provides a detailed explanation of the API routes for your application. It covers the purpose of each route, the expected input and output, and how they should be used.

---

### **1. Sign Up**

* **Endpoint:** `/sign_up`
* **Method:** `POST`
* **Purpose:** Register a new user.
* **Input:**
  * **Body:**
    * `username`: The username of the new user (string).
    * `password`: The password of the new user (string).
* **Output:**
  * **Success:** Returns a JSON response with a status of "success" and a message indicating the user was registered successfully.
  * **Failure:** If the username is already registered, returns a `400` status code with an error message.
* **Usage:** Used when a new user wants to create an account in the system.

---

### **2. Login**

* **Endpoint:** `/login`
* **Method:** `POST`
* **Purpose:** Authenticate a user and provide a JWT token.
* **Input:**
  * **Body:**
    * `username`: The username of the user (string).
    * `password`: The password of the user (string).
* **Output:**
  * **Success:** Returns a JSON response with a status of "success", an `access_token`, and the `token_type` as "bearer".
  * **Failure:** If the credentials are invalid, returns a `401` status code with an error message.
* **Usage:** Used when a user wants to log in and obtain a token for accessing protected routes.

---

### **3. Query Location**

* **Endpoint:** `/query_location`
* **Method:** `POST`
* **Purpose:** Query information about a specific geographical location based on latitude and longitude.
* **Input:**
  * **Body:**
    * `latitude`: Latitude of the location (float).
    * `longitude`: Longitude of the location (float).
    * `token`: JWT token for authentication (string).
    * `session_id`: (Optional) Session ID if continuing from a previous session (string).
    * `question`: (Optional) A specific question to ask about the location (string).
* **Output:**
  * **Success:** Returns a JSON response with the AI-generated content and the session ID.
  * **Failure:** Various error responses based on invalid token, session issues, or processing errors.
* **Usage:** Used when a user wants detailed information about a location by providing its coordinates.

---

### **4. Query Place**

* **Endpoint:** `/query_place`
* **Method:** `POST`
* **Purpose:** Fetch detailed information about a specific place by name.
* **Input:**
  * **Body:**
    * `place_name`: The name of the place to search for (string).
    * `token`: JWT token for authentication (string).
    * `session_id`: Session ID for tracking the interaction (string).
    * `question`: (Optional) A specific question to ask about the place (string).
* **Output:**
  * **Success:** Returns a JSON response with AI-generated content about the place and the session ID.
  * **Failure:** Various error responses based on invalid token, session issues, or data not found.
* **Usage:** Used when a user wants detailed information about a place by providing its name.

---

### **5. Query AI with Session**

* **Endpoint:** `/query_ai`
* **Method:** `POST`
* **Purpose:** Send a query to the AI and optionally track it within a session.
* **Input:**
  * **Body:**
    * `query`: The query string to ask the AI (string).
    * `token`: JWT token for authentication (string).
    * `session_id`: (Optional) Session ID if continuing from a previous session (string).
* **Output:**
  * **Success:** Returns a JSON response with the AI-generated content and the session ID.
  * **Failure:** Various error responses based on invalid token or session issues.
* **Usage:** Used when a user wants to interact with the AI and optionally store the interaction in a session.

---

### **6. Get Session History**

* **Endpoint:** `/session-history/`
* **Method:** `GET`
* **Purpose:** Retrieve the history of all sessions for the authenticated user.
* **Input:**
  * **Query Parameter:**
    * `token`: JWT token for authentication (string).
* **Output:**
  * **Success:** Returns a JSON response with a list of sessions and their corresponding conversations.
  * **Failure:** Returns an error response if the token is invalid or if there are issues retrieving the sessions.
* **Usage:** Used when a user wants to view the history of their interactions with the AI.

---

### **7. Get Session History by ID**

* **Endpoint:** `/session-history/{session_id}`
* **Method:** `GET`
* **Purpose:** Retrieve the history of a specific session by its ID.
* **Input:**
  * **Path Parameter:**
    * `session_id`: The ID of the session to retrieve (string).
  * **Query Parameter:**
    * `token`: JWT token for authentication (string).
* **Output:**
  * **Success:** Returns a JSON response with the session's conversation.
  * **Failure:** Returns an error response if the token is invalid, the session is not found, or the user is not authorized to access the session.
* **Usage:** Used when a user wants to view the conversation history of a specific session.

---

### **8. Get All Places**

* **Endpoint:** `/get_all_places/{session_id}`
* **Method:** `GET`
* **Purpose:** Retrieve a list of all places associated with a specific session.
* **Input:**
  * **Path Parameter:**
    * `session_id`: The ID of the session from which to retrieve the places (string).
  * **Query Parameter:**
    * `token`: JWT token for authentication (string).
* **Output:**
  * **Success:** Returns a JSON response containing a list of places with the following details for each place:
    * `name`: Name of the place (string).
    * `longitude`: Longitude of the place (float).
    * `latitude`: Latitude of the place (float).		
    * `pictures`: An array of URLs pointing to images of the place (array of strings).
    * `session_id`: The ID of the session associated with the retrieved places.
  * **Failure:**
    * `401 Unauthorized`: If the provided token is invalid or missing.
    * `403 Forbidden`: If the session does not belong to the authenticated user.
    * `404 Not Found`: If the session ID or the session data is not found.
* **Usage:** Used to retrieve and display all places that are linked to a specific session, useful for providing users with a summarized view of the places they have interacted with or queried during a session.

---

### Authentication:

* All protected routes require a valid JWT token provided in the request headers as `Authorization: Bearer <token>`.

### Error Handling:

* Each endpoint includes error handling for scenarios like invalid credentials, unauthorized access, session not found, and internal server errors. Ensure that your frontend properly handles these error responses and displays appropriate messages to the user.

---

### **Authentication:**

* All protected routes require a valid JWT token provided in the request headers as `Authorization: Bearer <token>`.

### **Error Handling:**

* Each endpoint includes error handling for scenarios like invalid credentials, unauthorized access, session not found, and internal server errors. Ensure that your frontend properly handles these error responses and displays appropriate messages to the user.
