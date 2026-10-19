# Fake News Detection System

A machine-learning-powered web application that analyzes news text and predicts whether it is **Real** or **Fake**. The project combines a React frontend, a Flask REST API, and a trained machine-learning model to provide predictions through a simple user interface.

## Features

- **Fake News Classification:** Predicts whether submitted news text is real or fake.
- **Machine Learning Integration:** Uses a pre-trained model to generate predictions.
- **Interactive Web Interface:** React-based frontend for entering news and viewing results.
- **REST API:** Flask backend exposes endpoints for health checks and predictions.
- **Input Validation:** Rejects empty news submissions and text exceeding the configured character limit.
- **Prediction Confidence:** Returns the model's prediction confidence when available.

## Technology Stack

| Component | Technologies |
|---|---|
| Frontend | React, JavaScript, Vite |
| Backend | Python, Flask |
| Machine Learning | Scikit-learn, Joblib |
| API Communication | HTTP, JSON |
| Version Control | Git, GitHub |

## Project Structure

```text
fake-news-detection/
├── backend/
│   ├── app/
│   │   └── predictor.py
│   ├── run.py
│   └── ...
├── frontend/
│   ├── src/
│   ├── package.json
│   └── ...
├── .gitignore
└── README.md
```

*Note: The exact files inside `backend/` and `frontend/` may vary depending on your implementation.*

## Prerequisites

Install the following before running the application:

- Python 3.12
- Node.js and npm
- Git

The trained model and any required preprocessing artifacts must also be available in the locations expected by the backend.

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/akarsh890/fake-news-detection.git
cd fake-news-detection
```

### 2. Set up the Python backend

From the project root, create and activate a virtual environment.

**Windows PowerShell:**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the backend dependencies:

```powershell
cd backend
pip install -r requirements.txt
```

If `requirements.txt` has not yet been created, install the dependencies listed in your project instead of running the command above.

Start the Flask server:

```powershell
python run.py
```

The backend should be available at:

`http://127.0.0.1:5000`

### 3. Set up the React frontend

Open a second terminal from the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite, usually:

`http://localhost:5173`

Keep both the Flask backend and React development server running while testing the application.

## API Endpoints

### Health Check

**Endpoint:** `GET /api/health`

Checks whether the backend is running.

Example response:

```json
{
  "status": "ok",
  "message": "Fake News Detection API is running"
}
```

### Predict News

**Endpoint:** `POST /api/predict`

Accepts news text and returns a model prediction.

Example request:

```json
{
  "text": "Enter the news article you want to analyze."
}
```

The response contains the prediction and any additional fields returned by the model.

The API rejects empty input and text longer than 20,000 characters.

## How It Works

1. The user enters a news article in the React interface.
2. The frontend sends the article to the Flask prediction API.
3. The backend validates the input.
4. The trained machine-learning model processes the text.
5. The backend returns the predicted class and available confidence information.
6. The frontend displays the result to the user.

## Testing

The following functionality has been tested during development:

- Loading the trained model locally.
- Checking the Flask health endpoint.
- Submitting news through the prediction endpoint.
- Generating predictions through the React interface.
- Validating empty input.

## Database Integration

MySQL integration is planned as a separate development task. It can be used to store prediction history, including submitted text, predicted class, confidence, and timestamps.

Database functionality should be documented as implemented only after it has been integrated and tested.

## Future Improvements

- Integrate MySQL for persistent prediction history.
- Add user authentication and prediction history if required.
- Improve model evaluation using precision, recall, F1-score, and a confusion matrix.
- Add automated backend and frontend tests.
- Improve error handling and deployment configuration.
- Deploy the application for public access.

## Limitations

- Predictions are model-based estimates and may be incorrect.
- Confidence scores should not be interpreted as proof that a news article is true or false.
- Reliable performance depends on the quality and representativeness of the training data.
- The system should be used as a preliminary screening tool rather than the sole basis for judging news credibility.

## Contributors

- **Akarsh Diwakar** — Project development, machine-learning integration, Flask API, and React frontend.
- **Collaborators** — Contributions to be added as the project develops.

## License

No license has been specified yet. Add an appropriate license before allowing others to reuse or redistribute the project.
