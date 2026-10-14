import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Search,
  Filter,
  RotateCcw,
  Download,
  Copy,
  Check,
  X,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { fetchReviews, overrideReview, fetchStats } from "../api";

export default function ReviewsPage() {
  const queryClient = useQueryClient();

  // Filters & Pagination State
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [activeTab, setActiveTab] = useState("all"); // all, quarantined, reviewed, approved, rejected, pending
  const [riskPreset, setRiskPreset] = useState("all"); // all, high (>0.7), medium (0.4-0.7), low (<0.4)
  const [searchQuery, setSearchQuery] = useState("");
  const [sortField, setSortField] = useState("created_at");
  const [sortOrder, setSortOrder] = useState("desc");

  // Drawer & Keyboard Navigation State
  const [selectedReview, setSelectedReview] = useState(null);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [copiedId, setCopiedId] = useState(null);
  const [drawerModeratorId, setDrawerModeratorId] = useState("mod-01");
  const [drawerNote, setDrawerNote] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");

  // Determine effective scoreMin / scoreMax from risk presets
  let scoreMin;
  let scoreMax;
  if (riskPreset === "high") {
    scoreMin = 0.7;
  } else if (riskPreset === "medium") {
    scoreMin = 0.4;
    scoreMax = 0.7;
  } else if (riskPreset === "low") {
    scoreMax = 0.4;
  }

  // Determine effective status from tab
  const statusParam = activeTab === "all" ? undefined : activeTab;

  // Determine if search is an ID or user_id or text
  const userParam = searchQuery.startsWith("user:")
    ? searchQuery.replace("user:", "").trim()
    : undefined;

  const queryParams = {
    page,
    pageSize,
    status: statusParam,
    userId: userParam,
    scoreMin,
    scoreMax,
  };

  // Live reviews query
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["reviews", queryParams],
    queryFn: () => fetchReviews(queryParams),
    keepPreviousData: true,
  });

  // Global platform stats query for tab counts
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
  });

  useEffect(() => {
    const handler = () => refetch();
    window.addEventListener("rg-refresh", handler);
    return () => window.removeEventListener("rg-refresh", handler);
  }, [refetch]);

  let reviews = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / pageSize) || 1;

  // Client-side text search filter if user didn't use user: prefix
  if (searchQuery && !searchQuery.startsWith("user:")) {
    const q = searchQuery.toLowerCase();
    reviews = reviews.filter(
      (r) =>
        r.id.toLowerCase().includes(q) ||
        r.user_id.toLowerCase().includes(q) ||
        (r.text && r.text.toLowerCase().includes(q))
    );
  }

  // Client-side sorting
  reviews = [...reviews].sort((a, b) => {
    let valA = a[sortField];
    let valB = b[sortField];
    if (sortField === "created_at") {
      valA = new Date(valA).getTime();
      valB = new Date(valB).getTime();
    }
    if (valA < valB) return sortOrder === "asc" ? -1 : 1;
    if (valA > valB) return sortOrder === "asc" ? 1 : -1;
    return 0;
  });

  // Moderator override mutation
  const overrideMutation = useMutation({
    mutationFn: ({ id, action, note, moderator_id }) =>
      overrideReview(id, { action, note, moderator_id }),
    onSuccess: (result, variables) => {
      setActionSuccess(`Review ${variables.action.toUpperCase()} successfully.`);
      queryClient.invalidateQueries({ queryKey: ["reviews"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      if (selectedReview && selectedReview.id === variables.id) {
        setSelectedReview((prev) => ({
          ...prev,
          status: variables.action === "approve" ? "approved" : "rejected",
        }));
      }
      setTimeout(() => setActionSuccess(""), 4000);
    },
  });

  const handleAction = (action) => {
    if (!selectedReview) return;
    overrideMutation.mutate({
      id: selectedReview.id,
      action,
      note: drawerNote || `Moderator quick ${action} from review drawer`,
      moderator_id: drawerModeratorId,
    });
  };

  // Keyboard navigation: j/k move, Enter open, a approve, r reject, Esc close
  const handleKeyDown = useCallback(
    (e) => {
      // Don't intercept if user is typing in an input
      if (["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) {
        if (e.key === "Escape") {
          e.target.blur();
        }
        return;
      }

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => {
          const next = Math.min(prev + 1, reviews.length - 1);
          if (selectedReview) setSelectedReview(reviews[next]);
          return next;
        });
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => {
          const next = Math.max(prev - 1, 0);
          if (selectedReview) setSelectedReview(reviews[next]);
          return next;
        });
      } else if (e.key === "Enter") {
        if (selectedIndex >= 0 && selectedIndex < reviews.length) {
          e.preventDefault();
          setSelectedReview(reviews[selectedIndex]);
        }
      } else if (e.key === "Escape") {
        if (selectedReview) {
          e.preventDefault();
          setSelectedReview(null);
        }
      } else if (e.key === "a" || e.key === "A") {
        if (selectedReview) {
          e.preventDefault();
          handleAction("approve");
        }
      } else if (e.key === "r" || e.key === "R") {
        if (selectedReview) {
          e.preventDefault();
          handleAction("reject");
        }
      }
    },
    [reviews, selectedIndex, selectedReview]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Export filtered view to CSV
  const exportToCSV = () => {
    if (!reviews.length) return;
    const headers = ["Review ID", "User ID", "Rating", "Score", "Status", "Reasons", "Created At", "Text"];
    const rows = reviews.map((r) => [
      r.id,
      r.user_id,
      r.rating,
      r.score != null ? r.score.toFixed(3) : "",
      r.status,
      `"${(r.reasons || []).join("; ")}"`,
      r.created_at,
      `"${(r.text || "").replace(/"/g, '""')}"`,
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `reviewguard_export_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Helper for relative timestamps
  const getRelativeTime = (isoString) => {
    if (!isoString) return "";
    const date = new Date(isoString);
    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  const getStatusBadge = (status) => {
    switch (status?.toLowerCase()) {
      case "quarantined":
        return <span className="badge badge-quarantined">Quarantined</span>;
      case "needs_review":
        return <span className="badge" style={{ background: "rgba(168, 116, 26, 0.15)", color: "#c68a24", border: "1px solid rgba(168, 116, 26, 0.3)" }}>Needs Review</span>;
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

  const statusCounts = stats?.status_counts || {};
  const totalCount = stats?.total_reviews || total;

  return (
    <div className="page-body">
      {/* 1. Status Tabs with real counts */}
      <div style={{ display: "flex", gap: 6, borderBottom: "1px solid var(--border)", marginBottom: 16, overflowX: "auto" }}>
        {[
          { key: "all", label: "All Reviews", count: totalCount },
          { key: "needs_review", label: "Needs Review (0.4 - 0.7)", count: statusCounts.needs_review || 0 },
          { key: "quarantined", label: "Quarantined", count: statusCounts.quarantined || 0 },
          { key: "reviewed", label: "Reviewed", count: statusCounts.reviewed || 0 },
          { key: "approved", label: "Approved", count: statusCounts.approved || 0 },
          { key: "rejected", label: "Rejected", count: statusCounts.rejected || 0 },
          { key: "pending", label: "Pending", count: statusCounts.pending || 0 },
        ].map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => {
              setActiveTab(tab.key);
              setPage(1);
            }}
            style={{
              padding: "8px 14px",
              background: "none",
              border: "none",
              borderBottom: activeTab === tab.key ? "2px solid var(--accent)" : "2px solid transparent",
              color: activeTab === tab.key ? "var(--ink)" : "var(--muted)",
              fontWeight: activeTab === tab.key ? 600 : 500,
              fontSize: "13px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 8,
              whiteSpace: "nowrap",
            }}
          >
            <span>{tab.label}</span>
            <span
              className="mono"
              style={{
                fontSize: "11px",
                padding: "1px 6px",
                borderRadius: 3,
                background: activeTab === tab.key ? "var(--accent-light)" : "var(--bg)",
                color: activeTab === tab.key ? "var(--accent)" : "var(--muted)",
              }}
            >
              {tab.count.toLocaleString()}
            </span>
          </button>
        ))}
      </div>

      {/* 2. Controls Bar: Risk presets, Search, Sorting, Export, Reset */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
          {/* Risk Presets */}
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ fontSize: "11px", color: "var(--muted)", fontWeight: 600, textTransform: "uppercase" }}>
              Risk:
            </span>
            {[
              { key: "all", label: "All" },
              { key: "high", label: "High (>0.7)" },
              { key: "medium", label: "Med (0.4-0.7)" },
              { key: "low", label: "Low (<0.4)" },
            ].map((p) => (
              <button
                key={p.key}
                type="button"
                className={`btn btn-sm ${riskPreset === p.key ? "btn-primary" : "btn-outline"}`}
                onClick={() => {
                  setRiskPreset(p.key);
                  setPage(1);
                }}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Search Input */}
          <div style={{ position: "relative", width: 230 }}>
            <Search
              style={{
                position: "absolute",
                left: 8,
                top: "50%",
                transform: "translateY(-50%)",
                width: 14,
                height: 14,
                color: "var(--muted)",
              }}
            />
            <input
              type="text"
              placeholder="Search id, user, text..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ paddingLeft: 28, width: "100%" }}
            />
          </div>

          {/* Sort Selector */}
          <select
            value={`${sortField}-${sortOrder}`}
            onChange={(e) => {
              const [field, order] = e.target.value.split("-");
              setSortField(field);
              setSortOrder(order);
            }}
            style={{ width: 160 }}
          >
            <option value="created_at-desc">Newest First</option>
            <option value="created_at-asc">Oldest First</option>
            <option value="score-desc">Highest Score</option>
            <option value="score-asc">Lowest Score</option>
            <option value="rating-desc">Highest Rating</option>
            <option value="rating-asc">Lowest Rating</option>
          </select>

          {/* Reset button */}
          {(riskPreset !== "all" || searchQuery || activeTab !== "all") && (
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={() => {
                setActiveTab("all");
                setRiskPreset("all");
                setSearchQuery("");
                setPage(1);
              }}
              title="Reset all filters"
            >
              <RotateCcw style={{ width: 12, height: 12 }} />
              <span>Reset</span>
            </button>
          )}
        </div>

        {/* Export & Keyboard hint */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: "11px", color: "var(--muted)" }}>
            Keys: <kbd className="mono">j</kbd>/<kbd className="mono">k</kbd> move, <kbd className="mono">Enter</kbd> open, <kbd className="mono">a</kbd>/<kbd className="mono">r</kbd> act
          </span>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={exportToCSV}
            title="Export filtered records as CSV"
          >
            <Download style={{ width: 13, height: 13 }} />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* 3. Table of Reviews */}
      {isLoading ? (
        <div className="card" style={{ height: 350 }}>
          <div className="skeleton-block" style={{ width: "100%", height: "100%" }} />
        </div>
      ) : isError ? (
        <div className="empty-state">
          <ShieldAlert style={{ width: 36, height: 36, color: "var(--danger)" }} />
          <h3 className="empty-state-title">Failed to load reviews</h3>
          <p className="empty-state-desc">{error?.message || "Check network connection"}</p>
        </div>
      ) : reviews.length === 0 ? (
        <div className="empty-state">
          <Filter style={{ width: 36, height: 36, color: "var(--muted)" }} />
          <h3 className="empty-state-title">No reviews match criteria</h3>
          <p className="empty-state-desc">
            No records match the active status tab or risk preset. Try clearing your filters.
          </p>
        </div>
      ) : (
        <div className="table-container" style={{ maxHeight: "calc(100vh - 310px)" }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 30 }} />
                <th>Review ID</th>
                <th>User ID</th>
                <th>Rating</th>
                <th>Fraud Score</th>
                <th>Status</th>
                <th>Heuristics</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {reviews.map((r, index) => {
                const score = r.score != null ? Number(r.score) : null;
                const scorePct = score != null ? Math.round(score * 100) : 0;
                let riskClass = "risk-low";
                if (score >= 0.7) riskClass = "risk-high";
                else if (score >= 0.4) riskClass = "risk-medium";

                const isSelected = selectedReview?.id === r.id || selectedIndex === index;

                return (
                  <tr
                    key={r.id}
                    className={`table-row-clickable ${isSelected ? "table-row-selected" : ""}`}
                    onClick={() => {
                      setSelectedIndex(index);
                      setSelectedReview(r);
                    }}
                  >
                    {/* 3px left risk marker */}
                    <td style={{ padding: 0, width: 4, position: "relative" }}>
                      <div className={`risk-marker ${riskClass}`} />
                    </td>

                    {/* Review ID with copy button */}
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span className="mono" style={{ fontWeight: 600 }}>
                          {r.id.slice(-8)}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(r.id, r.id);
                          }}
                          style={{
                            background: "none",
                            border: "none",
                            cursor: "pointer",
                            padding: 2,
                            color: "var(--muted)",
                          }}
                          title="Copy full review ID"
                        >
                          {copiedId === r.id ? (
                            <Check style={{ width: 12, height: 12, color: "var(--accent)" }} />
                          ) : (
                            <Copy style={{ width: 12, height: 12 }} />
                          )}
                        </button>
                      </div>
                    </td>

                    <td className="mono" style={{ fontSize: "12px" }}>
                      {r.user_id}
                    </td>

                    <td>
                      <span style={{ fontWeight: 600 }}>{"★".repeat(r.rating)}</span>
                      <span style={{ color: "var(--border)" }}>{"★".repeat(5 - r.rating)}</span>
                    </td>

                    {/* Fraud score with threshold marker at 0.7 */}
                    <td style={{ minWidth: 130 }}>
                      {score != null ? (
                        <div className="score-cell">
                          <span
                            className="score-value"
                            style={{
                              color: score >= 0.7 ? "var(--danger)" : score >= 0.4 ? "var(--warning)" : "var(--accent)",
                            }}
                          >
                            {score.toFixed(2)}
                          </span>
                          <div className="score-bar-bg" title={`Score: ${score.toFixed(3)} (Threshold: 0.70)`}>
                            <div className="threshold-marker" />
                            <div
                              className="score-bar-fill"
                              style={{
                                width: `${scorePct}%`,
                                background:
                                  score >= 0.7 ? "var(--danger)" : score >= 0.4 ? "var(--warning)" : "var(--accent)",
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
                          style={{ fontSize: "10.5px" }}
                        >
                          {r.reasons.length} {r.reasons.length > 1 ? "rules" : "rule"}
                        </span>
                      ) : r.fallback ? (
                        <span className="badge badge-pending">Fallback</span>
                      ) : (
                        <span style={{ color: "var(--muted)", fontSize: "11px" }}>None</span>
                      )}
                    </td>

                    {/* Relative timestamp with full date hover */}
                    <td
                      style={{ fontSize: "12px", color: "var(--muted)", whiteSpace: "nowrap" }}
                      title={new Date(r.created_at).toLocaleString()}
                    >
                      {getRelativeTime(r.created_at)}
                    </td>

                    <td>
                      <div style={{ display: "flex", gap: 6 }}>
                        <Link
                          to={`/reviews/${r.id}`}
                          className="btn btn-outline btn-sm"
                          onClick={(e) => e.stopPropagation()}
                          title="Open full page detail"
                        >
                          <ExternalLink style={{ width: 12, height: 12 }} />
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 4. Pagination */}
      <div className="pagination">
        <div>
          Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total.toLocaleString()} reviews
        </div>

        <div className="pagination-controls">
          <label style={{ fontSize: "11.5px", color: "var(--muted)" }}>Per page:</label>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
            style={{ padding: "3px 6px", fontSize: "12px" }}
          >
            <option value={15}>15</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>

          <button
            type="button"
            className="btn btn-outline btn-sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            <ChevronLeft style={{ width: 14, height: 14 }} />
            <span>Prev</span>
          </button>

          <span className="mono" style={{ padding: "0 6px" }}>
            {page} / {totalPages}
          </span>

          <button
            type="button"
            className="btn btn-outline btn-sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            <span>Next</span>
            <ChevronRight style={{ width: 14, height: 14 }} />
          </button>
        </div>
      </div>

      {/* 5. Right Side Drawer for Selected Review */}
      {selectedReview && (
        <>
          <div className="drawer-backdrop" onClick={() => setSelectedReview(null)} />
          <aside className="drawer" aria-label="Review Inspection Drawer">
            <div className="drawer-header">
              <div>
                <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>
                  Quick Inspection
                </div>
                <div className="mono" style={{ fontSize: "14px", fontWeight: 600 }}>
                  {selectedReview.id}
                </div>
              </div>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => setSelectedReview(null)}
                title="Close drawer (Esc)"
              >
                <X style={{ width: 14, height: 14 }} />
              </button>
            </div>

            <div className="drawer-body">
              {actionSuccess && (
                <div
                  style={{
                    padding: "10px 12px",
                    background: "var(--accent-light)",
                    border: "1px solid var(--accent)",
                    borderRadius: "var(--radius)",
                    fontSize: "12px",
                    color: "var(--accent)",
                    fontWeight: 600,
                  }}
                >
                  {actionSuccess}
                </div>
              )}

              {/* Status & Rating */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Status: </span>
                  {getStatusBadge(selectedReview.status)}
                </div>
                <div>
                  <span style={{ fontWeight: 600 }}>{"★".repeat(selectedReview.rating)}</span>
                  <span style={{ color: "var(--border)" }}>{"★".repeat(5 - selectedReview.rating)}</span>
                </div>
              </div>

              {/* Score bar with 0.70 threshold */}
              <div style={{ padding: 12, background: "var(--bg)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>
                    Fraud Probability
                  </span>
                  <span className="mono" style={{ fontWeight: 600 }}>
                    {selectedReview.score != null ? selectedReview.score.toFixed(3) : "N/A"}
                  </span>
                </div>
                <div className="score-bar-bg" style={{ height: 10 }}>
                  <div className="threshold-marker" />
                  <div
                    className="score-bar-fill"
                    style={{
                      width: `${Math.round((selectedReview.score || 0) * 100)}%`,
                      background:
                        (selectedReview.score || 0) >= 0.7
                          ? "var(--danger)"
                          : (selectedReview.score || 0) >= 0.4
                          ? "var(--warning)"
                          : "var(--accent)",
                    }}
                  />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: "10px", color: "var(--muted)" }}>
                  <span>0.00 (Legitimate)</span>
                  <span style={{ color: "var(--danger)", fontWeight: 600 }}>0.70 (Quarantine)</span>
                  <span>1.00</span>
                </div>
              </div>

              {/* Review Text */}
              <div>
                <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", marginBottom: 6 }}>
                  Review Text
                </div>
                <div
                  style={{
                    padding: 12,
                    background: "var(--bg)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius)",
                    fontSize: "13px",
                    lineHeight: 1.6,
                  }}
                >
                  {selectedReview.text}
                </div>
              </div>

              {/* Triggered reasons */}
              <div>
                <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", marginBottom: 6 }}>
                  Triggered Rule Heuristics
                </div>
                {selectedReview.reasons && selectedReview.reasons.length > 0 ? (
                  <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 6 }}>
                    {selectedReview.reasons.map((r, i) => (
                      <li
                        key={i}
                        className="mono"
                        style={{
                          fontSize: "11.5px",
                          padding: "6px 8px",
                          background: "var(--danger-light)",
                          border: "1px solid var(--danger)",
                          color: "var(--danger)",
                          borderRadius: 3,
                        }}
                      >
                        {r}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div style={{ fontSize: "12px", color: "var(--muted)" }}>
                    No deterministic rules triggered. Scored purely by transformer embeddings.
                  </div>
                )}
              </div>

              {/* Moderator Decision Box */}
              <div style={{ marginTop: "auto", borderTop: "1px solid var(--border)", paddingTop: 14 }}>
                <div style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", marginBottom: 8 }}>
                  Moderator Decision Action
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
                  <input
                    type="text"
                    placeholder="Moderator ID"
                    value={drawerModeratorId}
                    onChange={(e) => setDrawerModeratorId(e.target.value)}
                    style={{ fontSize: "12px" }}
                  />
                  <input
                    type="text"
                    placeholder="Audit justification note..."
                    value={drawerNote}
                    onChange={(e) => setDrawerNote(e.target.value)}
                    style={{ fontSize: "12px" }}
                  />
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ flex: 1, justifyContent: "center" }}
                    onClick={() => handleAction("approve")}
                    disabled={overrideMutation.isPending}
                  >
                    <CheckCircle style={{ width: 14, height: 14 }} />
                    <span>Approve (a)</span>
                  </button>

                  <button
                    type="button"
                    className="btn btn-danger"
                    style={{ flex: 1, justifyContent: "center" }}
                    onClick={() => handleAction("reject")}
                    disabled={overrideMutation.isPending}
                  >
                    <XCircle style={{ width: 14, height: 14 }} />
                    <span>Reject (r)</span>
                  </button>
                </div>
              </div>
            </div>

            <div className="drawer-footer">
              <Link
                to={`/reviews/${selectedReview.id}`}
                className="btn btn-outline btn-sm"
                style={{ width: "100%", justifyContent: "center" }}
              >
                <span>Open Full LIME Explanation</span>
                <ExternalLink style={{ width: 12, height: 12 }} />
              </Link>
            </div>
          </aside>
        </>
      )}
    </div>
  );
}
