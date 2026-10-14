import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  ReferenceLine,
} from "recharts";
import { ArrowRight, AlertTriangle, CheckCircle, ShieldAlert } from "lucide-react";
import { fetchStats, fetchReviews } from "../api";

export default function OverviewPage() {
  const {
    data: stats,
    isLoading: statsLoading,
    isError: statsError,
    refetch: refetchStats,
  } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
  });

  const {
    data: recentQuarantined,
    isLoading: quarLoading,
    refetch: refetchQuar,
  } = useQuery({
    queryKey: ["reviews", "recent-quarantined"],
    queryFn: () => fetchReviews({ page: 1, pageSize: 6, status: "quarantined" }),
  });

  useEffect(() => {
    const handler = () => {
      refetchStats();
      refetchQuar();
    };
    window.addEventListener("rg-refresh", handler);
    return () => window.removeEventListener("rg-refresh", handler);
  }, [refetchStats, refetchQuar]);

  if (statsLoading) {
    return (
      <div className="page-body">
        <div className="kpi-grid">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="kpi-card" style={{ height: 90 }}>
              <div className="skeleton-block" style={{ width: "60%", height: 12, marginBottom: 10 }} />
              <div className="skeleton-block" style={{ width: "40%", height: 28 }} />
            </div>
          ))}
        </div>
        <div className="card" style={{ height: 260 }}>
          <div className="skeleton-block" style={{ width: "100%", height: "100%" }} />
        </div>
      </div>
    );
  }

  if (statsError) {
    return (
      <div className="page-body">
        <div className="empty-state">
          <AlertTriangle style={{ width: 36, height: 36, color: "var(--danger)" }} />
          <h3 className="empty-state-title">Failed to load platform statistics</h3>
          <p className="empty-state-desc">
            Ensure the FastAPI backend is running and connected to MongoDB and Redis.
          </p>
          <button className="btn btn-outline" onClick={() => refetchStats()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const statusCounts = stats?.status_counts || {};
  const totalReviews = stats?.total_reviews || 0;
  const quarantinedCount = statusCounts.quarantined || 0;
  const fraudRate = stats?.fraud_rate != null ? (stats.fraud_rate * 100).toFixed(1) : "0.0";
  const avgScore = stats?.avg_score != null ? stats.avg_score.toFixed(3) : "0.000";
  const latestDrift = stats?.latest_drift;
  const timeline = stats?.daily_timeline || [];
  const scoreDistribution = stats?.score_distribution || [];

  return (
    <div className="page-body">
      {/* 1. KPI Strip */}
      <section className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Total Reviews</span>
          <span className="kpi-value">{totalReviews.toLocaleString()}</span>
          <span className="kpi-meta">All-time recorded in database</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Quarantined</span>
          <span className="kpi-value" style={{ color: "var(--danger)" }}>
            {quarantinedCount.toLocaleString()}
          </span>
          <span className="kpi-meta">Reviews flagged for inspection</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Fraud Rate</span>
          <span className="kpi-value">{fraudRate}%</span>
          <span className="kpi-meta">High risk score &gt; 0.70</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Average Score</span>
          <span className="kpi-value">{avgScore}</span>
          <span className="kpi-meta">0.0 (Legit) to 1.0 (Fraud)</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Drift Status</span>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {latestDrift?.alert ? (
              <>
                <ShieldAlert style={{ width: 18, height: 18, color: "var(--danger)" }} />
                <span className="kpi-value" style={{ color: "var(--danger)", fontSize: 18 }}>
                  DRIFT DETECTED
                </span>
              </>
            ) : (
              <>
                <CheckCircle style={{ width: 18, height: 18, color: "var(--accent)" }} />
                <span className="kpi-value" style={{ color: "var(--accent)", fontSize: 18 }}>
                  STABLE
                </span>
              </>
            )}
          </div>
          <span className="kpi-meta">
            {latestDrift ? `p = ${Number(latestDrift.p_value).toFixed(4)}` : "No drift event yet"}
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Engine Mode</span>
          <span className="kpi-value" style={{ fontSize: 18, color: "var(--accent)" }}>
            INT8 ONNX
          </span>
          <span className="kpi-meta">DistilBERT + Velocity Fusion</span>
        </div>
      </section>

      {/* 2. Charts Row: Fraud Rate Over Time + Score Histogram Overlay */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 20, marginBottom: 24 }}>
        {/* Fraud rate over time */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Daily Fraud Rate (Last 30 Days)</h2>
              <p className="card-subtitle">Ratio of quarantined reviews over total volume per day</p>
            </div>
          </div>
          <div style={{ width: "100%", height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeline} margin={{ top: 10, right: 15, left: -20, bottom: 0 }}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "var(--muted)" }}
                  tickFormatter={(val) => val.slice(5)}
                  stroke="var(--border)"
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "var(--muted)" }}
                  tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                  stroke="var(--border)"
                  domain={[0, "auto"]}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--surface)",
                    borderColor: "var(--border)",
                    borderRadius: "var(--radius)",
                    fontSize: "12px",
                    boxShadow: "none",
                  }}
                  formatter={(val) => [`${(Number(val) * 100).toFixed(1)}%`, "Fraud Rate"]}
                />
                <ReferenceLine
                  y={0.05}
                  stroke="var(--danger)"
                  strokeDasharray="4 4"
                  label={{ value: "5% Target Threshold", fill: "var(--danger)", fontSize: 10, position: "top" }}
                />
                <Line
                  type="monotone"
                  dataKey="fraud_rate"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Live vs Training Score Histogram Overlay */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Score Distribution (Live vs Reference)</h2>
              <p className="card-subtitle">20-bin histogram comparing reference dataset against current live reviews</p>
            </div>
          </div>
          <div style={{ width: "100%", height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={scoreDistribution} margin={{ top: 10, right: 15, left: -20, bottom: 0 }}>
                <XAxis
                  dataKey="bin"
                  tick={{ fontSize: 10, fill: "var(--muted)" }}
                  stroke="var(--border)"
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "var(--muted)" }}
                  tickFormatter={(val) => `${val}%`}
                  stroke="var(--border)"
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--surface)",
                    borderColor: "var(--border)",
                    borderRadius: "var(--radius)",
                    fontSize: "12px",
                    boxShadow: "none",
                  }}
                  formatter={(val, name) => [
                    `${Number(val).toFixed(1)}%`,
                    name === "live_pct" ? "Live Reviews" : "Reference Baseline",
                  ]}
                />
                <Bar dataKey="reference_pct" name="reference_pct" fill="var(--muted)" opacity={0.4} />
                <Bar dataKey="live_pct" name="live_pct" fill="var(--accent)" opacity={0.85} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* 3. Bottom Row: Recent Quarantined Reviews + Latest Drift Event */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 20 }}>
        {/* Recent Quarantined */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Recent Quarantined Reviews</h2>
              <p className="card-subtitle">Reviews flagged by heuristic velocity or NLP inference</p>
            </div>
            <Link to="/reviews?status=quarantined" className="btn btn-outline btn-sm">
              <span>View All</span>
              <ArrowRight style={{ width: 12, height: 12 }} />
            </Link>
          </div>

          {quarLoading ? (
            <div className="loading-text">Loading quarantined items...</div>
          ) : !recentQuarantined?.items || recentQuarantined.items.length === 0 ? (
            <div className="empty-state" style={{ padding: "20px" }}>
              <p className="empty-state-desc">No reviews currently quarantined.</p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Review ID</th>
                    <th>User ID</th>
                    <th>Score</th>
                    <th>Reasons</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {recentQuarantined.items.slice(0, 5).map((r) => (
                    <tr key={r.id}>
                      <td className="mono" style={{ fontSize: "12px", fontWeight: 600 }}>
                        {r.id.slice(-8)}
                      </td>
                      <td className="mono" style={{ fontSize: "12px" }}>
                        {r.user_id}
                      </td>
                      <td>
                        <span className="mono" style={{ color: "var(--danger)", fontWeight: 600 }}>
                          {r.score != null ? r.score.toFixed(2) : "N/A"}
                        </span>
                      </td>
                      <td style={{ fontSize: "11px", color: "var(--muted)" }}>
                        {r.reasons && r.reasons.length > 0
                          ? r.reasons.join(", ")
                          : "High NLP fraud score"}
                      </td>
                      <td>
                        <Link
                          to={`/reviews/${r.id}`}
                          className="btn btn-outline btn-sm"
                          style={{ padding: "3px 6px" }}
                        >
                          Inspect
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Latest Drift Telemetry Event */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Latest Drift Telemetry Event</h2>
              <p className="card-subtitle">Automated KS two-sample verification details</p>
            </div>
            <Link to="/drift" className="btn btn-outline btn-sm">
              <span>Drift Analytics</span>
              <ArrowRight style={{ width: 12, height: 12 }} />
            </Link>
          </div>

          {latestDrift ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 13 }}>
              <div
                style={{
                  padding: 12,
                  background: latestDrift.alert ? "var(--danger-light)" : "var(--accent-light)",
                  border: `1px solid ${latestDrift.alert ? "var(--danger)" : "var(--accent)"}`,
                  borderRadius: "var(--radius)",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                }}
              >
                {latestDrift.alert ? (
                  <AlertTriangle style={{ width: 20, height: 20, color: "var(--danger)" }} />
                ) : (
                  <CheckCircle style={{ width: 20, height: 20, color: "var(--accent)" }} />
                )}
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {latestDrift.alert
                      ? "Distribution Drift Detected"
                      : "Distribution Stable"}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>
                    {latestDrift.message || "Comparison against 40,000 baseline scores"}
                  </div>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div style={{ padding: 10, background: "var(--bg)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase" }}>KS Statistic</div>
                  <div className="mono" style={{ fontSize: 16, fontWeight: 600 }}>
                    {latestDrift.ks_statistic != null ? Number(latestDrift.ks_statistic).toFixed(4) : "N/A"}
                  </div>
                </div>
                <div style={{ padding: 10, background: "var(--bg)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase" }}>p-value</div>
                  <div className="mono" style={{ fontSize: 16, fontWeight: 600 }}>
                    {latestDrift.p_value != null ? Number(latestDrift.p_value).toExponential(4) : "N/A"}
                  </div>
                </div>
                <div style={{ padding: 10, background: "var(--bg)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase" }}>Reference Samples</div>
                  <div className="mono" style={{ fontSize: 15 }}>
                    {latestDrift.n_reference ? latestDrift.n_reference.toLocaleString() : "40,000"}
                  </div>
                </div>
                <div style={{ padding: 10, background: "var(--bg)", borderRadius: "var(--radius)", border: "1px solid var(--border)" }}>
                  <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase" }}>Live Batch Size</div>
                  <div className="mono" style={{ fontSize: 15 }}>
                    {latestDrift.n_live ? latestDrift.n_live.toLocaleString() : "1,000"}
                  </div>
                </div>
              </div>

              <div style={{ fontSize: 11.5, color: "var(--muted)" }}>
                Checked at: {latestDrift.checked_at ? new Date(latestDrift.checked_at).toLocaleString() : "Recent"}
              </div>
            </div>
          ) : (
            <div className="empty-state" style={{ padding: "20px" }}>
              <p className="empty-state-desc">No drift detection runs recorded yet.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
