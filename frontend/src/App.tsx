import { useCallback, useEffect, useRef, useState } from 'react';
import { PanelLeftClose, PanelLeftOpen, TrendingUp, Building2 } from 'lucide-react';
import type { QuoteData } from './types';
import { fetchTickers, saveTickers, fetchQuote } from './api';
import { TickerSidebar } from './components/TickerSidebar';
import { Dashboard } from './components/Dashboard';
import { PriceCharts } from './components/PriceCharts';
import { TechnicalAnalysis } from './components/TechnicalAnalysis';
import { DataTable } from './components/DataTable';
import { RankTable } from './components/RankTable';
import { AiInsightsPanel } from './components/AiInsightsPanel';
import { PatentAnalysis } from './components/PatentAnalysis';
import { CompanySearch } from './components/CompanySearch';
import { CompanyAI } from './components/CompanyAI';
import { DkptoSearch } from './components/DkptoSearch';
import { StarsLeaderboard } from './components/StarsLeaderboard';
import { AlphaSignals } from './components/AlphaSignals';

type Tab = 'alpha' | 'dashboard' | 'charts' | 'technicals' | 'table' | 'rank' | 'ai' | 'patents' | 'company-search' | 'company-ai' | 'dkpto' | 'stars';

const C25_TICKERS = [
  'NOVO-B.CO', 'MAERSK-B.CO', 'DSV.CO', 'DANSKE.CO', 'VWS.CO',
  'CARL-B.CO', 'COLO-B.CO', 'GMAB.CO', 'NSIS-B.CO', 'ORSTED.CO',
  'PNDORA.CO', 'ROCK-B.CO', 'TRYG.CO', 'DEMANT.CO', 'GN.CO',
  'ISS.CO', 'JYSK.CO', 'RBREW.CO', 'AMBU-B.CO', 'FLS.CO',
  'BAVA.CO', 'NETC.CO', 'ZEAL.CO', 'NKT.CO', 'DNORD.CO',
];

export default function App() {
  const [tickers, setTickers] = useState<string[]>([]);
  const [quotes, setQuotes] = useState<Map<string, QuoteData>>(new Map());
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const savedTickersRef = useRef<string[]>([]);
  const [dirty, setDirty] = useState(false);
  const [c25Mode, setC25Mode] = useState(false);

  // Load tickers from server on mount (always reads fresh from tickers.yaml)
  useEffect(() => {
    fetchTickers().then((d) => {
      setTickers(d.tickers);
      savedTickersRef.current = d.tickers;
      setDirty(false);
    });
  }, []);

  // Fetch quotes when active tickers change
  useEffect(() => {
    const active = c25Mode ? C25_TICKERS : tickers;
    if (active.length === 0) return;
    const fetchAll = async () => {
      // Only fetch quotes we don't already have
      const toFetch = active.filter((t) => !quotes.has(t));
      if (toFetch.length === 0) return;
      const results = await Promise.allSettled(toFetch.map((t) => fetchQuote(t)));
      const newQuotes = new Map(quotes);
      results.forEach((r, i) => {
        if (r.status === 'fulfilled') {
          newQuotes.set(toFetch[i], r.value);
        }
      });
      setQuotes(newQuotes);
    };
    fetchAll();

    // Refresh quotes every 60 seconds
    const interval = setInterval(async () => {
      const curr = c25Mode ? C25_TICKERS : tickers;
      const results = await Promise.allSettled(curr.map((t) => fetchQuote(t)));
      const newQuotes = new Map(quotes);
      results.forEach((r, i) => {
        if (r.status === 'fulfilled') {
          newQuotes.set(curr[i], r.value);
        }
      });
      setQuotes(newQuotes);
    }, 60_000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickers, c25Mode]);

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

  const activeTickers = c25Mode ? C25_TICKERS : tickers;

  if (tickers.length === 0) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-gray-500 text-lg">Loading...</div>
      </div>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'alpha', label: 'Alpha-signals' },
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'charts', label: 'Charts' },
    { id: 'technicals', label: 'Technical Analysis' },
    { id: 'table', label: 'Data Table' },
    { id: 'rank', label: 'Rank' },
    { id: 'ai', label: 'AI Insights' },
    { id: 'patents', label: 'Patent AI' },
    { id: 'company-search', label: 'Technology Search' },
    { id: 'company-ai', label: 'Company AI' },
    { id: 'dkpto', label: 'DKPTO' },
    { id: 'stars', label: 'Stars' },
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
        {/* mr-24 keeps the toggle clear of the nginx-injected "Log ud" button (fixed top-right) */}
        <div className="ml-auto mr-24">
          <button
            onClick={() => setC25Mode(!c25Mode)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
              c25Mode
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Building2 size={15} />
            {c25Mode ? 'All C25' : 'My Stocks'}
          </button>
        </div>
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
            {activeTab === 'alpha' && <AlphaSignals />}
            {activeTab === 'dashboard' && <Dashboard tickers={activeTickers} quotes={quotes} dirty={dirty} onSave={handleSaveTickers} />}
            {activeTab === 'charts' && <PriceCharts tickers={activeTickers} />}
            {activeTab === 'technicals' && <TechnicalAnalysis tickers={activeTickers} />}
            {activeTab === 'table' && <DataTable tickers={activeTickers} />}
            {activeTab === 'rank' && <RankTable tickers={activeTickers} />}
            {activeTab === 'ai' && <AiInsightsPanel tickers={activeTickers} quotes={quotes} />}
            {activeTab === 'patents' && <PatentAnalysis tickers={activeTickers} />}
            {activeTab === 'company-search' && <CompanySearch />}
            {activeTab === 'company-ai' && <CompanyAI />}
            {activeTab === 'dkpto' && <DkptoSearch />}
            {activeTab === 'stars' && <StarsLeaderboard onAddTicker={handleAddTicker} />}
          </div>
        </main>
      </div>
    </div>
  );
}
