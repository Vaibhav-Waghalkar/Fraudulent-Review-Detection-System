import { useQuery } from "@tanstack/react-query";
import { Download, ShieldCheck, History } from "lucide-react";
import { fetchAuditLogs } from "../api";

export default function AuditPage() {
  const { data: logs, isLoading, error } = useQuery({
    queryKey: ["auditLogs"],
    queryFn: () => fetchAuditLogs(100),
  });

  const handleDownloadCsv = () => {
    window.open("/api/reviews/export/labels", "_blank");
  };

  return (
    <div className="page-container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600 }}>Moderation Audit Trail</h2>
          <p style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
            Full immutable log of reviewer overrides, notes, and retraining label exports.
          </p>
        </div>
        <button type="button" className="btn btn-outline" onClick={handleDownloadCsv}>
          <Download style={{ width: 14, height: 14 }} />
          <span>Export Labels CSV</span>
        </button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {isLoading ? (
          <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-muted)" }}>Loading audit entries...</div>
        ) : error ? (
          <div style={{ padding: 24, color: "var(--color-danger)" }}>Error loading audit logs: {error.message}</div>
        ) : !logs || logs.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: "var(--color-text-muted)" }}>
            <History style={{ width: 24, height: 24, margin: "0 auto 8px", opacity: 0.6 }} />
            <div>No moderation override events recorded yet.</div>
          </div>
        ) : (
          <table className="table" style={{ margin: 0 }}>
            <thead>
              <tr>
                <th>TIMESTAMP</th>
                <th>REVIEW ID</th>
                <th>MODERATOR</th>
                <th>ACTION</th>
                <th>PREVIOUS</th>
                <th>NEW STATUS</th>
                <th>NOTE</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td className="mono" style={{ fontSize: 12 }}>{log.timestamp?.replace("T", " ").substring(0, 19)}</td>
                  <td className="mono" style={{ fontSize: 12 }}>
                    <a href={`/reviews/${log.review_id}`} style={{ color: "inherit", textDecoration: "underline" }}>
                      {log.review_id?.substring(0, 10)}...
                    </a>
                  </td>
                  <td className="mono" style={{ fontSize: 12 }}>{log.moderator_id}</td>
                  <td>
                    <span className={`badge badge-${log.action === "approve" ? "low" : "high"}`}>
                      {log.action}
                    </span>
                  </td>
                  <td className="mono" style={{ fontSize: 12 }}>{log.previous_status || "—"}</td>
                  <td className="mono" style={{ fontSize: 12 }}>{log.new_status}</td>
                  <td style={{ fontSize: 13 }}>{log.note || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
