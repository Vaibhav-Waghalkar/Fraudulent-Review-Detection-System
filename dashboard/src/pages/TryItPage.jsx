import { useState } from "react";
import { Play, CheckCircle2, AlertTriangle, Clock } from "lucide-react";
import { scoreBatch } from "../api";

export default function TryItPage() {
  const [text, setText] = useState("Outstanding quality! Build is sturdy, delivery was fast, highly recommend.");
  const [rating, setRating] = useState(5);
  const [velocity, setVelocity] = useState(1);
  const [userId, setUserId] = useState("user_tryit_test");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [clientLatency, setClientLatency] = useState(null);

  const handleTest = async (e) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    const t0 = performance.now();
    try {
      const data = await scoreBatch([{
        text,
        rating: Number(rating),
        user_id: userId,
      }]);
      const elapsed = performance.now() - t0;
      setClientLatency(elapsed);
      if (data && data.length > 0) {
        setResult(data[0]);
      }
    } catch (err) {
      console.error(err);
      alert("Error scoring review: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="card" style={{ maxWidth: 840, margin: "0 auto" }}>
        <h2 style={{ fontSize: 18, marginBottom: 8, fontWeight: 600 }}>Interactive Review Scoring</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: 13, marginBottom: 20 }}>
          Submit raw review payload to test real-time ONNX inference, rule heuristics, fallback status, and latency.
        </p>

        <form onSubmit={handleTest} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
              Review Text
            </label>
            <textarea
              className="input mono"
              rows={4}
              value={text}
              onChange={(e) => setText(e.target.value)}
              required
              style={{ width: "100%", resize: "vertical", fontSize: 13 }}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
                Rating (1 - 5)
              </label>
              <select
                className="input"
                value={rating}
                onChange={(e) => setRating(e.target.value)}
                style={{ width: "100%" }}
              >
                <option value={1}>1 Star</option>
                <option value={2}>2 Stars</option>
                <option value={3}>3 Stars</option>
                <option value={4}>4 Stars</option>
                <option value={5}>5 Stars</option>
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
                Simulated Velocity (reviews / day)
              </label>
              <input
                type="number"
                className="input"
                min={0}
                max={100}
                value={velocity}
                onChange={(e) => setVelocity(e.target.value)}
                style={{ width: "100%" }}
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
                User ID
              </label>
              <input
                type="text"
                className="input mono"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                style={{ width: "100%" }}
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading}
            style={{ alignSelf: "flex-start", marginTop: 8 }}
          >
            <Play style={{ width: 14, height: 14 }} />
            <span>{loading ? "Scoring..." : "Run Score Analysis"}</span>
          </button>
        </form>

        {result && (
          <div style={{ marginTop: 28, paddingTop: 24, borderTop: "1px solid var(--color-border)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, fontWeight: 600 }}>Scoring Diagnostics</h3>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <span className="mono" style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                  <Clock style={{ width: 12, height: 12, display: "inline", marginRight: 4 }} />
                  {clientLatency?.toFixed(1)} ms
                </span>
                <span className={`badge badge-${result.status === "quarantined" ? "high" : result.status === "needs_review" ? "medium" : "low"}`}>
                  {result.status}
                </span>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 20 }}>
              <div style={{ background: "var(--color-bg)", padding: 12, border: "1px solid var(--color-border)" }}>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: 4 }}>FINAL SCORE</div>
                <div className="mono" style={{ fontSize: 20, fontWeight: 600 }}>
                  {(result.score * 100).toFixed(1)}%
                </div>
              </div>
              <div style={{ background: "var(--color-bg)", padding: 12, border: "1px solid var(--color-border)" }}>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: 4 }}>MODEL FALLBACK</div>
                <div className="mono" style={{ fontSize: 14, fontWeight: 500, color: result.fallback ? "var(--color-danger)" : "var(--color-success)" }}>
                  {result.fallback ? "TRUE (rules-only)" : "FALSE (ONNX active)"}
                </div>
              </div>
              <div style={{ background: "var(--color-bg)", padding: 12, border: "1px solid var(--color-border)" }}>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginBottom: 4 }}>RECORD ID</div>
                <div className="mono" style={{ fontSize: 11, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {result.id}
                </div>
              </div>
            </div>

            <div>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>Triggered Rule Explanations:</div>
              {result.explanation?.rules && result.explanation.rules.length > 0 ? (
                <ul style={{ listStyle: "disc", paddingLeft: 20, fontSize: 13, display: "flex", flexDirection: "column", gap: 6 }}>
                  {result.explanation.rules.map((r, i) => (
                    <li key={i}>
                      <strong>{r.rule}</strong>: {r.description} (value: {typeof r.value === 'object' ? JSON.stringify(r.value) : r.value})
                    </li>
                  ))}
                </ul>
              ) : (
                <div style={{ fontSize: 13, color: "var(--color-text-muted)" }}>No heuristics triggered. Score derived purely from NLP representation.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
