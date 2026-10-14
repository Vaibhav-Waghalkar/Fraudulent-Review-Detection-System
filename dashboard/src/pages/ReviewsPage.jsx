import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Search,
  Filter,
  AlertTriangle,
  CheckCircle,
  Clock,
  ArrowRight,
  ShieldAlert,
  RotateCcw,
} from "lucide-react";
import { fetchReviews } from "../api";

export default function ReviewsPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [statusFilter, setStatusFilter] = useState("");
  const [userIdFilter, setUserIdFilter] = useState("");
  const [scoreMin, setScoreMin] = useState("");
  const [scoreMax, setScoreMax] = useState("");

  const queryParams = {
    page,
    pageSize,
    status: statusFilter || undefined,
    userId: userIdFilter.trim() || undefined,
    scoreMin: scoreMin !== "" ? Number(scoreMin) : undefined,
    scoreMax: scoreMax !== "" ? Number(scoreMax) : undefined,
  };

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reviews", queryParams],
    queryFn: () => fetchReviews(queryParams),
    keepPreviousData: true,
  });

  const reviews = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / pageSize) || 1;

  const handleResetFilters = () => {
    setStatusFilter("");
    setUserIdFilter("");
    setScoreMin("");
    setScoreMax("");
    setPage(1);
  };

  const getScoreColor = (score) => {
    if (score == null) return "var(--muted)";
    if (score >= 0.7) return "var(--danger)";
    if (score >= 0.4) return "var(--warning)";
    return "var(--accent)";
  };

  const getStatusBadge = (status) => {
    switch (status?.toLowerCase()) {
      case "quarantined":
        return <span className="badge badge-quarantined">Quarantined</span>;
      case "reviewed":
        return <span className="badge badge-reviewed">Reviewed</span>;
      case "approved":
        return <span className="badge badge-approved">Approved</span>;
      case "rejected":
        return <span className="badge badge-rejected">Rejected</span>;
      default:
        return <span className="badge badge-pending">Pending</span>;
    }
  };

  return (
    <div>
      <header className="page-header">
        <h1 className="page-title">Review Fraud Queue</h1>
        <p className="page-subtitle">
          Real-time review stream scored by DistilBERT ONNX and velocity heuristics
        </p>
      </header>

      <div className="page-body">
        {/* Filters */}
        <div className="filters-bar">
          <div className="filter-group">
            <label className="filter-label" htmlFor="status-select">Status</label>
            <select
              id="status-select"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All Statuses</option>
              <option value="quarantined">Quarantined</option>
              <option value="reviewed">Reviewed</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="pending">Pending</option>
            </select>
          </div>

          <div className="filter-group">
            <label className="filter-label" htmlFor="user-id-input">User ID</label>
            <input
              id="user-id-input"
              type="text"
              placeholder="Filter by user..."
              value={userIdFilter}
              onChange={(e) => {
                setUserIdFilter(e.target.value);
                setPage(1);
              }}
              style={{ width: "160px" }}
            />
          </div>

          <div className="filter-group">
            <label className="filter-label" htmlFor="score-min-input">Min Score</label>
            <input
              id="score-min-input"
              type="number"
              step="0.05"
              min="0"
              max="1"
              placeholder="0.0"
              value={scoreMin}
              onChange={(e) => {
                setScoreMin(e.target.value);
                setPage(1);
              }}
              style={{ width: "90px" }}
            />
          </div>

          <div className="filter-group">
            <label className="filter-label" htmlFor="score-max-input">Max Score</label>
            <input
              id="score-max-input"
              type="number"
              step="0.05"
              min="0"
              max="1"
              placeholder="1.0"
              value={scoreMax}
              onChange={(e) => {
                setScoreMax(e.target.value);
                setPage(1);
              }}
              style={{ width: "90px" }}
            />
          </div>

          <button
            type="button"
            className="btn btn-outline"
            onClick={handleResetFilters}
            title="Reset filters"
          >
            <RotateCcw style={{ width: "14px", height: "14px" }} />
            Reset
          </button>
        </div>

        {/* Content States */}
        {isLoading && <div className="loading-text">Loading reviews...</div>}

        {isError && (
          <div className="error-text">
            Failed to load reviews: {error?.message || "Unknown error"}
          </div>
        )}

        {!isLoading && !isError && reviews.length === 0 && (
          <div className="empty-state">
            <ShieldAlert style={{ width: 36, height: 36, color: "var(--muted)", margin: "0 auto 12px" }} />
            <h3 className="empty-state-title">No reviews found</h3>
            <p className="empty-state-desc">
              No review records match your current filter settings, or the database has not been seeded yet.
              Try running <code>python scripts/seed.py</code>.
            </p>
            <button className="btn btn-outline" onClick={handleResetFilters}>
              Clear Filters
            </button>
          </div>
        )}

        {!isLoading && !isError && reviews.length > 0 && (
          <>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Review ID</th>
                    <th>User ID</th>
                    <th>Rating</th>
                    <th>Text Snippet</th>
                    <th>Fraud Score</th>
                    <th>Status</th>
                    <th>Heuristics</th>
                    <th>Created</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {reviews.map((r) => {
                    const score = r.score != null ? Number(r.score) : null;
                    const scorePct = score != null ? Math.round(score * 100) : 0;
                    const scoreColor = getScoreColor(score);
                    const snippet = r.text?.length > 45 ? `${r.text.slice(0, 45)}...` : r.text;

                    return (
                      <tr key={r.id}>
                        <td>
                          <Link
                            to={`/reviews/${r.id}`}
                            className="mono"
                            style={{ color: "var(--ink)", fontWeight: 600, textDecoration: "none" }}
                          >
                            {r.id.slice(-8)}
                          </Link>
                        </td>
                        <td className="mono">{r.user_id}</td>
                        <td>
                          <span style={{ fontWeight: 600 }}>{"★".repeat(r.rating)}</span>
                          <span style={{ color: "var(--border)" }}>{"★".repeat(5 - r.rating)}</span>
                        </td>
                        <td style={{ maxWidth: "260px", color: "var(--muted)" }} title={r.text}>
                          {snippet}
                        </td>
                        <td>
                          {score != null ? (
                            <div className="score-cell">
                              <span className="score-value" style={{ color: scoreColor }}>
                                {score.toFixed(2)}
                              </span>
                              <div className="score-bar-bg">
                                <div
                                  className="score-bar-fill"
                                  style={{
                                    width: `${scorePct}%`,
                                    background: scoreColor,
                                  }}
                                />
                              </div>
                            </div>
                          ) : (
                            <span style={{ color: "var(--muted)" }}>N/A</span>
                          )}
                        </td>
                        <td>{getStatusBadge(r.status)}</td>
                        <td>
                          {r.reasons && r.reasons.length > 0 ? (
                            <span
                              className="badge badge-quarantined"
                              title={r.reasons.join(", ")}
                            >
                              {r.reasons.length} rule{r.reasons.length > 1 ? "s" : ""}
                            </span>
                          ) : r.fallback ? (
                            <span className="badge badge-pending">Fallback</span>
                          ) : (
                            <span style={{ color: "var(--muted)", fontSize: "11px" }}>None</span>
                          )}
                        </td>
                        <td style={{ color: "var(--muted)", fontSize: "12px", whiteSpace: "nowrap" }}>
                          {new Date(r.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </td>
                        <td>
                          <Link to={`/reviews/${r.id}`} className="btn btn-outline" style={{ padding: "4px 8px", fontSize: "12px" }}>
                            Inspect
                            <ArrowRight style={{ width: "12px", height: "12px" }} />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="pagination">
              <span className="pagination-info">
                Showing {((page - 1) * pageSize) + 1} - {Math.min(page * pageSize, total)} of {total} reviews
              </span>
              <button
                className="btn btn-outline"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </button>
              <button
                className="btn btn-outline"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
