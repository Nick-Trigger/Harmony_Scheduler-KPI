import { useState } from "react";
import { Gantt } from "./Gantt";
import { postSchedule, type ScheduleResponse, type InfeasibleResponse } from "./api";
import { exampleData } from "./exampleData";

export default function App() {
  const [result, setResult] = useState<ScheduleResponse | null>(null);
  const [error, setError] = useState<InfeasibleResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSchedule() {
    setLoading(true);
    setError(null);
    setResult(null);
    const response = await postSchedule(exampleData);
    setLoading(false);
    if (response.ok) {
      setResult(response.data);
    } else {
      setError(response.error);
    }
  }

  return (
    <div className="min-h-screen bg-base-200">
      {/* Top bar with settings dropdown */}
      <div className="navbar bg-base-100 shadow-sm">
        <div className="navbar-start">
          <div className="dropdown">
            <div tabIndex={0} role="button" className="btn btn-ghost btn-square">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                className="w-5 h-5"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            </div>
            <ul
              tabIndex={0}
              className="menu menu-sm dropdown-content bg-base-100 rounded-box z-10 mt-3 w-52 p-2 shadow"
            >
              <li>
                <a>Settings (placeholder)</a>
              </li>
              <li>
                <a>Theme</a>
              </li>
              <li>
                <a>About</a>
              </li>
            </ul>
          </div>
          <span className="ml-2 font-semibold">Harmony Scheduler</span>
        </div>
      </div>

      {/* Main content */}
      <div className="p-6 max-w-5xl mx-auto">
        <div className="mb-6">
          <button
            className="btn btn-primary"
            onClick={handleSchedule}
            disabled={loading}
          >
            {loading ? "Solving..." : "Schedule example"}
          </button>
        </div>

        {/* Error display */}
        {error && (
          <div className="alert alert-error mb-6">
            <div>
              <div className="font-semibold">{error.error}</div>
              <ul className="text-sm mt-1 list-disc list-inside">
                {error.why.map((reason, i) => (
                  <li key={i}>{reason}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Schedule display */}
        {result && (
          <div className="space-y-6">
            <div className="card bg-base-100 shadow-sm">
              <div className="card-body">
                <h2 className="card-title">Schedule</h2>
                <Gantt assignments={result.assignments} />
              </div>
            </div>

            <div className="card bg-base-100 shadow-sm">
              <div className="card-body">
                <h2 className="card-title">KPIs</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-xs opacity-70">Tardiness</div>
                    <div className="text-xl font-semibold">
                      {result.kpis.tardiness_minutes} min
                    </div>
                  </div>
                  <div>
                    <div className="text-xs opacity-70">Changeovers</div>
                    <div className="text-xl font-semibold">
                      {result.kpis.changeover_count} ({result.kpis.changeover_minutes} min)
                    </div>
                  </div>
                  <div>
                    <div className="text-xs opacity-70">Makespan</div>
                    <div className="text-xl font-semibold">
                      {result.kpis.makespan_minutes} min
                    </div>
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-xs opacity-70 mb-2">Utilization</div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {Object.entries(result.kpis.utilization_pct).map(([r, pct]) => (
                      <div key={r} className="text-sm">
                        <span className="font-mono">{r}:</span> {pct}%
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}