import { useRef, useState } from 'react';
import { Send, Loader2, Bot, User } from 'lucide-react';
import type { ChatMessage, QuoteData } from '../types';
import { sendChatMessage } from '../api';

interface Props {
  tickers: string[];
  quotes: Map<string, QuoteData>;
}

export function AiInsightsPanel({ tickers, quotes }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: 'user', content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      const quotesList = tickers
        .map((t) => quotes.get(t))
        .filter((q): q is QuoteData => q != null)
        .map((q) => ({ ticker: q.ticker, price: q.price, change_pct: q.change_pct, name: q.name }));

      const response = await sendChatMessage(
        newMessages.map((m) => ({ role: m.role, content: m.content })),
        { tickers, quotes: quotesList },
      );

      setMessages([...newMessages, { role: 'assistant', content: response.reply }]);
    } catch {
      setMessages([...newMessages, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }]);
    } finally {
      setLoading(false);
      setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }), 50);
    }
  };

  return (
    <div className="flex flex-col h-full max-h-[calc(100vh-200px)]">
      <div className="bg-white rounded-xl border border-gray-200 flex flex-col flex-1 overflow-hidden">
        {/* Header */}
        <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
          <Bot size={18} className="text-blue-500" />
          <h3 className="text-sm font-semibold text-gray-700">AI Market Insights</h3>
          <span className="text-xs text-gray-400 ml-auto">Powered by Databricks GPT-5.2</span>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 py-12">
              <Bot size={40} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">Ask about your tracked stocks, technical indicators, or market trends.</p>
              <div className="flex flex-wrap justify-center gap-2 mt-4">
                {[
                  `What's the outlook for ${tickers[0] ?? 'AAPL'}?`,
                  'Compare the momentum of my tickers',
                  'Which of my stocks looks overbought?',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setInput(suggestion)}
                    className="text-xs px-3 py-1.5 bg-gray-100 text-gray-600 rounded-full hover:bg-gray-200 transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
              {msg.role === 'assistant' && (
                <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
                  <Bot size={14} className="text-blue-600" />
                </div>
              )}
              <div
                className={`max-w-[80%] px-4 py-2.5 rounded-xl text-sm leading-relaxed whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                {msg.content}
              </div>
              {msg.role === 'user' && (
                <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center shrink-0">
                  <User size={14} className="text-gray-600" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3">
              <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
                <Bot size={14} className="text-blue-600" />
              </div>
              <div className="bg-gray-100 rounded-xl px-4 py-3">
                <Loader2 size={16} className="animate-spin text-gray-400" />
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-100">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder="Ask about stocks, technicals, or market trends..."
              className="flex-1 px-4 py-2.5 text-sm border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="p-2.5 bg-blue-500 text-white rounded-xl hover:bg-blue-600 disabled:opacity-50 transition-colors"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
