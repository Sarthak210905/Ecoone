import React from "react";

function Spinner() {
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative">
        <div className="w-16 h-16 border-4 border-blue-200 rounded-full"></div>
        <div className="w-16 h-16 border-4 border-blue-600 rounded-full border-t-transparent animate-spin absolute top-0 left-0"></div>
      </div>
      <p className="text-gray-600 font-semibold animate-pulse">
        Calculating your solar requirements...
      </p>
    </div>
  );
}

export default Spinner;

