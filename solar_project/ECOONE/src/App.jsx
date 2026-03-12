import React, { useState } from "react";
import Header from "./components/Header";
import AreaForm from "./components/AreaForm";
import UnitsForm from "./components/UnitsForm";
import SmartForm from "./components/SmartForm";
import ResultCard from "./components/ResultCard";
import Spinner from "./components/Spinner";
import Toast from "./components/Toast";

const MODES = [
  { key: "area", label: "Manual Area", icon: "📐" },
  { key: "units", label: "Consumption", icon: "⚡" },
  { key: "smart", label: "Smart Mode", icon: "🤖" },
];

function App() {
  const [mode, setMode] = useState("area");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [showToast, setShowToast] = useState(false);

  const handleError = (msg) => {
    setError(msg);
    setShowToast(true);
    setLoading(false);
  };

  const onClear = () => {
    setResult(null);
    setError(null);
    setLoading(false);
  };

  const handleSubmit = async (prom) => {
    setLoading(true);
    setError(null);
    try {
      const res = await prom;
      setResult(res);
    } catch (err) {
      handleError(err?.message || "Network or server error.");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      <Header />
      
      <main className="app-container py-8 px-4 max-w-7xl mx-auto">
        {/* Mode Selector */}
        <div className="mb-8">
          <div className="flex flex-wrap gap-3 justify-center">
            {MODES.map((m) => (
              <button
                key={m.key}
                onClick={() => {
                  setMode(m.key);
                  onClear();
                }}
                className={`
                  px-6 py-3 rounded-xl font-semibold text-sm transition-all duration-200
                  flex items-center gap-2 shadow-md hover:shadow-lg transform hover:-translate-y-0.5
                  ${mode === m.key
                    ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white scale-105"
                    : "bg-white text-gray-700 hover:bg-gray-50"
                  }
                `}
              >
                <span className="text-xl">{m.icon}</span>
                {m.label}
              </button>
            ))}
          </div>
        </div>

        {/* Forms Section */}
        <div className="grid lg:grid-cols-2 gap-8 items-start">
          <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-800 mb-2">
                {MODES.find(m => m.key === mode)?.label}
              </h2>
              <p className="text-gray-600 text-sm">
                Enter your details to calculate solar requirements
              </p>
            </div>

            {mode === "area" && (
              <AreaForm onSubmit={handleSubmit} loading={loading} error={error} onClear={onClear} />
            )}
            {mode === "units" && (
              <UnitsForm onSubmit={handleSubmit} loading={loading} error={error} onClear={onClear} />
            )}
            {mode === "smart" && (
              <SmartForm onSubmit={handleSubmit} loading={loading} error={error} onClear={onClear} />
            )}
          </div>

          {/* Results Section */}
          <div>
            {loading && (
              <div className="bg-white rounded-2xl shadow-xl p-12 flex items-center justify-center">
                <Spinner />
              </div>
            )}
            
            {result && !loading && (
              <div className="animate-fadeIn">
                <ResultCard result={result} mode={mode} />
              </div>
            )}

            {!result && !loading && (
              <div className="bg-gradient-to-br from-blue-100 to-indigo-100 rounded-2xl shadow-xl p-12 text-center border-2 border-dashed border-blue-300">
                <div className="text-6xl mb-4">☀️</div>
                <h3 className="text-xl font-semibold text-gray-700 mb-2">
                  Ready to Calculate
                </h3>
                <p className="text-gray-600">
                  Fill out the form and click submit to see your solar estimation
                </p>
              </div>
            )}
          </div>
        </div>
      </main>

      {showToast && error && (
        <Toast message={error} onClose={() => setShowToast(false)} />
      )}
    </div>
  );
}

export default App;


