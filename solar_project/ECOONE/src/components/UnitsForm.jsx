import React, { useState } from "react";
import { postSmart } from "../api/solar";
import { validatePositive } from "../utils/validators";

function UnitsForm({ onSubmit, loading, error, onClear }) {
  const [monthly_units, setUnits] = useState("");
  const [state, setState] = useState("");
  const [vendor_type, setVendorType] = useState("");
  const [errors, setErrors] = useState({});

  const handleSubmit = (e) => {
    e.preventDefault();
    let errs = {};
    
    if (!validatePositive(monthly_units))
      errs.monthly_units = "Monthly units required and must be positive.";
    if (!state) errs.state = "State is required.";
    if (!vendor_type) errs.vendor_type = "Vendor type is required.";
    
    setErrors(errs);
    
    if (Object.keys(errs).length === 0) {
      const formData = new FormData();
      formData.append("monthly_units", monthly_units);
      formData.append("state", state);
      formData.append("vendor_type", vendor_type);
      onSubmit(postSmart(formData));
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          ⚡ Monthly Consumption (kWh)
        </label>
        <input
          type="number"
          step="0.1"
          value={monthly_units}
          onChange={(e) => setUnits(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none"
          placeholder="Enter monthly units consumed"
        />
        {errors.monthly_units && (
          <p className="text-red-500 text-xs mt-1 flex items-center gap-1">
            <span>⚠️</span> {errors.monthly_units}
          </p>
        )}
      </div>

      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          🗺️ State
        </label>
        <select
          value={state}
          onChange={(e) => setState(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none bg-white"
        >
          <option value="">Select State</option>
          <option value="Default">Default</option>
          <option value="Chhattisgarh">Chhattisgarh</option>
          <option value="Madhya Pradesh">Madhya Pradesh</option>
          <option value="Maharashtra">Maharashtra</option>
          <option value="Uttar Pradesh">Uttar Pradesh</option>
        </select>
        {errors.state && (
          <p className="text-red-500 text-xs mt-1 flex items-center gap-1">
            <span>⚠️</span> {errors.state}
          </p>
        )}
      </div>

      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          🏪 Vendor Type
        </label>
        <select
          value={vendor_type}
          onChange={(e) => setVendorType(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none bg-white"
        >
          <option value="">Select Vendor</option>
          <option value="Default">Default</option>
          <option value="Premium">Premium</option>
          <option value="Budget">Budget</option>
        </select>
        {errors.vendor_type && (
          <p className="text-red-500 text-xs mt-1 flex items-center gap-1">
            <span>⚠️</span> {errors.vendor_type}
          </p>
        )}
      </div>

      <div className="flex gap-3 pt-4">
        <button
          type="submit"
          disabled={loading}
          className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-3 px-6 rounded-xl font-semibold shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
        >
          {loading ? "Calculating..." : "Calculate ⚡"}
        </button>
        <button
          type="button"
          onClick={onClear}
          className="px-6 py-3 rounded-xl border-2 border-gray-300 text-gray-700 font-semibold hover:bg-gray-50 transition-all"
        >
          Clear
        </button>
      </div>
    </form>
  );
}

export default UnitsForm;
