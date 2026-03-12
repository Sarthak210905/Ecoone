import React from "react";

function VendorChips({ vendors }) {
  return (
    <div className="flex flex-wrap gap-2">
      {vendors.map((vendor, idx) => (
        <span
          key={idx}
          className="px-4 py-2 bg-gradient-to-r from-blue-100 to-indigo-100 text-blue-800 rounded-full text-sm font-semibold border border-blue-200 shadow-sm"
        >
          {vendor}
        </span>
      ))}
    </div>
  );
}

export default VendorChips;

