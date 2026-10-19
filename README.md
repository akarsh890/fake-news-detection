# Fake News Detection System

A machine-learning-powered web application (**VeritasML**) that analyzes news text and predicts whether its linguistic patterns align with **Real** or **Fake** news articles. The project combines a React 19 + Vite frontend, a Python Flask REST API, a pre-trained `scikit-learn` (`TfidfVectorizer` + `LogisticRegression`) pipeline, and optional MySQL persistence via `PyMySQL`.

---

## Architecture & Features

- **Machine Learning Inference Pipeline:** Uses a serialized `scikit-learn==1.6.1` pipeline (`TfidfVectorizer` with 100k unigram/bigram features + `LogisticRegression`) loaded once at server startup from `backend/artifacts/fake_news_pipeline.joblib`.
- **Resilient Flask REST API:** Exposes `/api/health`, `/api/predict`, and `/api/history` with strict JSON validation, input size limits (20,000 characters), configurable CORS, and safe error handling.
- **Fault-Tolerant MySQL Persistence:** Saves each submitted article (`news`) and its prediction (`prediction`) atomically in a single transaction when MySQL is configured. If MySQL is unconfigured or unreachable, predictions continue to work seamlessly in stateless mode and clearly report their persistence state.
- **Modern, Accessible React Dashboard:** Features live API and MySQL status indicators, synthetic test presets, optional headline input, character/word counters, accessible confidence meters, session/database history, and light/dark theme support.

---

## Technology Stack

| Component | Technologies |
|---|---|
| **Frontend** | React 19, Vite 8, CSS Custom Properties (Light/Dark Theme) |
| **Backend** | Python 3.12, Flask 3.1, Flask-CORS, python-dotenv |
| **Machine Learning** | scikit-learn `1.6.1`, Joblib, NumPy, SciPy |
| **Database** | MySQL 8.0.16+, PyMySQL |
| **Testing & Linting** | Python `unittest`, Node `node:test`, `oxlint` |

---

## Project Structure

```text
fake-news-detection/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── db.py                # MySQL connection, health check, atomic save & history
│   │   └── predictor.py         # Model loading, validation & inference
│   ├── artifacts/
│   │   └── fake_news_pipeline.joblib
│   ├── .env.example             # Environment variable template (safe placeholders)
│   ├── db.py                    # Compatibility re-export of app.db
│   ├── requirements.txt         # Backend Python dependencies
│   ├── run.py                   # Flask application entrypoint
│   ├── test_db_integration.py   # Unit & MySQL integration test suite
│   └── test_model.py            # ML pipeline unit test suite
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.css              # Dashboard styling
│   │   ├── App.jsx              # Main React application
│   │   ├── App.test.js          # Frontend automated tests
│   │   ├── index.css            # Design system tokens & accessibility rules
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .env.example                 # Root environment variable template
├── .gitignore
├── fake_news_detection_db.sql   # Non-destructive MySQL schema initialization script
├── requirements.txt             # Root Python dependency manifest
├── run.py                       # Root convenience wrapper for backend/run.py
└── README.md
```

---

## Prerequisites

1. **Python 3.12** (`py -3.12` via the Windows Python Launcher).
   - *Important:* The saved model (`fake_news_pipeline.joblib`) was serialized with `scikit-learn==1.6.1`. Use Python 3.12 so `scikit-learn==1.6.1` installs cleanly without version-mismatch warnings.
2. **Node.js (v18+)** and **npm**.
3. **MySQL Server 8.0.16+** *(Optional for stateless predictions; required for database persistence)*.

---

## Windows Installation & Setup Guide

### 1. Create and Activate the Python 3.12 Virtual Environment

From the project root (`C:\Users\sonwa\fake-news-detection`) in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Python Dependencies

```powershell
pip install -r backend\requirements.txt
```

### 3. Configure Environment Variables

Copy the example environment file to `backend\.env` (or `.env` in the project root):

```powershell
Copy-Item backend\.env.example backend\.env
```

Edit `backend\.env` with your local settings (never commit `.env`):

```ini
# MySQL Database Configuration
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_NAME=fake_news_detection_db

# Flask Server Configuration
FLASK_DEBUG=false
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

> **Note:** If `DB_USER` or `DB_NAME` are left unset or left as placeholder values (`your_mysql_user`), the backend automatically runs in **stateless mode**—predictions work normally and the API reports `"status": "not_configured"` for persistence.

### 4. MySQL Setup & Safe Schema Initialization (When MySQL is Installed)

If MySQL Server is not yet installed on Windows:
1. Install MySQL Community Server 8.0+ (e.g., via the official MySQL Installer or `winget install Oracle.MySQL`) and ensure the MySQL Windows service is running on port `3306`.
2. Initialize the database schema using `fake_news_detection_db.sql`. The script uses `CREATE DATABASE IF NOT EXISTS` and `CREATE TABLE IF NOT EXISTS` so it will **not** drop or overwrite existing data:

```powershell
Get-Content fake_news_detection_db.sql | mysql -u root -p
```

3. Update `DB_USER`, `DB_PASSWORD`, and `DB_NAME=fake_news_detection_db` in `backend\.env`.

---

## Running the Application

### 1. Start the Flask Backend

From the project root in PowerShell:

```powershell
.\.venv\Scripts\python.exe backend\run.py
```

*(You can also run `.\.venv\Scripts\python.exe run.py` from the root or `python run.py` from `backend/`).*

The API will listen on `http://127.0.0.1:5000`.

### 2. Start the React Frontend

Open a second PowerShell terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite (typically `http://localhost:5173`).

---

## Automated Testing & Verification

### Backend Unit & Integration Tests

From the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -p "test_*.py" -v
```

- Runs 20 unit and endpoint tests covering ML pipeline loading, valid predictions, empty/whitespace rejection, >20,000 character rejection, malformed JSON, wrong data types, simulated database failure resilience, transaction commit/rollback, `/api/health`, and `/api/history`.
- When `DB_USER` and `DB_NAME` are configured with a reachable MySQL server, 6 additional live database integration tests (`DatabaseTests`) automatically run using isolated `[TEST]` rows and clean up after themselves.

### Frontend Tests, Linting & Production Build

From `frontend/`:

```powershell
npm test
npm run lint
npm run build
```

---

## API Reference

### 1. Health & Diagnostics

**Endpoint:** `GET /api/health`

Example response (`200 OK`):

```json
{
  "status": "ok",
  "message": "Fake News Detection API is running",
  "model": {
    "loaded": true,
    "model_file": "fake_news_pipeline.joblib",
    "pipeline_steps": ["tfidf", "classifier"]
  },
  "database": {
    "configured": false,
    "connected": false,
    "status": "not_configured",
    "message": "MySQL is not configured (set DB_USER and DB_NAME in .env to enable persistence)."
  }
}
```

### 2. Predict News

**Endpoint:** `POST /api/predict` (add `?meta=1` or `"include_meta": true` to include persistence metadata)

Example request:

```json
{
  "headline": "Regional Rail Expansion Plan Approved",
  "text": "The Department of Transportation announced on Tuesday that federal and municipal agencies have finalized a five-year infrastructure agreement."
}
```

Standard response (`POST /api/predict`, `200 OK`):

```json
{
  "label": "Real",
  "confidence": 65.46
}
```

Extended response (`POST /api/predict?meta=1`, `200 OK`):

```json
{
  "label": "Real",
  "confidence": 65.46,
  "persistence": {
    "saved": false,
    "status": "not_configured",
    "message": "MySQL is not configured; prediction returned in stateless mode."
  }
}
```

### 3. Recent Predictions History

**Endpoint:** `GET /api/history?limit=10`

Returns recent predictions stored in MySQL when connected, or `{"available": false, "items": []}` when operating in stateless mode.

---

## Common Errors & Solutions

| Issue | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'flask_cors'` or `'pymysql'` | Running global Python or an incomplete virtual environment | Activate `.venv` (`.\.venv\Scripts\Activate.ps1`) and run `pip install -r backend\requirements.txt`. |
| `InconsistentVersionWarning` when loading `fake_news_pipeline.joblib` | Environment has `scikit-learn 1.9.x` (e.g. under Python 3.14) instead of `1.6.1` | Recreate `.venv` with Python 3.12 (`py -3.12 -m venv .venv`) and install `scikit-learn==1.6.1`. |
| MySQL badge shows `Stateless Mode` or `Unreachable` | `.env` not created or MySQL Server is not running on port 3306 | Ensure MySQL Server is running, run `fake_news_detection_db.sql`, and configure `backend\.env`. |

---

## Known Model Limitations

- **Statistical Pattern Matching, Not Fact-Checking:** The model uses TF-IDF n-gram frequencies and Logistic Regression learned from its training dataset. It evaluates writing style and lexical patterns rather than verifying real-world facts.
- **Uncalibrated Confidence Scores:** The confidence percentage (`predict_proba`) represents the classifier's internal probability estimate for the predicted class, not an objective probability that an article is factually true or false.
- **Domain & Temporal Drift:** Articles covering topics, regions, or writing styles underrepresented in the training data may be misclassified. Always verify news stories against authoritative primary sources.
