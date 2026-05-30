import type { Assignment } from "./api";

interface GanttProps {
    assignments: Assignment[];
}

// Stable color palette — indexed by product order of appearance.
const COLORS = [
    "#3b82f6", // blue
    "#ef4444", // red
    "#10b981", // green
    "#f59e0b", // amber
    "#8b5cf6", // violet
    "#ec4899", // pink
    "#14b8a6", // teal
    "#f97316", // orange
];

export function Gantt({ assignments }: GanttProps) {
    if (assignments.length === 0) {
        return <div className="text-sm opacity-70">No assignments to display.</div>;
    }

    // Compute time scale 
    const times = assignments.flatMap((a) => [
        new Date(a.start).getTime(),
        new Date(a.end).getTime(),
    ]);
    const minTime = Math.min(...times);
    const maxTime = Math.max(...times);

    // Layout constants
    const ROW_HEIGHT = 50;
    const ROW_GAP = 6;
    const LABEL_WIDTH = 110;
    const CHART_WIDTH = 900;
    const PADDING = 20;
    const TOP_PADDING = 40;

    // Map products to colors
    const products = Array.from(new Set(assignments.map((a) => a.product)));
    products.sort();
    const colorOf = (product: string) =>
        COLORS[products.indexOf(product) % COLORS.length];

    // Group assignments by resource
    const resources = Array.from(new Set(assignments.map((a) => a.resource)));
    resources.sort();

    const byResource: Record<string, Assignment[]> = {};
    for (const a of assignments) {
        if (!byResource[a.resource]) byResource[a.resource] = [];
        byResource[a.resource].push(a);
    }

    // Time scaling 
    const chartX = LABEL_WIDTH + PADDING;
    const chartW = CHART_WIDTH - LABEL_WIDTH - 2 * PADDING;
    const toX = (iso: string) => {
        const t = new Date(iso).getTime();
        const fraction = (t - minTime) / (maxTime - minTime);
        return chartX + fraction * chartW;
    };

    const svgHeight = TOP_PADDING + resources.length * (ROW_HEIGHT + ROW_GAP) + 10;

    // Time axis ticks (every hour)
    const ticks: { x: number; label: string }[] = [];
    const startMs = Math.ceil(minTime / 3600000) * 3600000;
    for (let t = startMs; t <= maxTime; t += 3600000) {
        const d = new Date(t);
        ticks.push({
            x: toX(d.toISOString().slice(0, 19)),
            label: `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`,
        });
    }

    const fmtTime = (iso: string) => iso.slice(11, 16);

    return (
        <div className="overflow-x-auto">
            <svg width={CHART_WIDTH} height={svgHeight} style={{ background: "#fafafa" }}>
                {/* Time axis */}
                {ticks.map((tick, i) => (
                    <g key={i}>
                        <line
                            x1={tick.x}
                            y1={TOP_PADDING - 10}
                            x2={tick.x}
                            y2={svgHeight - 10}
                            stroke="#e5e5e5"
                            strokeDasharray="2,2"
                        />
                        <text
                            x={tick.x}
                            y={TOP_PADDING - 16}
                            fontSize="11"
                            fill="#666"
                            textAnchor="middle"
                        >
                            {tick.label}
                        </text>
                    </g>
                ))}

                {/* Resource rows */}
                {resources.map((resource, i) => {
                    const y = TOP_PADDING + i * (ROW_HEIGHT + ROW_GAP);
                    return (
                        <g key={resource}>
                            {/* Resource label */}
                            <text
                                x={LABEL_WIDTH + PADDING - 6}
                                y={y + ROW_HEIGHT / 2 + 4}
                                fontSize="14"
                                fontWeight="600"
                                fill="#222"
                                textAnchor="end"
                            >
                                {resource}
                            </text>

                            {/* Row background */}
                            <rect
                                x={chartX}
                                y={y}
                                width={chartW}
                                height={ROW_HEIGHT}
                                fill="#fff"
                                stroke="#e5e5e5"
                            />

                            {/* Assignment bars on this row */}
                            {byResource[resource].map((a, j) => {
                                const bx = toX(a.start);
                                const bx2 = toX(a.end);
                                const bw = Math.max(2, bx2 - bx);
                                return (
                                    <g key={j}>
                                        <rect
                                            x={bx}
                                            y={y + 4}
                                            width={bw}
                                            height={ROW_HEIGHT - 8}
                                            fill={colorOf(a.product)}
                                            rx={3}
                                        >
                                            <title>
                                                {a.product} step {a.step_index} ({a.capability})
                                                {"\n"}
                                                {fmtTime(a.start)} → {fmtTime(a.end)}
                                            </title>
                                        </rect>
                                        {bw > 60 && (
                                            <>
                                                <text
                                                    x={bx + bw / 2}
                                                    y={y + ROW_HEIGHT / 2 - 2}
                                                    fontSize="12"
                                                    fill="white"
                                                    fontWeight="600"
                                                    textAnchor="middle"
                                                >
                                                    {a.product}
                                                </text>
                                                <text
                                                    x={bx + bw / 2}
                                                    y={y + ROW_HEIGHT / 2 + 12}
                                                    fontSize="10"
                                                    fill="white"
                                                    fillOpacity="0.85"
                                                    textAnchor="middle"
                                                >
                                                    {fmtTime(a.start)}–{fmtTime(a.end)}
                                                </text>
                                            </>
                                        )}
                                    </g>
                                );
                            })}
                        </g>
                    );
                })}
            </svg>

            {/* Legend */}
            <div className="mt-4 flex gap-4 flex-wrap">
                {products.map((p) => (
                    <div key={p} className="flex items-center gap-2">
                        <span
                            className="inline-block w-4 h-4 rounded"
                            style={{ background: colorOf(p) }}
                        />
                        <span className="text-sm">{p}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}