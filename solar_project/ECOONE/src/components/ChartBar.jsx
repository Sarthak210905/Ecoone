import React from "react";

export default function ChartBar({ result }) {
  const prod =
    result.estimated_kw?.toFixed?.(2) ||
    result.estimated_kw ||
    result.required_kw ||
    0;
  const cons =
    result.monthly_units ||
    result.three_month_consumption ||
    0;
  if (!prod || !cons || prod <= 0 || cons <= 0) return null;
  const maxVal = Math.max(+prod, +cons);
  return (
    <div className="mt-4">
      <div className="flex gap-2 items-end h-12">
        <div className="flex flex-col items-center">
          <div
            className="bg-blue-400 rounded w-10"
            style={{ height: `${(prod / maxVal) * 48}px` }}
            aria-label={`Production bar: ${prod}`}
          ></div>
          <div className="text-xs mt-1">Production</div>
        </div>
        <div className="flex flex-col items-center">
          <div
            className="bg-orange-400 rounded w-10"
            style={{ height: `${(cons / maxVal) * 48}px` }}
            aria-label={`Consumption bar: ${cons}`}
          ></div>
          <div className="text-xs mt-1">Consumption</div>
        </div>
      </div>
    </div>
  );
}
