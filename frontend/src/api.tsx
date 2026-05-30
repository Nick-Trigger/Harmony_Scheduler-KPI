export interface Assignment {
    product: string;
    step_index: number;
    capability: string;
    resource: string;
    start: string;
    end: string;
}

export interface KPIs {
    tardiness_minutes: number;
    changeover_count: number;
    changeover_minutes: number;
    makespan_minutes: number;
    utilization_pct: Record<string, number>;
}

export interface ScheduleResponse {
    assignments: Assignment[];
    kpis: KPIs;
}

export interface InfeasibleResponse {
    error: string;
    why: string[];
}

const API_BASE = "http://localhost:8000";

export async function postSchedule(
    payload: object,
): Promise<{ ok: true; data: ScheduleResponse } | { ok: false; error: InfeasibleResponse }> {
    const res = await fetch(`${API_BASE}/schedule`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    if (res.ok) {
        return { ok: true, data: await res.json() };
    }
    return { ok: false, error: await res.json() };
}