import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  LineChart,
  ClipboardList,
  CalendarClock,
  Cog,
  Zap,
  FileBarChart,
  Moon,
  Sun,
  Factory,
  Menu,
  X,
} from "lucide-react";
import { useTheme } from "../context/ThemeContext";

const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/forecasting", label: "Demand Forecasting", icon: LineChart },
  { to: "/planning", label: "Production Planning", icon: ClipboardList },
  { to: "/scheduling", label: "Production Scheduling", icon: CalendarClock },
  { to: "/machines", label: "Machine Management", icon: Cog },
  { to: "/simulation", label: "Scenario Simulation", icon: Zap },
  { to: "/reports", label: "Reports", icon: FileBarChart },
];

export function Layout({ children }: { children: ReactNode }) {
  const { theme, toggleTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-950">
      {/* Sidebar (desktop) */}
      <aside className="hidden w-64 flex-col border-r border-slate-200 bg-white px-4 py-5 dark:border-slate-800 dark:bg-slate-900 lg:flex">
        <SidebarContent />
      </aside>

      {/* Sidebar (mobile) */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <aside className="relative z-50 flex w-64 flex-col bg-white px-4 py-5 dark:bg-slate-900">
            <button className="absolute right-3 top-3 text-slate-500" onClick={() => setMobileOpen(false)}>
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-h-screen flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900 lg:px-6">
          <button className="text-slate-500 lg:hidden" onClick={() => setMobileOpen(true)}>
            <Menu className="h-6 w-6" />
          </button>
          <div className="hidden text-sm text-slate-500 dark:text-slate-400 lg:block">
            AI-Based Production Planning and Scheduling System
          </div>
          <button
            onClick={toggleTheme}
            className="rounded-md p-2 text-slate-500 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
        </header>
        <main className="flex-1 px-4 py-6 lg:px-6">{children}</main>
      </div>
    </div>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <>
      <div className="mb-6 flex items-center gap-2 px-1">
        <div className="rounded-lg bg-indigo-600 p-1.5">
          <Factory className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">Production AI</p>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">Planning & Scheduling</p>
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              }`
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto px-1 pt-4 text-[11px] text-slate-400 dark:text-slate-500">
        Synthetic demo data where noted. See README for assumptions.
      </div>
    </>
  );
}
