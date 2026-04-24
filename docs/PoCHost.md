# Proof of Concept (PoC) Hosting Guide

This guide explains how to host the SmartTechBuddy Input Distribution system online for demonstration purposes—**without setting up any databases or Redis cache**. 

This utilizes the `backend/app_simple.py` mock server built directly into the repository to run entirely on memory, exactly as it works on your local machine without databases.

**Recommended Free Stack:**
- **Frontend**: Vercel (or Netlify/GitHub Pages)
- **Backend API**: Render.com (Using the standalone mock server)

---

### Step 1: Backend Deployment (Render.com)
1. Go to [Render.com](https://render.com) and sign in with GitHub.
2. Click **New +** and select **Web Service**.
3. Connect your GitHub repository.
4. Configure the Web Service:
   - **Name**: `smarttech-simple-api` (or a name of your choice)
   - **Root Directory**: `backend` (Important! Make sure this is set)
   - **Environment**: `Python`
   - **Build Command**: `pip install Flask flask-cors gunicorn` (We don't need the full `requirements.txt` packages for this lightweight mock API)
   - **Start Command**: `gunicorn -w 1 -b 0.0.0.0:$PORT app_simple:app`
   - **Instance Type**: Free Plan
5. Click **Create Web Service**. Render will now host the mock API securely.
6. Copy the deployed API URL (e.g., `https://smarttech-simple-api.onrender.com`).

*(Note: The Render free tier sleeps after 15 minutes of inactivity. First requests after sleeping may take ~50 seconds to spin up).*

---

### Step 2: Link Frontend to Backend
1. In your local code, go to `frontend/pod-interface/js/app.js` and any other frontend JS files you might use (like `frontend/shared/auth.js`).
2. Update the API base URL to point to your new Render Backend URL.
   ```javascript
   // Change from localhost to your live Render URL
   const API_BASE_URL = 'https://smarttech-simple-api.onrender.com/api/v1';
   ```
3. Commit and push this change to your repository on GitHub.

---

### Step 3: Frontend Deployment (Vercel)
1. Go to [Vercel.com](https://vercel.com) and log in with GitHub.
2. Click **Add New** -> **Project**.
3. Import your GitHub repository.
4. Configure Project:
   - **Framework Preset**: Other / Vanilla
   - **Root Directory**: `frontend` (Click edit and select the `frontend` folder).
5. Click **Deploy**. Vercel will instantly host your HTML/CSS/JS and provide you with a live URL.

---

That's it! Your Proof of Concept is fully hosted—mocked, robust, and completely free. You don't need databases, environment variables, or Redis providers.