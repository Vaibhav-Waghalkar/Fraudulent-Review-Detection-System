import { useState, useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Shield,
  LayoutDashboard,
  ListFilter,
  Activity,
  Cpu,
  RefreshCw,
  Sun,
  Moon,
} from "lucide-react";
import { fetchHealth } from "../api";

export default function Layout({ children }) {
  const location = useLocation();
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("rg-theme") || "light";
  });
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState(() => new Date());

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("rg-theme", theme);
  }, [theme]);

  // Health status query
  const { data: health, refetch: refetchHealth } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: autoRefresh ? 10000 : false,
  });

  const handleManualRefresh = () => {
    setLastRefreshed(new Date());
    refetchHealth();
    // Dispatch a custom event so active pages can refetch
    window.dispatchEvent(new CustomEvent("rg-refresh"));
  };

  useEffect(() => {
    let interval;
    if (autoRefresh) {
      interval = setInterval(() => {
        setLastRefreshed(new Date());
      }, 10000);
    }
    return () => clearInterval(interval);
  }, [autoRefresh]);

  // Page title mapping
  const getPageInfo = () => {
    const path = location.pathname;
    if (path === "/" || path === "/overview") {
      return { title: "Overview", subtitle: "Real-time fraud telemetry and score distributions" };
    }
    if (path.startsWith("/reviews/")) {
      return { title: "Review Detail", subtitle: "LIME explanation, rule breakdown, and audit timeline" };
    }
    if (path === "/reviews") {
      return { title: "Review Queue", subtitle: "Moderation triage, risk presets, and manual review actions" };
    }
    if (path === "/drift") {
      return { title: "Distribution Drift", subtitle: "Kolmogorov-Smirnov statistical monitoring and alerts" };
    }
    if (path === "/model") {
      return { title: "Model Telemetry", subtitle: "Architecture, confusion matrix, and ONNX benchmarks" };
    }
    return { title: "Dashboard", subtitle: "ReviewGuard moderation system" };
  };

  const pageInfo = getPageInfo();

  return (
    <div className="layout">
      {/* Grouped Sidebar */}
      <aside className="sidebar" role="navigation" aria-label="Main navigation">
        <div className="sidebar-brand">
          <Shield className="sidebar-brand-icon" aria-hidden="true" />
          <span className="sidebar-brand-name">ReviewGuard</span>
        </div>

        <div className="sidebar-nav-container">
          <div>
            <div className="sidebar-group-title">Monitor</div>
            <ul className="sidebar-nav">
              <li>
                <NavLink
                  to="/overview"
                  className={({ isActive }) =>
                    "sidebar-nav-link" + (isActive ? " active" : "")
                  }
                >
                  <LayoutDashboard aria-hidden="true" />
                  <span>Overview</span>
                </NavLink>
              </li>
              <li>
                <NavLink
                  to="/reviews"
                  className={({ isActive }) =>
                    "sidebar-nav-link" + (isActive ? " active" : "")
                  }
                >
                  <ListFilter aria-hidden="true" />
                  <span>Reviews</span>
                </NavLink>
              </li>
              <li>
                <NavLink
                  to="/drift"
                  className={({ isActive }) =>
                    "sidebar-nav-link" + (isActive ? " active" : "")
                  }
                >
                  <Activity aria-hidden="true" />
                  <span>Drift</span>
                </NavLink>
              </li>
            </ul>
          </div>

          <div>
            <div className="sidebar-group-title">Model</div>
            <ul className="sidebar-nav">
              <li>
                <NavLink
                  to="/model"
                  className={({ isActive }) =>
                    "sidebar-nav-link" + (isActive ? " active" : "")
                  }
                >
                  <Cpu aria-hidden="true" />
                  <span>Model Info</span>
                </NavLink>
              </li>
            </ul>
          </div>
        </div>

        {/* Sidebar Footer: System Status */}
        <div className="sidebar-footer">
          <div className="system-status-box">
            <div className="system-status-header">
              <span>System Status</span>
              <span className="mono" style={{ fontSize: "10px" }}>
                {health?.status === "ok" ? "HEALTHY" : "DEGRADED"}
              </span>
            </div>
            <div className="system-status-items">
              <div className="system-status-item">
                <span className="system-status-label">API</span>
                <span className="status-dot-wrap">
                  <span className={`status-dot ${health ? "online" : "offline"}`} />
                  {health ? "up" : "down"}
                </span>
              </div>
              <div className="system-status-item">
                <span className="system-status-label">Model</span>
                <span className="status-dot-wrap">
                  <span
                    className={`status-dot ${
                      health?.model_loaded ? "online" : "offline"
                    }`}
                  />
                  {health?.model_loaded ? "loaded" : "off"}
                </span>
              </div>
              <div className="system-status-item">
                <span className="system-status-label">MongoDB</span>
                <span className="status-dot-wrap">
                  <span
                    className={`status-dot ${
                      health?.mongo_connected ? "online" : "offline"
                    }`}
                  />
                  {health?.mongo_connected ? "rs0" : "down"}
                </span>
              </div>
              <div className="system-status-item">
                <span className="system-status-label">Redis</span>
                <span className="status-dot-wrap">
                  <span
                    className={`status-dot ${
                      health?.redis_connected ? "online" : "offline"
                    }`}
                  />
                  {health?.redis_connected ? "cache" : "down"}
                </span>
              </div>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-outline btn-sm"
            style={{ width: "100%", justifyContent: "center" }}
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            title="Toggle color theme"
          >
            {theme === "light" ? (
              <>
                <Moon style={{ width: 14, height: 14 }} />
                <span>Dark Theme</span>
              </>
            ) : (
              <>
                <Sun style={{ width: 14, height: 14 }} />
                <span>Light Theme</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        {/* Top Bar */}
        <header className="top-bar">
          <div className="top-bar-left">
            <h1 className="top-bar-title">{pageInfo.title}</h1>
            <p className="top-bar-subtitle">{pageInfo.subtitle}</p>
          </div>

          <div className="top-bar-actions">
            <span className="refresh-indicator">
              Refreshed: {lastRefreshed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </span>

            <button
              type="button"
              className={`btn btn-sm ${autoRefresh ? "btn-primary" : "btn-outline"}`}
              onClick={() => setAutoRefresh(!autoRefresh)}
              title="Toggle automatic periodic refetch every 10 seconds"
            >
              <RefreshCw
                style={{
                  width: 12,
                  height: 12,
                }}
              />
              <span>Auto-refresh: {autoRefresh ? "ON" : "OFF"}</span>
            </button>

            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={handleManualRefresh}
              title="Refresh page data"
            >
              Refresh
            </button>
          </div>
        </header>

        {children}

        {/* Demo notice footer */}
        <footer className="demo-notice-footer">
          ReviewGuard Enterprise Fraud Engine. Displaying seeded synthetic demo dataset from production telemetry.
        </footer>
      </main>
    </div>
  );
}
