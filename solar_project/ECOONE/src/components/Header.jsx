import React from "react";

function Header() {
  return (
    <header className="bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 text-white shadow-2xl">
      <div className="app-container py-8 px-4 max-w-7xl mx-auto">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 bg-white/20 backdrop-blur-sm rounded-2xl flex items-center justify-center text-4xl shadow-lg">
              ☀️
            </div>
            <div>
              <h1 className="text-3xl md:text-4xl font-bold tracking-tight">
                Smart Solar Calculator
              </h1>
              <p className="text-blue-100 text-sm md:text-base mt-1">
                Estimate your solar panel requirements instantly
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 bg-white/20 backdrop-blur-sm px-4 py-2 rounded-xl">
            <span className="text-2xl">🔆</span>
            <span className="font-semibold">AI-Powered</span>
          </div>
        </div>
      </div>
    </header>
  );
}

export default Header;
