import React from "react";
import VendorChips from "./VendorChips";

function ResultCard({ result, mode }) {
  const formatCurrency = (val) => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  const renderAreaResult = (data) => (
    <div className="space-y-4">
      <div className={`p-4 rounded-xl ${data.feasible ? 'bg-green-50 border-2 border-green-200' : 'bg-red-50 border-2 border-red-200'}`}>
        <p className={`font-semibold ${data.feasible ? 'text-green-800' : 'text-red-800'}`}>
          {data.message}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Total Area" value={`${data.total_area_m2} m²`} icon="📐" />
        <StatCard label="Usable Area" value={`${data.usable_area_m2} m²`} icon="✅" />
        <StatCard label="Panels Required" value={data.estimated_no_of_panels} icon="☀️" />
        <StatCard label="System Capacity" value={`${data.estimated_system_kw} kW`} icon="⚡" />
      </div>

      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-6 rounded-xl">
        <p className="text-sm opacity-90 mb-1">Estimated Cost</p>
        <p className="text-3xl font-bold">{formatCurrency(data.estimated_cost_inr)}</p>
      </div>

      {data.recommended_vendors && data.recommended_vendors.length > 0 && (
        <div>
          <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span>🏪</span> Recommended Vendors
          </h3>
          <VendorChips vendors={data.recommended_vendors} />
        </div>
      )}
    </div>
  );

  const renderUnitsResult = (data) => (
    <div className="space-y-4">
      <div className="bg-blue-50 border-2 border-blue-200 p-4 rounded-xl">
        <p className="font-semibold text-blue-800">{data.message}</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Monthly Usage" value={`${data.monthly_units} kWh`} icon="📊" />
        <StatCard label="Daily Average" value={`${data.average_daily_load_kwh} kWh`} icon="☀️" />
        <StatCard label="Required Capacity" value={`${data.required_solar_capacity_kw} kW`} icon="⚡" />
        <StatCard label="3-Month Total" value={`${data.three_month_consumption_kwh} kWh`} icon="📈" />
      </div>

      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-6 rounded-xl">
        <p className="text-sm opacity-90 mb-1">Estimated Cost</p>
        <p className="text-3xl font-bold">{formatCurrency(data.estimated_cost_inr)}</p>
      </div>

      {data.recommended_vendors && data.recommended_vendors.length > 0 && (
        <div>
          <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <span>🏪</span> Recommended Vendors
          </h3>
          <VendorChips vendors={data.recommended_vendors} />
        </div>
      )}
    </div>
  );

  return (
    <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-2 flex items-center gap-2">
          <span>📊</span> Results
        </h2>
        {result.mode_used && (
          <p className="text-sm text-gray-600">Mode: {result.mode_used}</p>
        )}
      </div>

      {result.manual_area_result && (
        <div className="mb-6">
          {result.mode_used === "Both" && (
            <h3 className="font-bold text-lg mb-4 text-gray-700">Area Analysis</h3>
          )}
          {renderAreaResult(result.manual_area_result)}
        </div>
      )}

      {result.consumption_result && (
        <div>
          {result.mode_used === "Both" && (
            <>
              <hr className="my-6 border-gray-200" />
              <h3 className="font-bold text-lg mb-4 text-gray-700">Consumption Analysis</h3>
            </>
          )}
          {renderUnitsResult(result.consumption_result)}
        </div>
      )}

      {!result.manual_area_result && !result.consumption_result && (
        <div className="text-center text-gray-500 py-8">
          No results to display
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon }) {
  return (
    <div className="bg-gradient-to-br from-gray-50 to-gray-100 p-4 rounded-xl border border-gray-200">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xl">{icon}</span>
        <p className="text-xs text-gray-600 font-medium">{label}</p>
      </div>
      <p className="text-xl font-bold text-gray-800">{value}</p>
    </div>
  );
}

export default ResultCard;

