"use client";

import { useState } from "react";
import Link from "next/link";

export default function AdminDashboard() {
  const [newName, setNewName] = useState("");
  const [newStock, setNewStock] = useState(100);
  const [newPrice, setNewPrice] = useState(999.99);

  const [updateName, setUpdateName] = useState("");
  const [updateStock, setUpdateStock] = useState(500);

  const [numUsers, setNumUsers] = useState(2000);
  const [minAmount, setMinAmount] = useState(500);
  const [maxAmount, setMaxAmount] = useState(5000);

  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);

  const addLog = (message) => setLogs((prev) => [message, ...prev]);

  const handleCreateProduct = async (e) => {
    e.preventDefault();
    if (!newName) return;
    setLoading(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/admin/product", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName, stock: parseInt(newStock), price: parseFloat(newPrice) }),
      });
      // BUG FIX: always parse the body — FastAPI errors arrive as { detail: "..." }
      const data = await res.json();
      if (res.ok) {
        addLog(`✅ Product Added: ${newName}`);
        setNewName("");
      } else {
        // res.ok is false for 4xx/5xx — show the actual server message
        addLog(`❌ Error: ${data.detail || "Failed to create product."}`);
      }
    } catch { addLog("❌ Network Error."); }
    setLoading(false);
  };

  const handleUpdateInventory = async (e) => {
    e.preventDefault();
    if (!updateName) return;
    setLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/admin/product/${updateName.toLowerCase()}?new_stock=${updateStock}`, { method: "PUT" });
      // BUG FIX: always parse the body — FastAPI errors arrive as { detail: "..." }
      const data = await res.json();
      if (res.ok) {
        addLog(`✅ Inventory Synced: ${updateName} → ${updateStock} units`);
        setUpdateName("");
      } else {
        addLog(`❌ Error: ${data.detail || "Failed to update inventory."}`);
      }
    } catch { addLog("❌ Network Error."); }
    setLoading(false);
  };

  const handleSeedWallets = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/admin/seed-wallets?num_users=${numUsers}&min_amount=${minAmount}&max_amount=${maxAmount}`, { method: "POST" });
      if (res.ok) addLog(`Wallets Seeded: ${numUsers} users`);
      else addLog("Error generating wallets.");
    } catch { addLog("Network Error."); }
    setLoading(false);
  };

  return (
    <main className="min-h-screen bg-[#F5F5F7] text-[#1D1D1F] p-8 md:p-16 font-sans">
      <div className="max-w-6xl mx-auto">
        
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-12">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">System Configuration</h1>
            <p className="text-gray-500 mt-1">Manage state and simulation parameters.</p>
          </div>
          <Link href="/" className="mt-4 md:mt-0 text-sm font-medium text-gray-500 hover:text-black transition-colors px-4 py-2 bg-white rounded-full border border-gray-200 shadow-sm">
            Exit to Storefront
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          
          {/* Card 1: New Product */}
          <form onSubmit={handleCreateProduct} className="bg-white p-8 rounded-3xl border border-gray-200 shadow-sm flex flex-col justify-between h-full">
            <div>
              <h2 className="text-sm font-semibold mb-6 tracking-tight">Add Product</h2>
              <div className="space-y-4 text-sm">
                <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Product Name" className="w-full bg-[#F5F5F7] border-none rounded-xl p-3 focus:ring-2 focus:ring-[#0071e3] transition-all outline-none" />
                <div className="flex space-x-3">
                  <input type="number" value={newStock} onChange={(e) => setNewStock(e.target.value)} placeholder="Stock" className="w-full bg-[#F5F5F7] border-none rounded-xl p-3 focus:ring-2 focus:ring-[#0071e3] transition-all outline-none" />
                  <input type="number" step="0.01" value={newPrice} onChange={(e) => setNewPrice(e.target.value)} placeholder="Price" className="w-full bg-[#F5F5F7] border-none rounded-xl p-3 focus:ring-2 focus:ring-[#0071e3] transition-all outline-none" />
                </div>
              </div>
            </div>
            <button type="submit" disabled={loading} className="w-full bg-black hover:bg-gray-800 text-white font-medium py-3 rounded-full mt-8 transition-transform active:scale-95 disabled:opacity-50">
              Save
            </button>
          </form>

          {/* Card 2: Inventory */}
          <form onSubmit={handleUpdateInventory} className="bg-white p-8 rounded-3xl border border-gray-200 shadow-sm flex flex-col justify-between h-full">
            <div>
              <h2 className="text-sm font-semibold mb-6 tracking-tight">Sync Inventory</h2>
              <div className="space-y-4 text-sm">
                <input type="text" value={updateName} onChange={(e) => setUpdateName(e.target.value)} placeholder="Target Product" className="w-full bg-[#F5F5F7] border-none rounded-xl p-3 focus:ring-2 focus:ring-[#0071e3] transition-all outline-none" />
                <input type="number" value={updateStock} onChange={(e) => setUpdateStock(e.target.value)} placeholder="New Quantity" className="w-full bg-[#F5F5F7] border-none rounded-xl p-3 focus:ring-2 focus:ring-[#0071e3] transition-all outline-none" />
              </div>
            </div>
            <button type="submit" disabled={loading} className="w-full bg-black hover:bg-gray-800 text-white font-medium py-3 rounded-full mt-8 transition-transform active:scale-95 disabled:opacity-50">
              Update
            </button>
          </form>

          {/* Card 3: Wallets */}
          <form onSubmit={handleSeedWallets} className="bg-white p-8 rounded-3xl border border-gray-200 shadow-sm flex flex-col justify-between h-full">
            <div>
              <h2 className="text-sm font-semibold mb-6 tracking-tight">Seed Data</h2>
              <div className="space-y-4 text-sm">
                <input type="number" value={numUsers} onChange={(e) => setNumUsers(e.target.value)} placeholder="Total Users" className="w-full bg-[#F5F5F7] border-none rounded-xl p-3 focus:ring-2 focus:ring-[#0071e3] transition-all outline-none" />
                <div className="flex space-x-3">
                  <input type="number" value={minAmount} onChange={(e) => setMinAmount(e.target.value)} placeholder="Min ₹" className="w-full bg-[#F5F5F7] border-none rounded-xl p-3 focus:ring-2 focus:ring-[#0071e3] transition-all outline-none" />
                  <input type="number" value={maxAmount} onChange={(e) => setMaxAmount(e.target.value)} placeholder="Max ₹" className="w-full bg-[#F5F5F7] border-none rounded-xl p-3 focus:ring-2 focus:ring-[#0071e3] transition-all outline-none" />
                </div>
              </div>
            </div>
            <button type="submit" disabled={loading} className="w-full bg-black hover:bg-gray-800 text-white font-medium py-3 rounded-full mt-8 transition-transform active:scale-95 disabled:opacity-50">
              Generate
            </button>
          </form>
        </div>

        {/* Console Log */}
        <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-200 font-mono text-xs h-[250px] flex flex-col">
          <div className="flex justify-between items-center mb-4 border-b border-gray-100 pb-4">
            <h3 className="text-gray-400 font-semibold uppercase tracking-widest">Admin Logs</h3>
            <button onClick={() => setLogs([])} className="text-gray-400 hover:text-black transition-colors">Clear</button>
          </div>
          <div className="flex-1 overflow-y-auto space-y-3 text-gray-600">
            {logs.length === 0 ? (
              <p className="text-gray-400 italic">No operations executed...</p>
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

      </div>
    </main>
  );
}