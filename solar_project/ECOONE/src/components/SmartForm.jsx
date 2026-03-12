import React, { useState, useRef } from "react";
import { postSmart } from "../api/solar";
import { validatePositive } from "../utils/validators";

function SmartForm({ onSubmit, loading, error, onClear }) {
  const [length_m, setLength_m] = useState("");
  const [breadth_m, setBreadth_m] = useState("");
  const [monthly_units, setMonthly_units] = useState("");
  const [state, setState] = useState("");
  const [vendor_type, setVendor_type] = useState("");
  const [photo, setPhoto] = useState(null);
  const [errors, setErrors] = useState({});
  const fileInput = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    let errs = {};

    if (validatePositive(length_m)) {
      // valid
    } else if (length_m !== "") {
      errs.length_m = "Must be positive if provided.";
    }

    if (validatePositive(breadth_m)) {
      // valid
    } else if (breadth_m !== "") {
      errs.breadth_m = "Must be positive if provided.";
    }

    if (validatePositive(monthly_units)) {
      // valid
    } else if (monthly_units !== "") {
      errs.monthly_units = "Must be positive if provided.";
    }

    if (!state) errs.state = "State required.";
    if (!vendor_type) errs.vendor_type = "Vendor type required.";

    if (length_m === "" && breadth_m === "" && monthly_units === "") {
      errs.mode = "Provide area, consumption, or both.";
    }

    setErrors(errs);

    if (Object.keys(errs).length === 0) {
      const data = new FormData();
      if (length_m) data.append("length_m", length_m);
      if (breadth_m) data.append("breadth_m", breadth_m);
      if (monthly_units) data.append("monthly_units", monthly_units);
      data.append("state", state);
      data.append("vendor_type", vendor_type);
      if (photo) data.append("photo", photo);
      onSubmit(postSmart(data));
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="bg-blue-50 border-2 border-blue-200 rounded-xl p-4">
        <p className="text-sm text-blue-800 flex items-start gap-2">
          <span className="text-lg">💡</span>
          <span>Smart mode allows flexible input. Provide area, consumption, or both for comprehensive analysis.</span>
        </p>
      </div>

      {errors.mode && (
        <div className="bg-red-50 border-2 border-red-200 rounded-xl p-4">
          <p className="text-sm text-red-800 flex items-center gap-2">
            <span>⚠️</span> {errors.mode}
          </p>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            📏 Length (m) - Optional
          </label>
          <input
            type="number"
            step="0.1"
            value={length_m}
            onChange={(e) => setLength_m(e.target.value)}
            className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none"
            placeholder="Length"
          />
          {errors.length_m && (
            <p className="text-red-500 text-xs mt-1">{errors.length_m}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            📐 Breadth (m) - Optional
          </label>
          <input
            type="number"
            step="0.1"
            value={breadth_m}
            onChange={(e) => setBreadth_m(e.target.value)}
            className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none"
            placeholder="Breadth"
          />
          {errors.breadth_m && (
            <p className="text-red-500 text-xs mt-1">{errors.breadth_m}</p>
          )}
        </div>
      </div>

      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          ⚡ Monthly Units (kWh) - Optional
        </label>
        <input
          type="number"
          step="0.1"
          value={monthly_units}
          onChange={(e) => setMonthly_units(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none"
          placeholder="Monthly consumption"
        />
        {errors.monthly_units && (
          <p className="text-red-500 text-xs mt-1">{errors.monthly_units}</p>
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
          <p className="text-red-500 text-xs mt-1">{errors.state}</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          🏪 Vendor Type
        </label>
        <select
          value={vendor_type}
          onChange={(e) => setVendor_type(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all outline-none bg-white"
        >
          <option value="">Select Vendor</option>
          <option value="Default">Default</option>
          <option value="Premium">Premium</option>
          <option value="Budget">Budget</option>
        </select>
        {errors.vendor_type && (
          <p className="text-red-500 text-xs mt-1">{errors.vendor_type}</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          📸 Upload Photo - Optional
        </label>
        <input
          type="file"
          ref={fileInput}
          accept="image/*"
          onChange={(e) => setPhoto(e.target.files[0])}
          className="hidden"
        />
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          className="w-full px-4 py-3 rounded-xl border-2 border-dashed border-gray-300 hover:border-blue-400 transition-all text-gray-600 hover:text-blue-600 flex items-center justify-center gap-2"
        >
          {photo ? (
            <>
              <span>✅</span> {photo.name}
            </>
          ) : (
            <>
              <span>📤</span> Click to upload image
            </>
          )}
        </button>
      </div>

      <div className="flex gap-3 pt-4">
        <button
          type="submit"
          disabled={loading}
          className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-3 px-6 rounded-xl font-semibold shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
        >
          {loading ? "Analyzing..." : "Smart Calculate 🤖"}
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

export default SmartForm;

