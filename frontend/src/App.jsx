
import { useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:5000/api";

function App() {
  const [newsText, setNewsText] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    setResult(null);
    setError("");

    if (!newsText.trim()) {
      setError("Please enter a news article or headline.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/predict`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: newsText }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Prediction failed.");
      }

      setResult(data);
    } catch (err) {
      setError(
        "Could not connect to the backend. Check that Flask is running."
      );
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <header className="header">
        <p className="eyebrow">NLP + MACHINE LEARNING</p>
        <h1>Fake News Detector</h1>
        <p className="subtitle">
          Enter a news headline or article to get a model prediction.
        </p>
      </header>

      <section className="panel">
        <form onSubmit={handleSubmit}>
          <label htmlFor="newsText">News article or headline</label>

          <textarea
            id="newsText"
            value={newsText}
            onChange={(event) => setNewsText(event.target.value)}
            placeholder="Paste your news text here..."
            maxLength={20000}
            rows={9}
          />

          <div className="form-footer">
            <span>{newsText.length}/20000 characters</span>

            <button type="submit" disabled={loading}>
              {loading ? "Analyzing..." : "Analyze News"}
            </button>
          </div>
        </form>

        {error && <p className="error">{error}</p>}

        {result && (
          <section className="result" aria-live="polite">
            <p className="eyebrow">MODEL RESULT</p>

            <h2 className={result.label === "Real" ? "real" : "fake"}>
              {result.label} News
            </h2>

            <p>
              Model confidence: <strong>{result.confidence}%</strong>
            </p>
          </section>
        )}
      </section>

      <footer>
        This tool identifies patterns learned from its training dataset.
        Its prediction is not proof that a news story is true or false.
      </footer>
    </main>
  );
}

export default App;
