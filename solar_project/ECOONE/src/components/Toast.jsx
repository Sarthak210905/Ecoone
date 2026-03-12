import React, { useEffect } from "react";

function Toast({ message, onClose }) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, 5000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-slideIn">
      <div className="bg-red-500 text-white px-6 py-4 rounded-xl shadow-2xl flex items-center gap-3 max-w-md">
        <span className="text-2xl">⚠️</span>
        <div className="flex-1">
          <p className="font-semibold mb-1">Error</p>
          <p className="text-sm opacity-90">{message}</p>
        </div>
        <button
          onClick={onClose}
          className="text-white hover:bg-red-600 rounded-lg p-1 transition-colors"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

export default Toast;

