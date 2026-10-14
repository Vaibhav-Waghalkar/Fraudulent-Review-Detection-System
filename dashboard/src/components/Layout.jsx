import { NavLink } from "react-router-dom";
import { Shield, List, Activity } from "lucide-react";

const navItems = [
  { to: "/reviews", label: "Reviews", icon: List },
  { to: "/drift", label: "Drift", icon: Activity },
];

export default function Layout({ children }) {
  return (
    <div className="layout">
      <aside className="sidebar" role="navigation" aria-label="Main navigation">
        <div className="sidebar-brand">
          <Shield className="sidebar-brand-icon" aria-hidden="true" />
          <span className="sidebar-brand-name">ReviewGuard</span>
        </div>
        <ul className="sidebar-nav">
          {navItems.map(({ to, label, icon: Icon }) => (
            <li key={to} className="sidebar-nav-item">
              <NavLink
                to={to}
                className={({ isActive }) =>
                  "sidebar-nav-link" + (isActive ? " active" : "")
                }
              >
                <Icon aria-hidden="true" />
                <span>{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
