import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle,
  Play,
  RotateCcw,
  Activity,
  Calendar,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  BarChart,
  Bar,
} from "recharts";
import { fetchDriftStatus, runDriftCheck, fetchStats } from "../api";

export default function DriftPage() {
  const queryClient = useQueryClient();
  const [runMessage, setRunMessage] = useState("");

  const { data: driftData, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["drift-status"],
    queryFn: fetchDriftStatus,
    refetchInterval: 15000,
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
  });

  const runMutation = useMutation({
    mutationFn: runDriftCheck,
    onSuccess: (result) => {
      setRunMessage(
        result.alert
          ? `Drift check finished: DRIFT DETECTED (p = ${Number(result.p_value).toExponential(3)}, KS = ${Number(result.ks_statistic).toFixed(4)})`
          : `Drift check finished: STABLE (p = ${Number(result.p_value).toFixed(4)}, KS = ${Number(result.ks_statistic).toFixed(4)})`
      );
      queryClient.invalidateQueries({ queryKey: ["drift-status"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      setTimeout(() => setRunMessage(""), 6000);
    },
    onError: (err) => {
      setRunMessage(`Check failed: ${err.message}`);
    },
  });

  const events = driftData?.recent_events || [];
  const latestPValue = driftData?.p_value;
  const isAlert = driftData?.alert;

  // Chart: p-values on log scale or formatted points
  // We plot log10(p_value) or direct p-value with reference at 0.05
  const chartData = [...events]
    .reverse()
    .map((evt, idx) => {
      const p = evt.p_value != null ? Number(evt.p_value) : null;
      // Clamped min for log visual
      const safeP = p != null ? Math.max(p, 1e-6) : null;
      return {
        id: idx + 1,
        time: evt.checked_at
          ? new Date(evt.checked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          : `#${idx + 1}`,
        rawP: p,
        pValue: safeP,
        ks: evt.ks_statistic != null ? Number(evt.ks_statistic).toFixed(4) : "N/A",
        source: evt.source || (evt.simulated ? "simulated" : "scheduled"),
        alert: evt.alert,
      };
    })
    .filter((d) => d.pValue != null);

  const scoreDistribution = stats?.score_distribution || [];

  return (
    <div className="page-body">
      {/* Header action button */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <span style={{ fontSize: "12px", color: "var(--muted)" }}>
            Kolmogorov-Smirnov two-sample testing against 40,000 baseline scores
          </span>
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={() => refetch()}
            title="Refresh status"
          >
            <RotateCcw style={{ width: 13, height: 13 }} />
            <span>Refresh</span>
          </button>

          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending}
            title="Execute immediate KS drift check on current reviews"
          >
            <Play style={{ width: 13, height: 13 }} />
            <span>{runMutation.isPending ? "Evaluating..." : "Run check now"}</span>
          </button>
        </div>
      </div>

      {runMessage && (
        <div
          style={{
            padding: "10px 14px",
            background: runMessage.includes("DRIFT") ? "var(--danger-light)" : "var(--accent-light)",
            border: `1px solid ${runMessage.includes("DRIFT") ? "var(--danger)" : "var(--accent)"}`,
            borderRadius: "var(--radius)",
            fontSize: "12.5px",
            color: runMessage.includes("DRIFT") ? "var(--danger)" : "var(--accent)",
            fontWeight: 600,
            marginBottom: 20,
          }}
        >
          {runMessage}
        </div>
      )}

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Current Status</span>
          <span
            className="kpi-value"
            style={{
              fontSize: 18,
              color: isAlert ? "var(--danger)" : "var(--accent)",
            }}
          >
            {isAlert ? "DRIFT DETECTED" : "DISTRIBUTION STABLE"}
          </span>
          <span className="kpi-meta">
            {isAlert ? "Score distribution shifted" : "Within confidence bounds"}
          </span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Latest p-value</span>
          <span className="kpi-value mono" style={{ fontSize: 20 }}>
            {latestPValue != null
              ? Number(latestPValue) < 1e-16
                ? "< 1e-16"
                : Number(latestPValue).toExponential(4)
              : "N/A"}
          </span>
          <span className="kpi-meta">Significance threshold &alpha; = 0.05</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Reference Baseline</span>
          <span className="kpi-value mono" style={{ fontSize: 20 }}>
            40,000
          </span>
          <span className="kpi-meta">Fixed reference_scores.npy</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Drift Check Schedule</span>
          <span className="kpi-value" style={{ fontSize: 18 }}>
            HOURLY
          </span>
          <span className="kpi-meta">Automated Celery beat task</span>
        </div>
      </div>

      {/* Charts Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 20, marginBottom: 24 }}>
        {/* p-value Trend Chart on Log Scale */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">p-value History (Log Scale)</h2>
              <p className="card-subtitle">
                Chronological p-values with labeled 0.05 significance alert line
              </p>
            </div>
          </div>

          <div style={{ width: "100%", height: 240 }}>
            {chartData.length === 0 ? (
              <div className="empty-state" style={{ height: "100%", justifyContent: "center" }}>
                <p className="empty-state-desc">No drift runs recorded. Click "Run check now".</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 15, right: 20, left: -10, bottom: 0 }}>
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 11, fill: "var(--muted)" }}
                    stroke="var(--border)"
                  />
                  <YAxis
                    scale="log"
                    domain={[1e-6, 1]}
                    tick={{ fontSize: 11, fill: "var(--muted)" }}
                    stroke="var(--border)"
                    tickFormatter={(val) => (val < 0.001 ? val.toExponential(0) : val.toFixed(2))}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface)",
                      borderColor: "var(--border)",
                      borderRadius: "var(--radius)",
                      fontSize: "12px",
                      boxShadow: "none",
                    }}
                    formatter={(val, name, item) => [
                      item.payload.rawP != null ? item.payload.rawP.toExponential(4) : "N/A",
                      "p-value",
                    ]}
                  />
                  <ReferenceLine
                    y={0.05}
                    stroke="var(--danger)"
                    strokeDasharray="4 4"
                    label={{
                      value: "Threshold (0.05)",
                      fill: "var(--danger)",
                      fontSize: 10,
                      position: "right",
                    }}
                  />
                  <Line
                    type="linear"
                    dataKey="pValue"
                    stroke="var(--accent)"
                    strokeWidth={2}
                    dot={{ fill: "var(--accent)", r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Reference vs Live Score Histogram */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Reference vs Live Score Histogram</h2>
              <p className="card-subtitle">
                20-bin relative density comparison across score intervals
              </p>
            </div>
          </div>

          <div style={{ width: "100%", height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={scoreDistribution} margin={{ top: 15, right: 15, left: -20, bottom: 0 }}>
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

      {/* Events Table marking source (scheduled or simulated or manual) */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">Drift Events Log</h2>
            <p className="card-subtitle">
              Audit log of statistical evaluations marking source (scheduled, simulated, or manual)
            </p>
          </div>
        </div>

        {events.length === 0 ? (
          <div className="empty-state">
            <p className="empty-state-desc">No events logged in database.</p>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Source</th>
                  <th>KS Statistic</th>
                  <th>p-value</th>
                  <th>Result</th>
                  <th>Reference N</th>
                  <th>Live N</th>
                </tr>
              </thead>
              <tbody>
                {events.map((evt, idx) => {
                  const source = evt.source || (evt.simulated ? "simulated" : "scheduled");
                  return (
                    <tr key={idx}>
                      <td style={{ fontSize: "12px", color: "var(--muted)", whiteSpace: "nowrap" }}>
                        {evt.checked_at ? new Date(evt.checked_at).toLocaleString() : "Recent"}
                      </td>
                      <td>
                        <span
                          className="mono"
                          style={{
                            fontSize: "11px",
                            padding: "2px 6px",
                            borderRadius: 3,
                            background: source === "simulated" ? "var(--warning-light)" : "var(--bg)",
                            color: source === "simulated" ? "var(--warning)" : "var(--muted)",
                            border: "1px solid var(--border)",
                          }}
                        >
                          {source.toUpperCase()}
                        </span>
                      </td>
                      <td className="mono" style={{ fontSize: "12px" }}>
                        {evt.ks_statistic != null ? Number(evt.ks_statistic).toFixed(4) : "N/A"}
                      </td>
                      <td className="mono" style={{ fontSize: "12px" }}>
                        {evt.p_value != null ? Number(evt.p_value).toExponential(4) : "N/A"}
                      </td>
                      <td>
                        {evt.alert ? (
                          <span className="badge badge-quarantined">Drift Alert</span>
                        ) : (
                          <span className="badge badge-reviewed">Pass</span>
                        )}
                      </td>
                      <td className="mono" style={{ fontSize: "12px" }}>
                        {evt.n_reference || 40000}
                      </td>
                      <td className="mono" style={{ fontSize: "12px" }}>
                        {evt.n_live || 1000}
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
  );
}
