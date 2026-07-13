// ============================================================
// 🚀 TIKI ANALYST — App Shell (Sidebar + Header + Routing)
// ============================================================

const { useState, useEffect } = React;

function App() {
    const [activeTab, setActiveTab] = React.useState('market-report');

    React.useEffect(() => {
        lucide.createIcons();
    }, [activeTab]);

    const pageTitle = {
        'market-report': 'Phân Tích Đơn',
        'batch':         'Phân tích dữ liệu CSV',
        'market':        'Market Insight — Tìm Ngách Thị Trường',
    }[activeTab] || '';

    const navItems = [
        { tab: 'market-report', icon: 'bar-chart-2',  label: 'Phân Tích Đơn'  },
        { tab: 'batch',         icon: 'upload-cloud', label: 'Phân tích loạt (CSV)'  },
        { tab: 'market',        icon: 'telescope',    label: 'Market Insight'        },
    ];

    return (
        <div className="flex h-screen bg-[#eff6ff] overflow-hidden">

            {/* ── SIDEBAR ───────────────────────────────────── */}
            <div className="w-64 sidebar-modern flex flex-col z-20">

                {/* Logo */}
                <div className="p-6 flex items-center gap-3 border-b border-blue-200">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center text-white shadow-lg">
                        <Icon name="sparkles" size={20} />
                    </div>
                    <div>
                        <h1 className="font-bold text-lg text-gray-900 tracking-tight">TikiAnalyst</h1>
                        <p className="text-xs text-gray-500">AI-Powered Analytics</p>
                    </div>
                </div>

                {/* Navigation */}
                <nav className="flex-1 p-4 space-y-2">
                    {navItems.map(({ tab, icon, label }) => (
                        <button
                            key={tab}
                            type="button"
                            onClick={() => setActiveTab(tab)}
                            className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                                activeTab === tab
                                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-md'
                                    : 'text-gray-600 hover:bg-blue-100/60 hover:text-blue-900'
                            }`}
                        >
                            <Icon name={icon} size={18} /> {label}
                        </button>
                    ))}

                    {/* System Info */}
                    <div className="pt-4 mt-4 border-t border-blue-200">
                        <p className="px-4 text-xs font-semibold text-gray-500 uppercase mb-2">Hệ thống</p>
                        <div className="px-4 py-2 text-sm text-gray-600 flex items-center gap-2">
                            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                            API: {API_BASE_URL}
                        </div>
                        <div className="px-4 py-2 text-sm text-gray-600 flex items-center gap-2">
                            <Icon name="database" size={14} /> Source: Delta Lake
                        </div>
                    </div>
                </nav>

                <div className="p-4 border-t border-blue-200 text-xs text-gray-500 text-center">
                    v1.0.0 • Fresh Blue Design
                </div>
            </div>

            {/* ── MAIN CONTENT ──────────────────────────────── */}
            <div className="flex-1 flex flex-col overflow-hidden relative">

                {/* Header */}
                <header className="h-16 gradient-header border-b border-blue-200 flex items-center justify-between px-8 z-10">
                    <h2 className="text-xl font-bold text-gray-900">{pageTitle}</h2>
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-white font-bold border border-blue-300 shadow-sm">
                        A
                    </div>
                </header>

                {/* Scrollable page area */}
                <main className="flex-1 overflow-y-auto p-8 scroll-smooth bg-gradient-to-b from-white to-blue-50">
                    <div style={{ display: activeTab === 'market-report' ? 'block' : 'none' }}>
                        <MarketReportPage />
                    </div>
                    <div style={{ display: activeTab === 'batch' ? 'block' : 'none' }}>
                        <BatchPage />
                    </div>
                    <div style={{ display: activeTab === 'market' ? 'block' : 'none' }}>
                        <MarketInsightPage />
                    </div>
                </main>

            </div>
        </div>
    );
}

// Mount app
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
