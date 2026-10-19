import { useEffect, useState } from "react";
import "./App.css";

const CONFIGURED_API_URL = import.meta.env.VITE_API_URL;
const API_CANDIDATES = CONFIGURED_API_URL
  ? [CONFIGURED_API_URL]
  : ["/api", "http://127.0.0.1:5000/api", "http://localhost:5000/api"];
const MAX_CHARS = 20000;

async function fetchFromApi(endpointPath, options = {}) {
  let lastError = null;
  for (const base of API_CANDIDATES) {
    try {
      const response = await fetch(`${base}${endpointPath}`, options);
      // If Vite dev proxy isn't active and returns HTML 404 for /api, try the direct backend URL
      const contentType = response.headers.get("content-type") || "";
      if (base === "/api" && response.status === 404 && !contentType.includes("application/json")) {
        continue;
      }
      return response;
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError || new Error("Could not connect to the backend.");
}

const SAMPLE_ARTICLES = [
  {
    id: "public-policy",
    label: "Public Policy Report",
    headline: "Transportation Department Approves Regional Rail Expansion Plan",
    text: "The Department of Transportation announced on Tuesday that federal and municipal agencies have finalized a five-year infrastructure agreement to modernize commuter rail corridors across three metropolitan regions. According to the published budget report, phase one will replace aging signal equipment and add twelve electric locomotives following environmental review.",
  },
  {
    id: "sensational-claim",
    label: "Sensational Viral Claim",
    headline: "SHOCKING: Secret Lemon Peel Trick Cures All Chronic Illnesses Overnight!",
    text: "BREAKING: Doctors and pharmaceutical companies are furious after an anonymous internet blogger leaked a secret kitchen remedy that reportedly eliminates every known disease in less than 24 hours without exercise or medication! Share this immediately before the mainstream media deletes this miracle discovery forever!",
  },
];

function countWords(str) {
  const trimmed = str.trim();
  if (!trimmed) return 0;
  return trimmed.split(/\s+/).length;
}

function App() {
  const [headline, setHeadline] = useState("");
  const [newsText, setNewsText] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("veritas_theme") || "light";
    } catch {
      return "light";
    }
  });

  const [healthStatus, setHealthStatus] = useState({
    checked: false,
    apiOnline: false,
    modelLoaded: false,
    dbStatus: "unknown",
    dbMessage: "Checking service status...",
  });

  const [recentItems, setRecentItems] = useState([]);
  const [historySource, setHistorySource] = useState("session");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("veritas_theme", theme);
    } catch {
      // Ignore storage errors in restricted environments
    }
  }, [theme]);

  useEffect(() => {
    let active = true;

    async function checkSystemStatus() {
      try {
        const res = await fetchFromApi("/health");
        const data = await res.json();
        if (!active) return;

        const dbState = data?.database?.status || "not_configured";
        setHealthStatus({
          checked: true,
          apiOnline: res.ok,
          modelLoaded: Boolean(data?.model?.loaded ?? res.ok),
          dbStatus: dbState,
          dbMessage:
            data?.database?.message ||
            (dbState === "connected"
              ? "MySQL connected"
              : "MySQL not configured (stateless mode)"),
        });

        if (dbState === "connected") {
          const histRes = await fetchFromApi("/history?limit=5");
          if (histRes.ok) {
            const histData = await histRes.json();
            if (active && histData?.available && Array.isArray(histData.items)) {
              setRecentItems(histData.items);
              setHistorySource("mysql");
            }
          }
        }
      } catch {
        if (!active) return;
        setHealthStatus({
          checked: true,
          apiOnline: false,
          modelLoaded: false,
          dbStatus: "offline",
          dbMessage: "Backend API is unreachable.",
        });
      }
    }

    checkSystemStatus();
    const intervalId = setInterval(checkSystemStatus, 8000);
    return () => {
      active = false;
      clearInterval(intervalId);
    };
  }, []);

  function handleSelectSample(sample) {
    setHeadline(sample.headline);
    setNewsText(sample.text);
    setError("");
    setResult(null);
  }

  function handleClear() {
    setHeadline("");
    setNewsText("");
    setError("");
    setResult(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();

    setResult(null);
    setError("");

    const trimmedText = newsText.trim();
    if (!trimmedText) {
      setError("Please enter a news article or headline before analyzing.");
      return;
    }

    if (newsText.length > MAX_CHARS) {
      setError(`Text exceeds the maximum limit of ${MAX_CHARS.toLocaleString()} characters.`);
      return;
    }

    setLoading(true);

    let response;
    try {
      const payload = {
        text: newsText,
        include_meta: true,
      };
      if (headline.trim()) {
        payload.headline = headline.trim();
      }

      response = await fetchFromApi("/predict?meta=1", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
    } catch (networkErr) {
      setError("Could not connect to the backend. Check that the Flask server is running on port 5000.");
      console.error(networkErr);
      setLoading(false);
      return;
    }

    try {
      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }

      if (!response.ok) {
        setError(data.error || `Prediction request failed (HTTP ${response.status}).`);
        return;
      }

      setResult(data);

      // Update live DB status if persistence metadata was returned
      if (data.persistence) {
        const saved = Boolean(data.persistence.saved);
        setHealthStatus((prev) => ({
          ...prev,
          apiOnline: true,
          modelLoaded: true,
          dbStatus: saved ? "connected" : data.persistence.status || prev.dbStatus,
          dbMessage: data.persistence.message || prev.dbMessage,
        }));
        if (saved) {
          setHistorySource("mysql");
        }
      }

      const displayHeadline =
        headline.trim() ||
        trimmedText.split(/\r?\n/).find((l) => l.trim())?.slice(0, 90) ||
        trimmedText.slice(0, 90);

      setRecentItems((prev) =>
        [
          {
            prediction_id: data.persistence?.prediction_id || Date.now(),
            headline: displayHeadline,
            label: data.label,
            confidence: data.confidence,
            savedToDb: Boolean(data.persistence?.saved),
          },
          ...prev,
        ].slice(0, 5)
      );
    } finally {
      setLoading(false);
    }
  }

  const wordCount = countWords(newsText);
  const isReal = result?.label === "Real";
  const dbDotClass =
    healthStatus.dbStatus === "connected"
      ? "online"
      : healthStatus.dbStatus === "not_configured"
      ? "warning"
      : "offline";

  return (
    <div className="app-shell">
      <header className="navbar">
        <div className="navbar-inner">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
            </div>
            <div className="brand-text">
              <span className="brand-title">VeritasML</span>
              <span className="brand-subtitle">Fake News Detection System</span>
            </div>
          </div>

          <div className="nav-actions">
            <div className="status-pills" aria-label="System connectivity status">
              <span
                className="status-pill"
                title={
                  healthStatus.apiOnline
                    ? "Flask API & ML Pipeline are ready"
                    : "Flask API is offline or unreachable"
                }
              >
                <span
                  className={`status-dot ${
                    !healthStatus.checked
                      ? "warning"
                      : healthStatus.apiOnline
                      ? "online"
                      : "offline"
                  }`}
                />
                API: {!healthStatus.checked ? "Checking" : healthStatus.apiOnline ? "Online" : "Offline"}
              </span>

              <span className="status-pill" title={healthStatus.dbMessage}>
                <span className={`status-dot ${dbDotClass}`} />
                MySQL:{" "}
                {healthStatus.dbStatus === "connected"
                  ? "Connected"
                  : healthStatus.dbStatus === "not_configured"
                  ? "Stateless Mode"
                  : "Unreachable"}
              </span>
            </div>

            <button
              type="button"
              className="theme-toggle"
              onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
            >
              {theme === "light" ? "Dark Mode" : "Light Mode"}
            </button>
          </div>
        </div>
      </header>

      <main className="page-container">
        <section className="hero">
          <span className="eyebrow-badge">NLP + Machine Learning</span>
          <h1>Fake News Detector</h1>
          <p className="hero-subtitle">
            Enter a news headline or article to evaluate linguistic credibility patterns using our
            trained TF-IDF &amp; Logistic Regression classification pipeline.
          </p>
        </section>

        <div className="workspace-grid">
          {/* Left Panel: Article Submission Form */}
          <section className="card" aria-labelledby="analyzer-heading">
            <div className="card-header">
              <div className="card-title-group">
                <h2 id="analyzer-heading">Article Input</h2>
                <p>Paste an article body or test with a synthetic sample below.</p>
              </div>
            </div>

            <div className="sample-bar" role="group" aria-label="Sample test articles">
              <span className="sample-bar-label">Try sample:</span>
              {SAMPLE_ARTICLES.map((sample) => (
                <button
                  key={sample.id}
                  type="button"
                  className="sample-chip"
                  disabled={loading}
                  onClick={() => handleSelectSample(sample)}
                >
                  {sample.label}
                </button>
              ))}
            </div>

            <form onSubmit={handleSubmit} noValidate>
              <div className="form-group">
                <div className="form-label-row">
                  <label htmlFor="headlineInput" className="form-label">
                    Article Headline
                  </label>
                  <span className="optional-tag">Optional</span>
                </div>
                <input
                  id="headlineInput"
                  type="text"
                  className="input-field"
                  value={headline}
                  onChange={(e) => setHeadline(e.target.value)}
                  placeholder="e.g., Council Approves Regional Transit Budget..."
                  maxLength={200}
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <div className="form-label-row">
                  <label htmlFor="newsText" className="form-label">
                    News article or headline
                  </label>
                  <span className="optional-tag">Required</span>
                </div>
                <textarea
                  id="newsText"
                  className="textarea-field"
                  value={newsText}
                  onChange={(event) => setNewsText(event.target.value)}
                  placeholder="Paste your news text here..."
                  maxLength={MAX_CHARS}
                  rows={9}
                  disabled={loading}
                />
              </div>

              <div className="form-footer">
                <div className="metrics-bar" aria-live="polite">
                  <span className={newsText.length >= MAX_CHARS ? "over-limit" : ""}>
                    {newsText.length}/{MAX_CHARS} characters
                  </span>
                  <span>•</span>
                  <span>{wordCount} words</span>
                </div>

                <div className="button-group">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={handleClear}
                    disabled={loading || (!newsText && !headline && !result && !error)}
                  >
                    Clear
                  </button>

                  <button type="submit" className="btn-primary" disabled={loading}>
                    {loading && <span className="spinner" aria-hidden="true" />}
                    {loading ? "Analyzing..." : "Analyze News"}
                  </button>
                </div>
              </div>
            </form>

            {error && (
              <div className="error-banner" role="alert">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>{error}</span>
              </div>
            )}
          </section>

          {/* Right Panel: Model Result & History */}
          <div className="side-column">
            <section className="card" aria-live="polite" aria-labelledby="result-panel-heading">
              <div className="card-header">
                <div className="card-title-group">
                  <h2 id="result-panel-heading">Model Assessment</h2>
                  <p>Classification output and estimated model confidence</p>
                </div>
              </div>

              {!result ? (
                <div className="empty-result-state">
                  <div className="empty-icon-circle" aria-hidden="true">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                      <line x1="16" y1="13" x2="8" y2="13" />
                      <line x1="16" y1="17" x2="8" y2="17" />
                    </svg>
                  </div>
                  <h3>Ready for Analysis</h3>
                  <p>
                    Submit a news article on the left to inspect its predicted classification and
                    model confidence score.
                  </p>
                </div>
              ) : (
                <div className="result">
                  <div className={`result-banner ${isReal ? "real" : "fake"}`}>
                    <div className="result-top-row">
                      <span className={`verdict-badge ${isReal ? "real" : "fake"}`}>
                        {isReal ? "✓ Credible Pattern" : "⚠ Suspicious Pattern"}
                      </span>
                      <span className="optional-tag">MODEL RESULT</span>
                    </div>

                    <h3 className={`verdict-heading ${isReal ? "real" : "fake"}`}>
                      {result.label} News
                    </h3>

                    <p className="verdict-summary">
                      {isReal
                        ? "The text aligns more closely with standard journalistic phrasing in the training corpus."
                        : "The text exhibits stylistic and lexical patterns associated with fabricated or sensationalized articles in the training corpus."}
                    </p>
                  </div>

                  <div className="confidence-section">
                    <div className="confidence-row">
                      <span className="confidence-label">Model confidence</span>
                      <strong className="confidence-value">{result.confidence}%</strong>
                    </div>

                    <div
                      className="meter-track"
                      role="progressbar"
                      aria-valuenow={result.confidence}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label="Model confidence score"
                    >
                      <div
                        className={`meter-fill ${isReal ? "real" : "fake"}`}
                        style={{ width: `${Math.min(100, Math.max(0, Number(result.confidence) || 0))}%` }}
                      />
                    </div>

                    <p className="confidence-note">
                      Estimated classifier probability from Logistic Regression over TF-IDF n-gram
                      features (not a guarantee of factual accuracy).
                    </p>
                  </div>

                  {result.persistence && (
                    <div className="persistence-box">
                      <span>Database Persistence</span>
                      <span
                        className={`persistence-tag ${
                          result.persistence.saved ? "saved" : "skipped"
                        }`}
                      >
                        {result.persistence.saved
                          ? `Saved (#${result.persistence.prediction_id})`
                          : "Not Saved (Stateless)"}
                      </span>
                    </div>
                  )}

                  <div className="methodology-note">
                    <strong>Important Limitation:</strong> This prediction reflects statistical text
                    patterns rather than live fact-checking. Always cross-verify claims with primary
                    sources.
                  </div>
                </div>
              )}
            </section>

            {recentItems.length > 0 && (
              <section className="card" aria-labelledby="recent-heading">
                <div className="card-header">
                  <div className="card-title-group">
                    <h2 id="recent-heading">Recent Analyses</h2>
                    <p>
                      {historySource === "mysql"
                        ? "Persisted in MySQL database"
                        : "Current browser session history (stateless mode)"}
                    </p>
                  </div>
                </div>

                <ul className="history-list">
                  {recentItems.map((item, idx) => (
                    <li key={item.prediction_id || idx} className="history-item">
                      <div className="history-item-main">
                        <p className="history-headline">{item.headline}</p>
                        <p className="history-meta">
                          Confidence: {item.confidence}%{" "}
                          {item.savedToDb === false ? "• Session only" : ""}
                        </p>
                      </div>
                      <span
                        className={`history-badge ${
                          item.label === "Real" ? "real" : "fake"
                        }`}
                      >
                        {item.label}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        </div>
      </main>

      <footer className="app-footer">
        <div className="footer-inner">
          <p className="footer-disclaimer">
            This tool identifies patterns learned from its training dataset. Its prediction is not
            proof that a news story is true or false.
          </p>
          <span className="footer-tech">React 19 • Flask • scikit-learn 1.6.1 • MySQL</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
