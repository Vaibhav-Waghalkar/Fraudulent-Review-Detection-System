import { useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Sparkles,
  Clock,
  History,
  ShieldAlert,
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

  // Query for LIME explanation (enabled on-demand or preloaded)
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
      queryClient.invalidateQueries({ queryKey: ["review", id] });
      queryClient.invalidateQueries({ queryKey: ["reviews"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
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

  // Build LIME weights lookup map
  const limeWeights = useMemo(() => {
    const weights = {};
    const localExp = limeData?.lime_explanation?.local_explanation || [];
    localExp.forEach(([word, weight]) => {
      weights[word.toLowerCase()] = weight;
    });
    return weights;
  }, [limeData]);

  // Max weight for normalizing color opacity
  const maxLimeWeight = useMemo(() => {
    const localExp = limeData?.lime_explanation?.local_explanation || [];
    const vals = localExp.map(([, w]) => Math.abs(w));
    return vals.length > 0 ? Math.max(...vals, 0.05) : 0.05;
  }, [limeData]);

  if (isLoading) {
    return (
      <div className="page-body">
        <div className="card" style={{ height: 250 }}>
          <div className="skeleton-block" style={{ width: "100%", height: "100%" }} />
        </div>
      </div>
    );
  }

  if (isError || !review) {
    return (
      <div className="page-body">
        <div className="empty-state">
          <ShieldAlert style={{ width: 36, height: 36, color: "var(--danger)" }} />
          <h3 className="empty-state-title">Failed to load review</h3>
          <p className="empty-state-desc">{error?.message || "Review record not found in MongoDB."}</p>
          <Link to="/reviews" className="btn btn-outline btn-sm">
            Back to Queue
          </Link>
        </div>
      </div>
    );
  }

  const score = review.score != null ? Number(review.score) : 0.0;
  const scorePct = Math.round(score * 100);
  const nlpScore = review.nlp_score != null ? Number(review.nlp_score) : score;
  const ruleScore = review.rule_score != null ? Number(review.rule_score) : 0.0;
  const rules = review.explanation?.rules || [];

  // Parse review words for inline LIME highlights
  const words = review.text.split(/(\s+|[.,!?;:()]+)/);

  return (
    <div className="page-body">
      {/* Top action row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <Link to="/reviews" className="btn btn-outline btn-sm">
          <ArrowLeft style={{ width: 13, height: 13 }} />
          <span>Back to Reviews</span>
        </Link>

        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => {
              setOverrideAction("approve");
              setShowOverrideForm(true);
            }}
          >
            <CheckCircle style={{ width: 13, height: 13 }} />
            <span>Approve Review</span>
          </button>
          <button
            type="button"
            className="btn btn-danger btn-sm"
            onClick={() => {
              setOverrideAction("reject");
              setShowOverrideForm(true);
            }}
          >
            <XCircle style={{ width: 13, height: 13 }} />
            <span>Reject Review</span>
          </button>
        </div>
      </div>

      {overrideSuccessMsg && (
        <div
          style={{
            padding: "10px 14px",
            background: "var(--accent-light)",
            border: "1px solid var(--accent)",
            borderRadius: "var(--radius)",
            fontSize: "12.5px",
            color: "var(--accent)",
            fontWeight: 600,
            marginBottom: 20,
          }}
        >
          {overrideSuccessMsg}
        </div>
      )}

      {/* Override inline form */}
      {showOverrideForm && (
        <div className="card" style={{ border: "2px solid var(--accent)", marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
            Moderator Action: {overrideAction.toUpperCase()}
          </h3>
          <form onSubmit={handleOverrideSubmit}>
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 14 }}>
              <div className="filter-group">
                <label className="filter-label">Moderator ID</label>
                <input
                  type="text"
                  value={moderatorId}
                  onChange={(e) => setModeratorId(e.target.value)}
                  required
                />
              </div>
              <div className="filter-group" style={{ flex: 1, minWidth: 260 }}>
                <label className="filter-label">Audit Justification Note</label>
                <input
                  type="text"
                  placeholder="Reason for audit log..."
                  value={overrideNote}
                  onChange={(e) => setOverrideNote(e.target.value)}
                />
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => setShowOverrideForm(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className={`btn btn-sm ${overrideAction === "approve" ? "btn-primary" : "btn-danger"}`}
                disabled={overrideMutation.isPending}
              >
                Confirm {overrideAction.toUpperCase()}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Review Score</span>
          <span
            className="kpi-value"
            style={{
              color: score >= 0.7 ? "var(--danger)" : score >= 0.4 ? "var(--warning)" : "var(--accent)",
            }}
          >
            {score.toFixed(3)}
          </span>
          <span className="kpi-meta">Quarantine threshold: 0.70</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Current Status</span>
          <span className="kpi-value" style={{ fontSize: 18 }}>
            {review.status?.toUpperCase()}
          </span>
          <span className="kpi-meta">Rating: {"★".repeat(review.rating)}</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">NLP Contribution</span>
          <span className="kpi-value mono" style={{ fontSize: 18 }}>
            {(nlpScore * 0.7).toFixed(3)}
          </span>
          <span className="kpi-meta">70% NLP weight (Score: {nlpScore.toFixed(3)})</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Velocity / Rule</span>
          <span className="kpi-value mono" style={{ fontSize: 18 }}>
            {(ruleScore * 0.3).toFixed(3)}
          </span>
          <span className="kpi-meta">30% Velocity weight (Score: {ruleScore.toFixed(3)})</span>
        </div>
      </div>

      {/* Main Grid: Left = Text with inline LIME, Right = Rule Trigger Values & Audit Timeline */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(440px, 1fr))", gap: 20 }}>
        {/* Left Column: Review Text & LIME Inline Highlighting */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div className="card">
            <div className="card-header">
              <div>
                <h2 className="card-title">Review Text & LIME Attribution</h2>
                <p className="card-subtitle">
                  Inline token weights indicating pull toward Fraud (Brick red) vs Legit (Forest green)
                </p>
              </div>

              {!limeRequested && (
                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={() => setLimeRequested(true)}
                >
                  <Sparkles style={{ width: 13, height: 13, color: "var(--accent)" }} />
                  <span>Compute LIME</span>
                </button>
              )}
            </div>

            {/* Score Bar with 0.70 Threshold Marker */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>
                <span>Score Scale</span>
                <span className="mono">0.70 Threshold Marker</span>
              </div>
              <div className="score-bar-bg" style={{ height: 12 }}>
                <div className="threshold-marker" />
                <div
                  className="score-bar-fill"
                  style={{
                    width: `${scorePct}%`,
                    background: score >= 0.7 ? "var(--danger)" : score >= 0.4 ? "var(--warning)" : "var(--accent)",
                  }}
                />
              </div>
            </div>

            {/* LIME Legend */}
            <div
              style={{
                display: "flex",
                gap: 16,
                padding: "8px 12px",
                background: "var(--bg)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                marginBottom: 16,
                fontSize: "11.5px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 12, height: 12, background: "rgba(178, 58, 46, 0.45)", borderRadius: 2 }} />
                <span>Fraud Indicators (+Weight)</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 12, height: 12, background: "rgba(47, 93, 80, 0.35)", borderRadius: 2 }} />
                <span>Legitimacy Indicators (-Weight)</span>
              </div>
              <div style={{ marginLeft: "auto", color: "var(--muted)" }}>
                {limeRequested ? (limeLoading ? "Computing 500 samples..." : "LIME computed") : "Click Compute LIME to highlight"}
              </div>
            </div>

            {/* Inline Highlighted Text */}
            <div
              style={{
                padding: "16px",
                background: "var(--bg)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                fontSize: "14px",
                lineHeight: 1.8,
              }}
            >
              {words.map((chunk, i) => {
                const cleanWord = chunk.toLowerCase().replace(/[^a-z0-9]/g, "");
                const weight = limeWeights[cleanWord];

                if (weight != null && Math.abs(weight) > 0.001) {
                  const isFraud = weight > 0;
                  const intensity = Math.min(Math.abs(weight) / maxLimeWeight, 1);
                  const alpha = Math.max(0.18, intensity * 0.75);
                  const bg = isFraud
                    ? `rgba(178, 58, 46, ${alpha})`
                    : `rgba(47, 93, 80, ${alpha})`;
                  const border = isFraud ? "var(--danger)" : "var(--accent)";

                  return (
                    <span
                      key={i}
                      className="lime-token mono"
                      style={{
                        background: bg,
                        borderBottom: `2px solid ${border}`,
                        color: "var(--ink)",
                      }}
                      title={`${cleanWord}: ${weight > 0 ? "+" : ""}${weight.toFixed(4)}`}
                    >
                      {chunk}
                    </span>
                  );
                }

                return <span key={i}>{chunk}</span>;
              })}
            </div>
          </div>
        </div>

        {/* Right Column: Rule Reasons with Triggering Values + Audit Timeline */}
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Rule Reasons with Triggering Values */}
          <div className="card">
            <div className="card-header">
              <div>
                <h2 className="card-title">Triggered Heuristics & Values</h2>
                <p className="card-subtitle">Deterministic rule validations with recorded threshold conditions</p>
              </div>
            </div>

            {rules.length === 0 ? (
              <div className="empty-state" style={{ padding: "24px" }}>
                <CheckCircle style={{ width: 28, height: 28, color: "var(--accent)" }} />
                <h3 className="empty-state-title" style={{ fontSize: 13 }}>No rules triggered</h3>
                <p className="empty-state-desc">Review passed all deterministic heuristics clean.</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {rules.map((r, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: 12,
                      background: "var(--bg)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span className="mono" style={{ fontWeight: 600, color: "var(--warning)" }}>
                        {r.rule}
                      </span>
                      <span className="badge badge-quarantined">Violated</span>
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--muted)", marginBottom: 6 }}>
                      {r.description || "Deterministic rule threshold exceeded"}
                    </div>

                    {r.value !== undefined && (
                      <div
                        className="mono"
                        style={{
                          fontSize: "11px",
                          padding: "4px 8px",
                          background: "var(--surface)",
                          border: "1px solid var(--border)",
                          borderRadius: 3,
                        }}
                      >
                        Measured Value:{" "}
                        <span style={{ fontWeight: 600 }}>
                          {typeof r.value === "object" ? JSON.stringify(r.value) : String(r.value)}
                        </span>
                        {r.threshold !== undefined && (
                          <span style={{ color: "var(--muted)", marginLeft: 8 }}>
                            (Threshold: {JSON.stringify(r.threshold)})
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Audit Timeline */}
          <div className="card">
            <div className="card-header">
              <div>
                <h2 className="card-title">Audit Timeline</h2>
                <p className="card-subtitle">Chronological record of submission, scoring, and moderator decisions</p>
              </div>
              <History style={{ width: 16, height: 16, color: "var(--muted)" }} />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", gap: 12 }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: "var(--accent)", marginTop: 6 }} />
                <div>
                  <div style={{ fontSize: "12.5px", fontWeight: 600 }}>Review Created & Submitted</div>
                  <div style={{ fontSize: "11.5px", color: "var(--muted)" }}>
                    {new Date(review.created_at).toLocaleString()}
                  </div>
                  <div className="mono" style={{ fontSize: "11px", color: "var(--muted)", marginTop: 2 }}>
                    Author: {review.user_id}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: 12 }}>
                <div style={{ width: 8, height: 8, borderRadius: 2, background: "var(--accent)", marginTop: 6 }} />
                <div>
                  <div style={{ fontSize: "12.5px", fontWeight: 600 }}>Scored via INT8 Quantized Inference</div>
                  <div style={{ fontSize: "11.5px", color: "var(--muted)" }}>
                    Score: {score.toFixed(3)} | Status: {review.status}
                  </div>
                </div>
              </div>

              {review.updated_at && (
                <div style={{ display: "flex", gap: 12 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: "var(--warning)", marginTop: 6 }} />
                  <div>
                    <div style={{ fontSize: "12.5px", fontWeight: 600 }}>Last Status Update / Moderation</div>
                    <div style={{ fontSize: "11.5px", color: "var(--muted)" }}>
                      {new Date(review.updated_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
