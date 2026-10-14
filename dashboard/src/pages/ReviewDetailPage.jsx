import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Zap,
  CheckCircle,
  XCircle,
  Clock,
  Sparkles,
} from "lucide-react";
import { fetchReview, fetchReviewExplain, overrideReview } from "../api";

export default function ReviewDetailPage() {
  const { id } = useParams();
  const queryClient = useQueryClient();

  const [moderatorId, setModeratorId] = useState("mod-01");
  const [overrideNote, setOverrideNote] = useState("");
  const [showOverrideForm, setShowOverrideForm] = useState(false);
  const [overrideAction, setOverrideAction] = useState("approve");
  const [overrideSuccessMsg, setOverrideSuccessMsg] = useState(null);

  // Fetch Review details
  const {
    data: review,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["review", id],
    queryFn: () => fetchReview(id),
  });

  // Query for LIME explanation (enabled on-demand)
  const [limeRequested, setLimeRequested] = useState(false);
  const {
    data: limeData,
    isLoading: limeLoading,
    isError: limeError,
  } = useQuery({
    queryKey: ["review-explain", id],
    queryFn: () => fetchReviewExplain(id),
    enabled: limeRequested,
  });

  // Mutation for Moderator Override
  const overrideMutation = useMutation({
    mutationFn: (payload) => overrideReview(id, payload),
    onSuccess: (data) => {
      queryClient.invalidateQueries(["review", id]);
      queryClient.invalidateQueries(["reviews"]);
      setShowOverrideForm(false);
      setOverrideSuccessMsg(`Review successfully ${data.action}d by ${data.moderator_id}`);
      setTimeout(() => setOverrideSuccessMsg(null), 5000);
    },
  });

  const handleOverrideSubmit = (e) => {
    e.preventDefault();
    overrideMutation.mutate({
      moderator_id: moderatorId.trim() || "mod-01",
      action: overrideAction,
      note: overrideNote.trim() || undefined,
    });
  };

  if (isLoading) {
    return (
      <div>
        <header className="page-header">
          <Link to="/reviews" className="btn btn-outline" style={{ gap: 4 }}>
            <ArrowLeft style={{ width: 14, height: 14 }} /> Back to Queue
          </Link>
        </header>
        <div className="page-body">
          <div className="loading-text">Loading review details...</div>
        </div>
      </div>
    );
  }

  if (isError || !review) {
    return (
      <div>
        <header className="page-header">
          <Link to="/reviews" className="btn btn-outline" style={{ gap: 4 }}>
            <ArrowLeft style={{ width: 14, height: 14 }} /> Back to Queue
          </Link>
        </header>
        <div className="page-body">
          <div className="error-text">
            Failed to load review: {error?.message || "Review not found."}
          </div>
        </div>
      </div>
    );
  }

  const score = review.score != null ? Number(review.score) : null;
  const isQuarantined = review.status === "quarantined";
  const rules = review.explanation?.rules || [];
  const localExplanation = limeData?.lime_explanation?.local_explanation || [];

  return (
    <div>
      <header className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <Link to="/reviews" className="btn btn-outline" style={{ gap: 4 }}>
            <ArrowLeft style={{ width: 14, height: 14 }} /> Back
          </Link>
          <div>
            <h1 className="page-title">
              Review <span className="mono">{review.id}</span>
            </h1>
            <p className="page-subtitle">
              Submitted by <span className="mono">{review.user_id}</span> •{" "}
              {new Date(review.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className={`badge badge-${review.status}`} style={{ fontSize: "13px", padding: "4px 10px" }}>
            {review.status?.toUpperCase()}
          </span>
          <button
            className="btn btn-primary"
            onClick={() => {
              setOverrideAction("approve");
              setShowOverrideForm(true);
            }}
          >
            <CheckCircle style={{ width: 14, height: 14 }} /> Approve
          </button>
          <button
            className="btn btn-danger"
            onClick={() => {
              setOverrideAction("reject");
              setShowOverrideForm(true);
            }}
          >
            <XCircle style={{ width: 14, height: 14 }} /> Reject
          </button>
        </div>
      </header>

      <div className="page-body">
        {overrideSuccessMsg && (
          <div className="alert-banner info">
            <CheckCircle style={{ width: 16, height: 16 }} />
            <span>{overrideSuccessMsg}</span>
          </div>
        )}

        {/* Override Modal / Inline Form */}
        {showOverrideForm && (
          <div className="card" style={{ marginBottom: 20, border: "2px solid var(--accent)" }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
              Moderator Action: {overrideAction.toUpperCase()}
            </h3>
            <form onSubmit={handleOverrideSubmit}>
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 14 }}>
                <div className="filter-group">
                  <label className="filter-label">Moderator ID</label>
                  <input
                    type="text"
                    value={moderatorId}
                    onChange={(e) => setModeratorId(e.target.value)}
                    required
                  />
                </div>
                <div className="filter-group" style={{ flex: 1, minWidth: 240 }}>
                  <label className="filter-label">Audit Note (Reason)</label>
                  <input
                    type="text"
                    placeholder="Provide justification for audit log..."
                    value={overrideNote}
                    onChange={(e) => setOverrideNote(e.target.value)}
                  />
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setShowOverrideForm(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={`btn ${overrideAction === "approve" ? "btn-primary" : "btn-danger"}`}
                  disabled={overrideMutation.isPending}
                >
                  Confirm {overrideAction === "approve" ? "Approval" : "Rejection"}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Score & Status Overview Cards */}
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">Composite Fraud Score</div>
            <div className={`stat-value ${score >= 0.7 ? "danger" : score >= 0.4 ? "" : "accent"}`}>
              {score != null ? score.toFixed(4) : "N/A"}
            </div>
            <div style={{ fontSize: "11.5px", color: "var(--muted)", marginTop: 4 }}>
              Threshold: 0.70 (Quarantine)
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Rating Given</div>
            <div className="stat-value" style={{ color: "var(--ink)" }}>
              {"★".repeat(review.rating)}
              <span style={{ color: "var(--border)" }}>{"★".repeat(5 - review.rating)}</span>
            </div>
            <div style={{ fontSize: "11.5px", color: "var(--muted)", marginTop: 4 }}>
              {review.rating} of 5 stars
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Rules Triggered</div>
            <div className={`stat-value ${rules.length > 0 ? "danger" : "accent"}`}>
              {rules.length}
            </div>
            <div style={{ fontSize: "11.5px", color: "var(--muted)", marginTop: 4 }}>
              Heuristic flags raised
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Inference Mode</div>
            <div className="stat-value" style={{ fontSize: "16px", marginTop: 4 }}>
              {review.fallback ? (
                <span style={{ color: "var(--warning)" }}>Fallback Mode</span>
              ) : (
                <span style={{ color: "var(--accent)" }}>DistilBERT ONNX</span>
              )}
            </div>
            <div style={{ fontSize: "11.5px", color: "var(--muted)", marginTop: 4 }}>
              {review.fallback ? "Model offline, rule backup" : "Active quantized engine"}
            </div>
          </div>
        </div>

        {/* Main Content Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* Left Column: Review Text & Heuristics */}
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Review Content Card */}
            <div className="card">
              <h2 className="chart-title">Review Content</h2>
              <div
                style={{
                  background: "var(--bg)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  padding: "16px",
                  fontSize: "14px",
                  lineHeight: "1.6",
                  color: "var(--ink)",
                  fontStyle: "normal",
                  whiteSpace: "pre-wrap",
                }}
              >
                "{review.text}"
              </div>

              <div style={{ marginTop: 14, display: "flex", gap: 16, fontSize: "12px", color: "var(--muted)" }}>
                <span>Length: {review.text.length} chars</span>
                <span>Words: {review.text.split(/\s+/).filter(Boolean).length}</span>
              </div>
            </div>

            {/* Heuristic Rule Violations */}
            <div className="card">
              <h2 className="chart-title">Heuristic Rule Analysis</h2>
              {rules.length === 0 ? (
                <div style={{ color: "var(--muted)", fontSize: "13px", padding: "12px 0" }}>
                  No heuristic rules violated. Review passed all pattern checks.
                </div>
              ) : (
                <ul className="rule-list">
                  {rules.map((r, idx) => (
                    <li key={idx} className="rule-item">
                      <div className="rule-item-name">{r.rule}</div>
                      <div className="rule-item-desc">{r.reason || "Rule condition matched."}</div>
                      {r.value !== undefined && (
                        <div className="rule-item-value">Measured value: {String(r.value)}</div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Right Column: LIME Explanation & System Details */}
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* LIME Explainability Card */}
            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h2 className="chart-title" style={{ margin: 0 }}>
                  LIME Token Attribution
                </h2>
                {!limeRequested && (
                  <button
                    className="btn btn-outline"
                    onClick={() => setLimeRequested(true)}
                    style={{ fontSize: "12px", padding: "4px 10px" }}
                  >
                    <Sparkles style={{ width: 13, height: 13, color: "var(--accent)" }} />
                    Compute LIME
                  </button>
                )}
              </div>

              {!limeRequested && (
                <p style={{ fontSize: "12.5px", color: "var(--muted)", lineHeight: 1.5 }}>
                  Click "Compute LIME" to generate on-demand local interpretable model explanations.
                  This calculates token-level feature attributions for this review.
                </p>
              )}

              {limeLoading && (
                <div className="loading-text">
                  Perturbing text samples and estimating token weights...
                </div>
              )}

              {limeError && (
                <div className="error-text">
                  Failed to compute LIME explanation.
                </div>
              )}

              {limeData?.lime_explanation?.error && (
                <div className="alert-banner warning">
                  <AlertTriangle style={{ width: 16, height: 16 }} />
                  <span>{limeData.lime_explanation.error}</span>
                </div>
              )}

              {localExplanation.length > 0 && (
                <div>
                  <p style={{ fontSize: "12px", color: "var(--muted)", marginBottom: 12 }}>
                    Weights indicate how strongly each word pushed the prediction toward Fraud (Red) vs Legit (Green):
                  </p>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {localExplanation.map((item, idx) => {
                      const isFraudPush = item.importance > 0;
                      const maxImp = Math.max(...localExplanation.map((x) => Math.abs(x.importance))) || 1;
                      const barWidth = Math.min(Math.round((Math.abs(item.importance) / maxImp) * 100), 100);

                      return (
                        <div key={idx} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <span
                            className="mono"
                            style={{
                              width: 90,
                              fontSize: "12px",
                              fontWeight: 600,
                              textAlign: "right",
                              color: isFraudPush ? "var(--danger)" : "var(--accent)",
                            }}
                          >
                            {item.word}
                          </span>
                          <div style={{ flex: 1, height: 16, background: "var(--bg)", borderRadius: 3, position: "relative" }}>
                            <div
                              style={{
                                width: `${barWidth}%`,
                                height: "100%",
                                background: isFraudPush ? "var(--danger)" : "var(--accent)",
                                borderRadius: 3,
                              }}
                            />
                          </div>
                          <span
                            className="mono"
                            style={{ width: 50, fontSize: "11.5px", textAlign: "right", color: "var(--muted)" }}
                          >
                            {item.importance > 0 ? `+${item.importance.toFixed(3)}` : item.importance.toFixed(3)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Audit & Metadata Details */}
            <div className="card">
              <h2 className="chart-title">System & Audit Record</h2>
              <div className="detail-field">
                <div className="detail-label">Review ID</div>
                <div className="detail-value mono">{review.id}</div>
              </div>
              <div className="detail-field">
                <div className="detail-label">User Identifier</div>
                <div className="detail-value mono">{review.user_id}</div>
              </div>
              <div className="detail-field">
                <div className="detail-label">Created At</div>
                <div className="detail-value">{new Date(review.created_at).toISOString()}</div>
              </div>
              {review.updated_at && (
                <div className="detail-field">
                  <div className="detail-label">Last Updated / Overridden</div>
                  <div className="detail-value">{new Date(review.updated_at).toISOString()}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
