import React, { useState } from "react";
import { postManual } from "../api/solar";
import { validatePositive } from "../utils/validators";

function AreaForm({ onSubmit, loading, error, onClear }) {
  const [length_m, setLength] = useState("");
  const [breadth_m, setBreadth] = useState("");
  const [state, setState] = useState("");
  const [vendor_type, setVendorType] = useState("");
  const [errors, setErrors] = useState({});

  const handleSubmit = (e) => {
    e.preventDefault();
    let errs = {};
    
    if (!validatePositive(length_m))
      errs.length_m = "Length is required and must be positive.";
    if (!validatePositive(breadth_m))
      errs.breadth_m = "Breadth is required and must be positive.";
    if (!state) errs.state = "State is required.";
    if (!vendor_type) errs.vendor_type = "Vendor type is required.";
    
    setErrors(errs);
    
    if (Object.keys(errs).length === 0) {
      onSubmit(postManual({ length_m, breadth_m, state, vendor_type }));
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          📏 Length (meters)
        </label>
        <input
          type="number"
          step="0.1"
          value={length_m}
          onChange={(e) => setLength(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none"
          placeholder="Enter length in meters"
        />
        {errors.length_m && (
          <p className="text-red-500 text-xs mt-1 flex items-center gap-1">
            <span>⚠️</span> {errors.length_m}
          </p>
        )}
      </div>

      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          📐 Breadth (meters)
        </label>
        <input
          type="number"
          step="0.1"
          value={breadth_m}
          onChange={(e) => setBreadth(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none"
          placeholder="Enter breadth in meters"
        />
        {errors.breadth_m && (
          <p className="text-red-500 text-xs mt-1 flex items-center gap-1">
            <span>⚠️</span> {errors.breadth_m}
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

export default AreaForm;

