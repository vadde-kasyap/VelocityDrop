"use client";

import { useState, useEffect } from "react";

export default function Storefront() {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [userId, setUserId] = useState("user_1"); 
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]); 

  useEffect(() => {
    if (query.length < 1) {
      setSuggestions([]);
      return;
    }
    const fetchSuggestions = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/search?q=${query}`);
        const data = await res.json();
        setSuggestions(data.results || []);
      } catch (error) {
        console.error("Search failed:", error);
      }
    };
    const timeoutId = setTimeout(() => fetchSuggestions(), 150);
    return () => clearTimeout(timeoutId);
  }, [query]);

  const handleCheckout = async () => {
    if (!selectedProduct) return;
    setLoading(true);
    addLog(`Processing ${quantity}x ${selectedProduct}...`);

    try {
      const res = await fetch("http://127.0.0.1:8000/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          product_name: selectedProduct,
          quantity: parseInt(quantity),
        }),
      });

      const data = await res.json();
      if (res.ok) {
        addLog(`Confirmed. Queue ID: ${data.idempotency_key.substring(0, 8)}`);
      } else {
        addLog(`Error: ${data.detail || "Validation Failed"}`);
      }
    } catch (error) {
      addLog("Network Error: Backend unreachable.");
    }
    setLoading(false);
  };

  const addLog = (message) => setLogs((prev) => [message, ...prev]);

  return (
    <main className="min-h-screen bg-[#F5F5F7] text-[#1D1D1F] px-6 py-16 md:px-24 font-sans selection:bg-blue-200">
      <div className="max-w-4xl mx-auto">
        
        <header className="mb-12 text-center md:text-left">
          <h1 className="text-4xl md:text-5xl font-semibold tracking-tight mb-2">VelocityDrop</h1>
          <p className="text-gray-500 text-lg tracking-wide">High-concurrency architecture.</p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-8">
          
          {/* Main Interface */}
          <section className="md:col-span-3 space-y-6">
            <div className="bg-white p-8 rounded-3xl shadow-sm border border-gray-200 relative">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search products..."
                className="w-full text-xl bg-transparent border-none p-2 focus:outline-none placeholder-gray-300 font-medium"
              />
              
              {suggestions.length > 0 && (
                <ul className="absolute left-0 w-full bg-white border border-gray-100 rounded-2xl mt-4 overflow-hidden z-10 shadow-xl">
                  {suggestions.map((item, idx) => (
                    <li 
                      key={idx}
                      onClick={() => {
                        setSelectedProduct(item);
                        setQuery(item);
                        setSuggestions([]);
                      }}
                      className="p-4 px-8 hover:bg-gray-50 cursor-pointer capitalize transition-colors border-b border-gray-50 last:border-0"
                    >
                      {item}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {selectedProduct && (
              <div className="bg-white p-8 rounded-3xl shadow-sm border border-gray-200 animate-in fade-in duration-500">
                <h2 className="text-2xl font-medium capitalize mb-8">{selectedProduct}</h2>
                
                <div className="flex space-x-6 mb-8">
                  <div className="flex-1">
                    <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-widest">Qty</label>
                    <input 
                      type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)}
                      className="w-full bg-gray-50 rounded-xl p-3 focus:outline-none focus:ring-2 focus:ring-[#0071e3] transition-all"
                    />
                  </div>
                  <div className="flex-1">
                    <label className="block text-xs font-semibold text-gray-400 mb-2 uppercase tracking-widest">User ID</label>
                    <input 
                      type="text" value={userId} onChange={(e) => setUserId(e.target.value)}
                      className="w-full bg-gray-50 rounded-xl p-3 focus:outline-none focus:ring-2 focus:ring-[#0071e3] transition-all"
                    />
                  </div>
                </div>

                <button 
                  onClick={handleCheckout} disabled={loading}
                  className="w-full bg-[#0071e3] hover:bg-[#0077ED] text-white font-medium py-4 rounded-full transition-transform active:scale-95 disabled:opacity-50"
                >
                  {loading ? "Processing" : "Buy Now"}
                </button>
              </div>
            )}
          </section>

          {/* Clean Diagnostic Terminal */}
          <aside className="md:col-span-2">
            <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-200 font-mono text-xs h-[400px] flex flex-col">
              <div className="flex justify-between items-center mb-4 border-b border-gray-100 pb-4">
                <h3 className="text-gray-400 font-semibold uppercase tracking-widest">System Logs</h3>
                <button onClick={() => setLogs([])} className="text-gray-400 hover:text-black transition-colors">Clear</button>
              </div>
              <div className="flex-1 overflow-y-auto space-y-3 text-gray-600">
                {logs.length === 0 ? (
                  <p className="text-gray-400 italic">Idle...</p>
                ) : (
                  logs.map((log, i) => (
                    <div key={i} className="leading-relaxed">
                      <span className="text-gray-400 mr-2">[{new Date().toLocaleTimeString()}]</span>
                      {log}
                    </div>
                  ))
                )}
              </div>
            </div>
          </aside>

        </div>
      </div>
    </main>
  );
}