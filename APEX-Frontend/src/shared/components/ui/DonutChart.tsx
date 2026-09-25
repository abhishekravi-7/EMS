import React from "react";

export interface SliceItem {
  label: string;
  value: number;
  color: string;
  percent?: number;
}

export interface DonutChartProps {
  slices: SliceItem[];
  total: number;
  centerLabel: string;
  size?: number;
  outerRadius?: number;
  innerRadius?: number;
}

const DonutChart: React.FC<DonutChartProps> = ({
  slices,
  total,
  centerLabel,
  size = 160,
  outerRadius = 64,
  innerRadius = 46
}) => {
  const cx = size / 2;
  const cy = size / 2;
  const strokeWidth = outerRadius - innerRadius;
  const midRadius = (outerRadius + innerRadius) / 2;

  const nonZeroSlices = slices.filter((s) => s.value > 0);

  let chartContent: React.ReactNode;

  if (total === 0 || nonZeroSlices.length === 0) {
    chartContent = (
      <circle
        cx={cx}
        cy={cy}
        r={midRadius}
        fill="none"
        stroke="#f1f5f9"
        strokeWidth={strokeWidth}
      />
    );
  } else if (nonZeroSlices.length === 1) {
    const single = nonZeroSlices[0];
    chartContent = (
      <circle
        cx={cx}
        cy={cy}
        r={midRadius}
        fill="none"
        stroke={single.color}
        strokeWidth={strokeWidth}
      />
    );
  } else {
    let accumulatedAngle = -Math.PI / 2;
    const paths: React.ReactNode[] = [];

    slices.forEach((slice, idx) => {
      if (slice.value <= 0) return;
      const sliceAngle = (slice.value / total) * 2 * Math.PI;
      const startAngle = accumulatedAngle;
      const endAngle = accumulatedAngle + sliceAngle;
      accumulatedAngle = endAngle;

      const x1Outer = cx + outerRadius * Math.cos(startAngle);
      const y1Outer = cy + outerRadius * Math.sin(startAngle);
      const x2Outer = cx + outerRadius * Math.cos(endAngle);
      const y2Outer = cy + outerRadius * Math.sin(endAngle);

      const x1Inner = cx + innerRadius * Math.cos(endAngle);
      const y1Inner = cy + innerRadius * Math.sin(endAngle);
      const x2Inner = cx + innerRadius * Math.cos(startAngle);
      const y2Inner = cy + innerRadius * Math.sin(startAngle);

      const largeArcFlag = sliceAngle > Math.PI ? 1 : 0;

      const d = `
        M ${x1Outer} ${y1Outer}
        A ${outerRadius} ${outerRadius} 0 ${largeArcFlag} 1 ${x2Outer} ${y2Outer}
        L ${x1Inner} ${y1Inner}
        A ${innerRadius} ${innerRadius} 0 ${largeArcFlag} 0 ${x2Inner} ${y2Inner}
        Z
      `;

      paths.push(
        <path
          key={idx}
          d={d}
          fill={slice.color}
          stroke="#ffffff"
          strokeWidth="2"
          strokeLinejoin="round"
        />
      );
    });

    chartContent = paths;
  }

  return (
    <div style={{ position: "relative", width: size, height: size, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {chartContent}
      </svg>
      <div style={{ position: "absolute", textAlign: "center", pointerEvents: "none" }}>
        <div style={{ fontSize: 20, fontWeight: 900, color: "#0f172a", lineHeight: 1 }}>{total.toLocaleString()}</div>
        <div style={{ fontSize: 9, fontWeight: 800, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.8, marginTop: 4 }}>
          {centerLabel}
        </div>
      </div>
    </div>
  );
};

export default DonutChart;
