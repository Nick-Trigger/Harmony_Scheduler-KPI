import type { Assignment } from "./api";
import { ColorRampCollection } from "@maptiler/sdk"

interface GanttProps {
    assignments: Assignment[];
}

export function Gantt({ assignments }: GanttProps) {
    if (assignments.length === 0) {
        return <div className="text-sm opacity-70">No assignments to display.</div>;
    }

    // --- Layout constants ---
    const ROW_HEIGHT = 50;
    const ROW_GAP = 6;
    const LABEL_WIDTH = 110;
    const PADDING = 20;
    const TOP_PADDING = 40;
    const MIN_BAR_WIDTH = 80;       // narrowest width of a time block
    const MIN_CHART_WIDTH = 700;    // never shrink the chart below this
    const TICK_MS = 15 * 60 * 1000;
    const ASSIGNMENT_FILL_OPACITY = 0.25;
    const ASSIGNMENT_STROKE_WIDTH = 1.5;


    // Compute time scale at 15-minute intervals
    const times = assignments.flatMap((a) => [
        new Date(a.start).getTime(),
        new Date(a.end).getTime(),
    ]);
    const rawMin = Math.min(...times);
    const rawMax = Math.max(...times);
    const minTime = Math.floor(rawMin / TICK_MS) * TICK_MS;
    const maxTime = Math.ceil(rawMax / TICK_MS) * TICK_MS;


    // Compute chart width based on shortest assignment duration
    const shortestMin = Math.min(
        ...assignments.map(
            (a) => (new Date(a.end).getTime() - new Date(a.start).getTime()) / 60000,
        ),
    );
    const totalMin = (maxTime - minTime) / 60000;

    const pxPerMin = MIN_BAR_WIDTH / shortestMin;
    const requiredChartW = pxPerMin * totalMin;
    const chartW = Math.max(
        MIN_CHART_WIDTH - LABEL_WIDTH - 2 * PADDING,
        requiredChartW,
    );
    const CHART_WIDTH = LABEL_WIDTH + 2 * PADDING + chartW;
    const chartX = LABEL_WIDTH + PADDING;

    // Map products to colors
    const products = Array.from(new Set(assignments.map((a) => a.product)));
    products.sort();

    const colorMap = ColorRampCollection.PORTLAND.scale(0, products.length);

    const colorOf = (product: string) =>
        colorMap.getColorHex(products.indexOf(product));

    // Group assignments by resource
    const resources = Array.from(new Set(assignments.map((a) => a.resource)));
    resources.sort();

    const byResource: Record<string, Assignment[]> = {};
    for (const a of assignments) {
        if (!byResource[a.resource]) byResource[a.resource] = [];
        byResource[a.resource].push(a);
    }

    // Time scaling 
    const xFromMs = (ms: number) => {
        const fraction = (ms - minTime) / (maxTime - minTime);
        return chartX + fraction * chartW;
    };

    const xFromIso = (iso: string) => xFromMs(new Date(iso).getTime());

    const toX = (iso: string) => {
        const t = new Date(iso).getTime();
        const fraction = (t - minTime) / (maxTime - minTime);
        return chartX + fraction * chartW;
    };

    // Time axis ticks (every 15 minutes)
    const ticks: { x: number; isHour: boolean; label: string; key: string }[] = [];
    for (let t = minTime; t <= maxTime; t += TICK_MS) {
        const d = new Date(t);
        const isHour = d.getMinutes() === 0;
        const label = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
        ticks.push({
            x: xFromMs(t),
            isHour,
            label,
            key: String(t),
        });
    }

    const svgHeight = TOP_PADDING + resources.length * (ROW_HEIGHT + ROW_GAP) + 10;

    const fmtTime = (iso: string) => iso.slice(11, 16);

    return (
        <div className="overflow-x-auto">
            <svg width={CHART_WIDTH} height={svgHeight} style={{ background: "#fafafa" }}>
                {/* Resource rows */}
                {resources.map((resource, i) => {
                    const y = TOP_PADDING + i * (ROW_HEIGHT + ROW_GAP);
                    return (
                        <g key={`row-${resource}`}>
                            {/* Resource label */}
                            <text
                                x={LABEL_WIDTH + PADDING - 6}
                                y={y + ROW_HEIGHT / 2 + 4}
                                fontSize="14"
                                fontWeight="600"
                                fill="black"
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
                                fill="white"
                                stroke="lightgrey"
                            />
                        </g>
                    );
                })}

                {/* Time axis */}
                {ticks.map((tick) => (
                    <g key={`tick-${tick.key}`}>
                        <line
                            x1={tick.x}
                            y1={TOP_PADDING - 10}
                            x2={tick.x}
                            y2={svgHeight - 10}
                            stroke={tick.isHour ? "black" : "darkgrey"}
                            strokeWidth={tick.isHour ? 1 : 1}
                        />
                        <text
                            x={tick.x}
                            y={TOP_PADDING - 16}
                            fontSize={tick.isHour ? 13 : 10}
                            fill={tick.isHour ? "black" : "darkgrey"}
                            textAnchor="middle"
                        >
                            {tick.label}
                        </text>
                    </g>
                ))}

                {/* Assignment bars (drawn last so they sit on top of gridlines) */}
                {resources.map((resource, i) => {
                    const y = TOP_PADDING + i * (ROW_HEIGHT + ROW_GAP);
                    return (
                        <g key={`bars-${resource}`}>
                            {byResource[resource].map((a) => {
                                const bx = toX(a.start);
                                const bx2 = toX(a.end);
                                const bw = Math.max(2, bx2 - bx);
                                const barKey = `${a.product}-${a.step_index}-${a.resource}`;
                                return (
                                    <g key={barKey}>
                                        <rect
                                            x={bx}
                                            y={y + 4}
                                            width={bw}
                                            height={ROW_HEIGHT - 8}
                                            fill="#fff"
                                            rx={3}
                                        />
                                        {/* Colored overlay — translucent, sits on the white below */}
                                        <rect
                                            x={bx}
                                            y={y + 4}
                                            width={bw}
                                            height={ROW_HEIGHT - 8}
                                            fill={colorOf(a.product)}
                                            fillOpacity={ASSIGNMENT_FILL_OPACITY}
                                            stroke={colorOf(a.product)}
                                            strokeWidth={ASSIGNMENT_STROKE_WIDTH}
                                            rx={3}
                                        />
                                        <title>
                                            {a.product} step {a.step_index} ({a.capability})
                                            {"\n"}
                                            {fmtTime(a.start)} → {fmtTime(a.end)}
                                        </title>
                                        {bw > 60 && (
                                            <>
                                                <text
                                                    x={bx + bw / 2}
                                                    y={y + ROW_HEIGHT / 2 - 2}
                                                    fontSize="12"
                                                    fill="black"
                                                    fontWeight="600"
                                                    textAnchor="middle"
                                                >
                                                    {a.product}, #{a.step_index}
                                                </text>
                                                <text
                                                    x={bx + bw / 2}
                                                    y={y + ROW_HEIGHT / 2 + 12}
                                                    fontSize="10"
                                                    fill="black"
                                                    fillOpacity="0.85"
                                                    textAnchor="middle"
                                                >
                                                    {fmtTime(a.start)}-{fmtTime(a.end)}
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
        </div>
    );
}