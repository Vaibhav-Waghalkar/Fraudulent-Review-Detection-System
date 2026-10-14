import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  TrendingDown,
  Clock,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { fetchDriftStatus } from "../api";

export default function DriftPage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["drift-status"],
    queryFn: fetchDriftStatus,
    refetchInterval: 30000, // Poll every 30s
  });

  const events = data?.recent_events || [];
  const pValue = data?.p_value;
  const isAlert = data?.alert;

  // Prepare chart data from recent events (reverse to chronological order)
  const chartData = [...events]
    .reverse()
    .map((evt, index) => {
      const timeStr = evt.checked_at
        ? new Date(evt.checked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        : `#${index + 1}`;
      return {
        name: timeStr,
        timestamp: evt.checked_at,
        pValue: evt.p_value != null ? Number(evt.p_value.toFixed(4)) : null,
        alert: evt.alert,
        sampleSize: evt.sample_size || 0,
      };
    })
    .filter((d) => d.pValue != null);

  return (
    <div>
      <header
        className="page-header"
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
      >
        <div>
          <h1 className="page-title">Model Drift Monitoring</h1>
          <p className="page-subtitle">
            Two-sample Kolmogorov-Smirnov test comparing live score distributions against baseline
          </p>
        </div>
        <button
          className="btn btn-outline"
          onClick={() => refetch()}
          disabled={isFetching}
          style={{ gap: 6 }}
        >
          <RefreshCw style={{ width: 14, height: 14 }} />
          {isFetching ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      <div className="page-body">
        {/* Status Banner */}
        {isAlert ? (
          <div className="alert-banner danger">
            <AlertTriangle style={{ width: 18, height: 18, flexShrink: 0 }} />
            <div>
              <strong>Model Drift Detected!</strong> {data?.message || "Prediction distribution has significantly shifted (p < 0.05). Retraining model recommended."}
            </div>
          </div>
        ) : pValue != null ? (
          <div className="alert-banner info">
            <CheckCircle2 style={{ width: 18, height: 18, flexShrink: 0 }} />
            <div>
              <strong>Distribution Stable.</strong> Live review fraud scores conform to the reference baseline (p = {pValue.toFixed(4)} &ge; 0.05).
            </div>
          </div>
        ) : (
          <div className="alert-banner warning">
            <Clock style={{ width: 18, height: 18, flexShrink: 0 }} />
            <div>
              <strong>Drift Scheduler Idle.</strong> {data?.message || "No drift events recorded yet. Run Celery beat or scripts/simulate_drift.py."}
            </div>
          </div>
        )}

        {/* Stat Cards */}
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">Latest KS p-Value</div>
            <div
              className={`stat-value ${
                pValue == null
                  ? ""
                  : pValue < 0.05
                  ? "danger"
                  : "accent"
              }`}
            >
              {pValue != null ? pValue.toFixed(4) : "N/A"}
            </div>
            <div style={{ fontSize: "11.5px", color: "var(--muted)", marginTop: 4 }}>
              Significance Threshold: 0.0500
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">System Health</div>
            <div className="stat-value" style={{ fontSize: "18px", marginTop: 4 }}>
              {isAlert ? (
                <span style={{ color: "var(--danger)" }}>DRIFT ALERT</span>
              ) : pValue != null ? (
                <span style={{ color: "var(--accent)" }}>HEALTHY</span>
              ) : (
                <span style={{ color: "var(--muted)" }}>AWAITING RUN</span>
              )}
            </div>
            <div style={{ fontSize: "11.5px", color: "var(--muted)", marginTop: 4 }}>
              KS Two-Sample Hypothesis
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Last Evaluated</div>
            <div className="stat-value" style={{ fontSize: "15px", marginTop: 6, color: "var(--ink)" }}>
              {data?.checked_at
                ? new Date(data.checked_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })
                : "Never"}
            </div>
            <div style={{ fontSize: "11.5px", color: "var(--muted)", marginTop: 4 }}>
              Periodic Celery task
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-label">Historical Checks</div>
            <div className="stat-value">{events.length}</div>
            <div style={{ fontSize: "11.5px", color: "var(--muted)", marginTop: 4 }}>
              Recent events in memory
            </div>
          </div>
        </div>

        {/* Chart Section */}
        <div className="chart-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h2 className="chart-title" style={{ margin: 0 }}>
              p-Value Trajectory (Drift Alert Threshold = 0.05)
            </h2>
            <span style={{ fontSize: "12px", color: "var(--muted)" }}>
              Values below red dashed line trigger drift alert
            </span>
          </div>

          {chartData.length > 0 ? (
            <div style={{ width: "100%", height: 260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                  <XAxis
                    dataKey="name"
                    tick={{ fill: "var(--muted)", fontSize: 11 }}
                    stroke="var(--border)"
                  />
                  <YAxis
                    domain={[0, 1]}
                    tick={{ fill: "var(--muted)", fontSize: 11 }}
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
                    formatter={(val) => [val, "p-value"]}
                  />
                  <ReferenceLine
                    y={0.05}
                    stroke="var(--danger)"
                    strokeDasharray="4 4"
                    label={{
                      value: "Threshold (0.05)",
                      fill: "var(--danger)",
                      fontSize: 11,
                      position: "right",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="pValue"
                    stroke="var(--accent)"
                    strokeWidth={2.5}
                    dot={{ r: 4, fill: "var(--accent)" }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-state" style={{ padding: "36px 0" }}>
              <Activity style={{ width: 32, height: 32, color: "var(--muted)", margin: "0 auto 8px" }} />
              <div style={{ fontSize: "13px", color: "var(--muted)" }}>
                No historical drift points plotted yet. Run drift checks to visualize trends.
              </div>
            </div>
          )}
        </div>

        {/* Drift Events History Table */}
        <div className="card" style={{ marginTop: 20 }}>
          <h2 className="chart-title">Drift Evaluation History</h2>
          {events.length === 0 ? (
            <div className="empty-state">
              <Clock style={{ width: 36, height: 36, color: "var(--muted)", margin: "0 auto 12px" }} />
              <h3 className="empty-state-title">No drift events logged</h3>
              <p className="empty-state-desc">
                The drift monitoring worker runs periodically or via manual simulation. To simulate
                drift immediately, run:
                <br />
                <code>python scripts/simulate_drift.py</code>
              </p>
            </div>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>p-Value</th>
                    <th>Status</th>
                    <th>Sample Size</th>
                    <th>Message</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((evt, idx) => {
                    const evtP = evt.p_value;
                    const alert = evt.alert;
                    return (
                      <tr key={idx}>
                        <td className="mono" style={{ whiteSpace: "nowrap" }}>
                          {evt.checked_at
                            ? new Date(evt.checked_at).toLocaleString()
                            : "N/A"}
                        </td>
                        <td>
                          <span
                            className={`mono ${
                              evtP != null && evtP < 0.05
                                ? "p-value-alert"
                                : "p-value-normal"
                            }`}
                          >
                            {evtP != null ? evtP.toFixed(4) : "N/A"}
                          </span>
                        </td>
                        <td>
                          {alert ? (
                            <span className="badge badge-quarantined">Drift Alert</span>
                          ) : (
                            <span className="badge badge-reviewed">Normal</span>
                          )}
                        </td>
                        <td className="mono">{evt.sample_size || "N/A"}</td>
                        <td style={{ color: "var(--muted)", fontSize: "12.5px" }}>
                          {evt.message || (alert ? "Drift detected" : "Distributions match baseline")}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
