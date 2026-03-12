import { useCallback, useEffect, useRef, useState } from 'react';
import { PanelLeftClose, PanelLeftOpen, TrendingUp } from 'lucide-react';
import type { QuoteData } from './types';
import { fetchTickers, saveTickers, fetchQuote } from './api';
import { TickerSidebar } from './components/TickerSidebar';
import { Dashboard } from './components/Dashboard';
import { PriceCharts } from './components/PriceCharts';
import { TechnicalAnalysis } from './components/TechnicalAnalysis';
import { DataTable } from './components/DataTable';
import { RankTable } from './components/RankTable';
import { AiInsightsPanel } from './components/AiInsightsPanel';

type Tab = 'dashboard' | 'charts' | 'technicals' | 'table' | 'rank' | 'ai';

export default function App() {
  const [tickers, setTickers] = useState<string[]>([]);
  const [quotes, setQuotes] = useState<Map<string, QuoteData>>(new Map());
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const savedTickersRef = useRef<string[]>([]);
  const [dirty, setDirty] = useState(false);

  // Load tickers from server on mount (always reads fresh from tickers.yaml)
  useEffect(() => {
    fetchTickers().then((d) => {
      setTickers(d.tickers);
      savedTickersRef.current = d.tickers;
      setDirty(false);
    });
  }, []);

  // Fetch quotes when tickers change
  useEffect(() => {
    if (tickers.length === 0) return;
    const fetchAll = async () => {
      const results = await Promise.allSettled(tickers.map((t) => fetchQuote(t)));
      const newQuotes = new Map(quotes);
      results.forEach((r, i) => {
        if (r.status === 'fulfilled') {
          newQuotes.set(tickers[i], r.value);
        }
      });
      setQuotes(newQuotes);
    };
    fetchAll();

    // Refresh quotes every 60 seconds
    const interval = setInterval(fetchAll, 60_000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickers]);

  const handleAddTicker = useCallback((ticker: string) => {
    setTickers((prev) => {
      const next = [...prev, ticker];
      setDirty(JSON.stringify(next) !== JSON.stringify(savedTickersRef.current));
      return next;
    });
  }, []);

  const handleRemoveTicker = useCallback((ticker: string) => {
    setTickers((prev) => {
      const next = prev.filter((t) => t !== ticker);
      setDirty(JSON.stringify(next) !== JSON.stringify(savedTickersRef.current));
      return next;
    });
    setQuotes((prev) => {
      const next = new Map(prev);
      next.delete(ticker);
      return next;
    });
  }, []);

  const handleSaveTickers = useCallback(async () => {
    await saveTickers(tickers);
    savedTickersRef.current = tickers;
    setDirty(false);
  }, [tickers]);

  if (tickers.length === 0) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-gray-500 text-lg">Loading...</div>
      </div>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'charts', label: 'Charts' },
    { id: 'technicals', label: 'Technical Analysis' },
    { id: 'table', label: 'Data Table' },
    { id: 'rank', label: 'Rank' },
    { id: 'ai', label: 'AI Insights' },
  ];

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3 shrink-0">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-1.5 rounded hover:bg-gray-100 text-gray-500"
        >
          {sidebarOpen ? <PanelLeftClose size={20} /> : <PanelLeftOpen size={20} />}
        </button>
        <TrendingUp size={22} className="text-blue-500" />
        <h1 className="text-xl font-semibold text-gray-800">Stock Ticker Analyzer</h1>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        {sidebarOpen && (
          <aside className="w-64 bg-white border-r border-gray-200 overflow-y-auto shrink-0">
            <TickerSidebar
              tickers={tickers}
              quotes={quotes}
              onAdd={handleAddTicker}
              onRemove={handleRemoveTicker}
            />
          </aside>
        )}

        {/* Main */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Tabs */}
          <div className="bg-white border-b border-gray-200 px-4 flex gap-1 shrink-0">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-auto p-4">
            {activeTab === 'dashboard' && <Dashboard tickers={tickers} quotes={quotes} dirty={dirty} onSave={handleSaveTickers} />}
            {activeTab === 'charts' && <PriceCharts tickers={tickers} />}
            {activeTab === 'technicals' && <TechnicalAnalysis tickers={tickers} />}
            {activeTab === 'table' && <DataTable tickers={tickers} />}
            {activeTab === 'rank' && <RankTable tickers={tickers} />}
            {activeTab === 'ai' && <AiInsightsPanel tickers={tickers} quotes={quotes} />}
          </div>
        </main>
      </div>
    </div>
  );
}
