// ============================================================
// 🌊 MARKET INSIGHT PAGE — KMeans Blue Ocean Analysis (v2)
// ============================================================

function MarketInsightPage() {
    const { useState, useEffect, useRef } = React;

    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [currentPage, setCurrentPage] = useState(1);
    const [activeStrategy, setActiveStrategy] = useState('🌊 Đại Dương Xanh');
    const [reviewModal, setReviewModal] = useState({ open: false, product: null, reviews: [], loading: false, error: null });

    const [selectedCategory, setSelectedCategory] = useState('all');   // for pre-analysis filter
    const [categories, setCategories] = useState([]);       // loaded from CSV via API
    const [catLoading, setCatLoading] = useState(false);
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const [catSearch, setCatSearch] = useState('');


    const dropdownRef = useRef(null);

    // Close dropdown on outside click
    useEffect(() => {
        const handler = (e) => {
            // Use composedPath() to handle lucide SVG icon replacements inside the button
            const path = e.composedPath ? e.composedPath() : [e.target];
            // Check if click is outside the dropdown
            if (dropdownRef.current && !dropdownRef.current.contains(e.target) && !path.includes(dropdownRef.current)) {
                setDropdownOpen(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);



    // Load categories from CSV on mount
    useEffect(() => {
        setCatLoading(true);
        fetch(`${API_BASE_URL}/api/categories`)
            .then(r => r.ok ? r.json() : Promise.reject(r.status))
            .then(json => setCategories(json.categories || []))
            .catch(err => console.warn('Could not load categories:', err))
            .finally(() => setCatLoading(false));
    }, []);

    // fetch market insight
    const handleMarketInsight = async () => {
        setLoading(true);
        setResult(null);
        setCurrentPage(1);
        try {
            const params = selectedCategory !== 'all' ? `?category=${encodeURIComponent(selectedCategory)}` : '';
            const res = await fetch(`${API_BASE_URL}/api/market-insight${params}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            setResult(json.data);
        } catch (e) {
            setResult({ error: e.message });
        } finally {
            setLoading(false);
        }
    };

    const handleOpenReviews = async (product) => {
        setReviewModal({ open: true, product, reviews: [], loading: true, error: null });
        try {
            const res = await fetch(`${API_BASE_URL}/api/product-reviews/${product.product_id}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            setReviewModal({ open: true, product, reviews: json.data || [], loading: false, error: null });
        } catch (e) {
            setReviewModal(prev => ({ ...prev, loading: false, error: e.message }));
        }
    };

    useEffect(() => { setTimeout(() => lucide.createIcons(), 100); }, [result, dropdownOpen, categories, reviewModal.open]);



    // table helpers
    const getTableData = () => {
        if (!result || result.error || !result.all_products) return [];
        let rows = result.all_products;
        const rt = result.rating_threshold || 4.0;
        const pt = result.pop_threshold || 5.0;
        const pt2 = pt * 0.5;
        const at = result.avg_price_threshold || 0;

        if (activeStrategy === '🌊 Đại Dương Xanh') {
            rows = rows.filter(p => p.rating <= rt && p.popularity_score >= pt);
        } else if (activeStrategy === '⚡ Đại Trà') {
            rows = rows.filter(p => p.rating > rt && p.popularity_score >= pt);
        } else if (activeStrategy === '💎 Cao Cấp') {
            rows = rows.filter(p => p.price > at && p.rating > rt);
        } else if (activeStrategy === '🔍 Ngách Nhỏ') {
            rows = rows.filter(p => p.popularity_score < pt);
        } else if (activeStrategy === '📈 Tăng Trưởng') {
            rows = rows.filter(p => p.rating >= rt && p.popularity_score >= pt2 && p.popularity_score < pt);
        }

        return [...rows].sort((a, b) => (b.popularity_score || 0) - (a.popularity_score || 0));
    };

    const STRATEGY = [
        { icon: 'rocket', color: 'text-blue-500', bg: 'border-blue-300/40  bg-cyan-900/20', title: '🌊 Đại Dương Xanh', desc: 'Rating thấp + Popularity cao — nhu cầu thị trường chưa được đáp ứng. Cơ hội vàng để nhập hàng chất lượng cao và chiếm thị phần.' },
        { icon: 'zap', color: 'text-yellow-400', bg: 'border-amber-400/30 bg-amber-50', title: '⚡ Đại Trà', desc: 'Rating tốt + Popularity cao — thị trường bão hòa. Chiến lược: cạnh tranh giá hoặc bundle sản phẩm kèm dịch vụ.' },
        { icon: 'gem', color: 'text-violet-400', bg: 'border-violet-400/30 bg-violet-50', title: '💎 Cao Cấp', desc: 'Giá cao + Rating tốt — phân khúc premium. Tập trung thương hiệu, uy tín và trải nghiệm khách hàng.' },
        { icon: 'search', color: 'text-blue-400', bg: 'border-blue-300/30 bg-blue-50/50', title: '🔍 Ngách Nhỏ', desc: 'Popularity thấp — thị trường chưa khai thác rõ. Cần khảo sát trước khi đầu tư. Rủi ro cao, tiềm năng chưa rõ.' },
        { icon: 'trending-up', color: 'text-emerald-400', bg: 'border-emerald-400/30 bg-emerald-50', title: '📈 Tăng Trưởng', desc: 'Rating khá + Popularity đang tăng — đang trong giai đoạn phát triển. Nhập hàng sớm để nắm lợi thế người đi trước.' },
    ];

    const filteredCategories = categories.filter(cat => 
        cat && cat.toLowerCase().includes(catSearch.toLowerCase())
    );
    const displayedCategories = filteredCategories.slice(0, 100);

    return (
        <>
            <div className="pb-10">

                {/* ACTION */}
                <div className="max-w-4xl mx-auto mb-8 relative z-50">
                    <div className="glass-panel p-6 rounded-xl animate-fade-in">
                        <p className="text-gray-700 text-sm mb-5 text-center">
                            Phân tích toàn bộ sản phẩm bằng <strong>K-Means Clustering </strong> dựa trên Giá · Rating · Popularity để tìm cơ hội có thể triển khai.
                        </p>

                        {/* Dropdown + Button — same row */}
                        <div className="flex flex-wrap items-center justify-center gap-3">

                            {/* Custom Dropdown */}
                            <div className="relative" ref={dropdownRef}>
                                {/* Trigger */}
                                <button
                                    onClick={() => { setDropdownOpen(o => !o); setCatSearch(''); }}
                                    disabled={loading}
                                    className="flex items-center gap-2.5 bg-white hover:bg-blue-50 border border-gray-300 hover:border-gray-500 rounded-lg px-4 py-2.5 text-sm text-gray-800 transition-all disabled:opacity-50 min-w-[250px] justify-between shadow-sm"
                                >
                                    <div className="flex items-center gap-2 overflow-hidden">
                                        <Icon name="layout-grid" size={14} className="text-blue-500 flex-shrink-0" />
                                        <span className="font-medium truncate">
                                            {selectedCategory === 'all' ? 'Tất cả danh mục' : selectedCategory}
                                        </span>
                                    </div>
                                    <Icon name={dropdownOpen ? 'chevron-up' : 'chevron-down'} size={14} className="text-gray-500 flex-shrink-0" />
                                </button>

                                {/* Dropdown list */}
                                {dropdownOpen && (
                                    <div className="absolute z-50 top-full mt-1 left-0 w-full min-w-[280px] bg-white border border-gray-300 rounded-lg shadow-2xl overflow-hidden flex flex-col">
                                        {/* Search Input */}
                                        <div className="p-2 border-b border-gray-200 bg-gray-50">
                                            <input
                                                type="text"
                                                placeholder="Tìm danh mục..."
                                                value={catSearch}
                                                onChange={(e) => setCatSearch(e.target.value)}
                                                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-gray-800"
                                                autoFocus
                                            />
                                        </div>
                                        
                                        <div className="max-h-64 overflow-y-auto">
                                            {/* Tất cả */}
                                            <button
                                                onClick={() => { setSelectedCategory('all'); setDropdownOpen(false); setCatSearch(''); }}
                                                className={`w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-left transition-colors ${selectedCategory === 'all'
                                                    ? 'bg-blue-50 text-gray-900 font-medium'
                                                    : 'text-gray-700 hover:bg-blue-50 hover:text-gray-900'
                                                    }`}
                                            >
                                                <Icon name="layout-grid" size={13} className={selectedCategory === 'all' ? 'text-blue-500' : 'text-gray-500'} />
                                                Tất cả danh mục
                                                {selectedCategory === 'all' && <Icon name="check" size={13} className="ml-auto text-blue-500" />}
                                            </button>

                                            {/* Separator */}
                                            <div className="border-t border-blue-100 mx-3" />

                                            {/* Category items */}
                                            {catLoading ? (
                                                <div className="px-4 py-3 text-xs text-gray-500 animate-pulse">Đang tải danh mục...</div>
                                            ) : displayedCategories.length === 0 ? (
                                                <div className="px-4 py-3 text-sm text-gray-500">Không tìm thấy danh mục nào.</div>
                                            ) : (
                                                <>
                                                    {displayedCategories.map(cat => (
                                                        <button
                                                            key={cat}
                                                            onClick={() => { setSelectedCategory(cat); setDropdownOpen(false); setCatSearch(''); }}
                                                            className={`w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-left transition-colors ${selectedCategory === cat
                                                                ? 'bg-blue-50 text-gray-900 font-medium'
                                                                : 'text-gray-700 hover:bg-blue-50 hover:text-gray-900'
                                                                }`}
                                                        >
                                                            <Icon name="tag" size={13} className={selectedCategory === cat ? 'text-blue-500' : 'text-gray-500'} />
                                                            <span className="truncate">{cat}</span>
                                                            {selectedCategory === cat && <Icon name="check" size={13} className="ml-auto text-blue-500" />}
                                                        </button>
                                                    ))}
                                                    
                                                    {filteredCategories.length > 100 && (
                                                        <div className="px-4 py-2 text-xs text-gray-400 border-t border-gray-100 bg-gray-50 text-center">
                                                            ...và {filteredCategories.length - 100} danh mục khác (nhập để tìm thêm)
                                                        </div>
                                                    )}
                                                </>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Run button */}
                            <button onClick={handleMarketInsight} disabled={loading}
                                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 text-white font-bold rounded-lg flex items-center gap-2 transition-all shadow-lg shadow-blue-200">
                                {loading ? <Icon name="loader-2" className="animate-spin" /> : <Icon name="telescope" />}
                                {loading ? 'Đang phân tích...' : 'Chạy phân tích KMeans'}
                            </button>
                        </div>
                    </div>
                </div>

                {/* LOADING */}
                {loading && (
                    <div className="flex flex-col items-center justify-center py-20 text-blue-500 animate-pulse">
                        <Icon name="bot" size={48} className="mb-4" />
                        <p className="text-lg font-medium">Đang phân tích clusters...</p>
                    </div>
                )}

                {/* ERROR */}
                {!loading && result && result.error && (
                    <div className="bg-red-50 border border-red-500 rounded-xl p-5 text-red-600 max-w-4xl mx-auto">
                        ❌ Lỗi: {result.error}
                    </div>
                )}

                {/* RESULTS */}
                {!loading && result && !result.error && (
                    <div className="max-w-6xl mx-auto space-y-8 animate-fade-in">

                        <div className="bg-white border border-blue-100 rounded-xl p-4 text-sm text-gray-700 shadow-sm flex flex-wrap items-center gap-4">
                            <span>Rating TB thị trường: <span className="font-semibold text-blue-700">{Number(result.market_avg_rating || 0).toFixed(2)}</span></span>
                            <span>• Ngưỡng cơ hội hiện tại: <span className="font-semibold text-yellow-300">{Number(result.rating_threshold || 0).toFixed(2)}</span></span>
                            {selectedCategory !== 'all' && (
                                <span className="ml-auto flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 border border-red-300/40 text-blue-700">
                                    <Icon name="filter" size={12} /> Danh mục: {selectedCategory}
                                </span>
                            )}
                        </div>

                        {/* KPI CARDS */}
                        {(() => {
                            const strategyCardMap = {
                                '🌊 Đại Dương Xanh': { icon: 'waves',       label: 'Sản phẩm Blue Ocean', color: 'text-blue-500',    border: 'border-blue-300/40' },
                                '⚡ Đại Trà':         { icon: 'zap',         label: 'Sản phẩm Đại Trà',    color: 'text-yellow-400',  border: 'border-yellow-500/30' },
                                '💎 Cao Cấp':         { icon: 'gem',         label: 'Sản phẩm Cao Cấp',    color: 'text-violet-400',  border: 'border-violet-400/30' },
                                '🔍 Ngách Nhỏ':       { icon: 'search',      label: 'Sản phẩm Ngách Nhỏ',  color: 'text-blue-400',    border: 'border-blue-300/30' },
                                '📈 Tăng Trưởng':     { icon: 'trending-up', label: 'Sản phẩm Tăng Trưởng',color: 'text-emerald-400', border: 'border-emerald-400/30' },
                            };
                            const activeCard = strategyCardMap[activeStrategy] || strategyCardMap['🌊 Đại Dương Xanh'];
                            const activeCount = getTableData().length;
                            const cards = [
                                { icon: 'package', label: 'Tổng sản phẩm',   value: result.total_products.toLocaleString('vi-VN'), color: 'text-blue-400',   border: 'border-blue-500/30' },
                                { icon: 'star',    label: 'Rating Trung Bình', value: Number(result.market_avg_rating || 0).toFixed(2), color: 'text-yellow-400', border: 'border-yellow-500/30' },
                                { ...activeCard,   value: activeCount.toLocaleString('vi-VN') },
                            ];
                            return (
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                                    {cards.map(({ icon, label, value, color, border }) => (
                                        <div key={label} className={`bg-white rounded-xl border ${border} p-5 flex items-center gap-4`}>
                                            <div className={`w-10 h-10 rounded-lg bg-white flex items-center justify-center flex-shrink-0 ${color}`}>
                                                <Icon name={icon} size={20} />
                                            </div>
                                            <div>
                                                <p className="text-xs text-gray-500 mb-0.5">{label}</p>
                                                <p className={`text-xl font-bold ${color}`}>{value}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            );
                        })()}





                        {/* STRATEGY PANEL */}
                        <div>
                            <h3 className="font-bold text-gray-900 mb-3 flex items-center gap-2">
                                <Icon name="lightbulb" size={16} className="text-yellow-400" /> Gợi Ý Chiến Lược Theo Phân Khúc
                            </h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {STRATEGY.map(s => {
                                    const isActive = activeStrategy === s.title;
                                    return (
                                        <button
                                            key={s.title}
                                            onClick={() => { setActiveStrategy(s.title); setCurrentPage(1); }}
                                            className={`rounded-xl border p-4 text-left cursor-pointer transition-all ${s.bg} ${isActive ? 'ring-2 ring-blue-400/60 shadow-lg scale-[1.02]' : 'opacity-70 hover:opacity-100'}`}
                                        >
                                            <div className="flex items-center gap-2 mb-2">
                                                <div className={`w-8 h-8 rounded-lg bg-white flex items-center justify-center ${s.color}`}>
                                                    <Icon name={s.icon} size={16} />
                                                </div>
                                                <span className={`font-bold text-sm ${s.color}`}>{s.title}</span>
                                            </div>
                                            <p className="text-xs text-gray-700 leading-relaxed">{s.desc}</p>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>


                        {/* PRODUCT TABLE */}
                        <div className="bg-white rounded-xl border border-blue-100 overflow-hidden shadow-lg">
                            <div className="p-4 border-b border-blue-100 bg-blue-50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                <h3 className="font-bold text-gray-900 flex items-center gap-2">
                                    <Icon name="list" size={18} className="text-gray-500" /> Danh sách {activeStrategy} ({getTableData().length} sản phẩm)
                                </h3>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm text-left">
                                    <thead className="text-xs text-gray-500 uppercase bg-white border-b border-blue-100">
                                        <tr>
                                            <th className="px-4 py-3">#</th>
                                            <th className="px-4 py-3">Sản phẩm</th>
                                            <th className="px-4 py-3">Danh mục</th>
                                            {[['price', '💰 Giá'], ['rating', '⭐ Rating'], ['quantity_sold', '🛒 Đã bán'], ['popularity_score', '🔥 Popularity']].map(([key, label]) => (
                                                <th key={key} className="px-4 py-3 text-right select-none">
                                                    {label}
                                                </th>
                                            ))}
                                            <th className="px-4 py-3 text-right select-none">
                                                🎯 Cơ hội
                                            </th>
                                            <th className="px-4 py-3 text-center">Đánh Giá</th>
                                            <th className="px-4 py-3 text-center">Link</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100/60">
                                        {(() => {
                                            const items = getTableData();
                                            if (items.length === 0) return (
                                                <tr><td colSpan={9} className="px-4 py-10 text-center text-gray-500">Không có sản phẩm nào.</td></tr>
                                            );
                                            const itemsPerPage = 10;
                                            const totalPages = Math.ceil(items.length / itemsPerPage);
                                            const safePage = Math.min(currentPage, Math.max(totalPages, 1));
                                            const startIndex = (safePage - 1) * itemsPerPage;
                                            const pageProducts = items.slice(startIndex, startIndex + itemsPerPage);
                                            return pageProducts.map((p, idx) => (
                                                <tr key={p.product_id} className="hover:bg-cyan-900/10 transition-colors">
                                                    <td className="px-4 py-3 text-gray-500 text-xs">{startIndex + idx + 1}</td>
                                                    <td className="px-4 py-3 text-gray-900 max-w-[200px]">
                                                        <span className="line-clamp-2 text-xs leading-4" title={p.name}>{p.name}</span>
                                                    </td>
                                                    <td className="px-4 py-3">
                                                        <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-700 border border-gray-300 whitespace-nowrap">{p.category}</span>
                                                    </td>
                                                    <td className="px-4 py-3 text-right text-gray-700 text-xs whitespace-nowrap">{p.price.toLocaleString('vi-VN')} đ</td>
                                                    <td className="px-4 py-3 text-right"><span className="font-bold text-red-400">{p.rating}</span></td>
                                                    <td className="px-4 py-3 text-right text-green-600 text-xs">{p.quantity_sold.toLocaleString('vi-VN')}</td>
                                                    <td className="px-4 py-3 text-right">
                                                        <div className="flex items-center justify-end gap-2">
                                                            <div className="w-12 bg-gray-200 rounded-full h-1 hidden sm:block">
                                                                <div className="h-1 rounded-full bg-blue-500" style={{ width: `${Math.min((p.popularity_score / (result.max_popularity || 10)) * 100, 100)}%` }}></div>
                                                            </div>
                                                            <span className="text-blue-700 text-xs">{p.popularity_score}</span>
                                                        </div>
                                                    </td>
                                                    <td className="px-4 py-3 text-right text-yellow-300 font-semibold text-xs">{Number(p.opportunity_score || 0).toFixed(1)}</td>
                                                    <td className="px-4 py-3 text-center">
                                                        <button onClick={() => handleOpenReviews(p)} className="inline-flex items-center px-2 py-1 rounded-lg text-xs bg-gray-200 hover:bg-blue-200 text-gray-900 transition-colors gap-1">
                                                            <Icon name="message-square" size={11} /> Đánh giá
                                                        </button>
                                                    </td>
                                                    <td className="px-4 py-3 text-center">
                                                        <a href={p.url || `https://tiki.vn/p/${p.product_id}`} target="_blank" rel="noopener noreferrer"
                                                            className="inline-flex items-center px-2 py-1 rounded-lg text-xs bg-blue-600 hover:bg-blue-600 text-white transition-colors gap-1">
                                                            <Icon name="external-link" size={11} /> Xem
                                                        </a>
                                                    </td>
                                                </tr>
                                            ));
                                        })()}
                                    </tbody>
                                </table>
                            </div>
                            {/* Pagination Footer */}
                            {(() => {
                                const items = getTableData();
                                if (items.length <= 10) return null;
                                const itemsPerPage = 10;
                                const totalPages = Math.ceil(items.length / itemsPerPage);
                                const safePage = Math.min(currentPage, Math.max(totalPages, 1));
                                const start = (safePage - 1) * itemsPerPage + 1;
                                const end = Math.min(safePage * itemsPerPage, items.length);
                                return (
                                    <div className="p-4 border-t border-cyan-700/50 bg-blue-50 flex justify-between items-center">
                                        <span className="text-sm text-gray-500">
                                            Hiển thị {start}–{end} / {items.length} sản phẩm
                                        </span>
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                                                disabled={safePage <= 1}
                                                className="px-3 py-1.5 bg-white border border-gray-200 hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-gray-900 text-sm font-medium transition-colors"
                                            >
                                                Trước
                                            </button>
                                            <span className="px-3 py-1.5 text-sm text-gray-700">{safePage} / {totalPages}</span>
                                            <button
                                                onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                                                disabled={safePage >= totalPages}
                                                className="px-3 py-1.5 bg-white border border-gray-200 hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-gray-900 text-sm font-medium transition-colors"
                                            >
                                                Sau
                                            </button>
                                        </div>
                                    </div>
                                );
                            })()}
                        </div>

                    </div>
                )}

                {/* EMPTY STATE */}
                {!loading && !result && (
                    <div className="flex flex-col items-center justify-center h-64 text-gray-500 opacity-60">
                        <Icon name="telescope" size={64} className="mb-4" />
                        <p className="text-lg">Nhấn nút để chạy phân tích KMeans</p>
                    </div>
                )}
            </div>

            {/* REVIEWS MODAL */}
            {
                reviewModal.open && (
                    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                        <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl border border-blue-100">
                            <div className="flex justify-between items-center p-5 border-b border-blue-100/50">
                                <h3 className="font-bold text-gray-900 text-lg flex items-center gap-2">
                                    <Icon name="message-square" className="text-blue-500" /> Đánh giá: <span className="text-gray-700 line-clamp-1 max-w-[300px]" title={reviewModal.product?.name}>{reviewModal.product?.name}</span>
                                </h3>
                                <button onClick={() => setReviewModal({ open: false, product: null, reviews: [], loading: false, error: null })} className="p-2 hover:bg-blue-100 rounded-full transition-colors text-gray-500 hover:text-gray-900">
                                    <Icon name="x" size={20} />
                                </button>
                            </div>
                            <div className="p-5 overflow-y-auto flex-1">
                                {reviewModal.loading ? (
                                    <div className="flex justify-center items-center py-10">
                                        <Icon name="loader-2" className="animate-spin text-blue-500" size={32} />
                                    </div>
                                ) : reviewModal.error ? (
                                    <div className="text-red-400 text-center py-5">Lỗi: {reviewModal.error}</div>
                                ) : reviewModal.reviews.length === 0 ? (
                                    <div className="text-gray-500 text-center py-10 italic">Không có đánh giá nào cho sản phẩm này.</div>
                                ) : (
                                    <div className="space-y-6">
                                        {/* SENTIMENT SUMMARY */}
                                        {(() => {
                                            const total = reviewModal.reviews.length;
                                            let pos = 0, neg = 0, neu = 0;
                                            reviewModal.reviews.forEach(r => {
                                                const s = (r.sentiment || '').toLowerCase();
                                                if (s === 'tích cực' || s === 'positive') pos++;
                                                else if (s === 'tiêu cực' || s === 'negative') neg++;
                                                else neu++;
                                            });
                                            const pPct = total > 0 ? ((pos / total) * 100).toFixed(1) : 0;
                                            const nPct = total > 0 ? ((neg / total) * 100).toFixed(1) : 0;
                                            const uPct = total > 0 ? ((neu / total) * 100).toFixed(1) : 0;

                                            return (
                                                <div className="bg-white rounded-xl p-5 border border-blue-100">
                                                    <div className="flex items-center gap-2 mb-1">
                                                        <Icon name="message-circle" size={18} className="text-blue-500" />
                                                        <h4 className="font-bold text-gray-900">Sentiment Đánh Giá</h4>
                                                    </div>
                                                    <p className="text-xs text-gray-500 mb-4">Từ {total} đánh giá (hiển thị tối đa 50)</p>

                                                    <div className="space-y-4">
                                                        <div>
                                                            <div className="flex justify-between text-sm mb-1.5">
                                                                <span className="flex items-center gap-1.5 text-gray-700">
                                                                    <div className="w-3 h-3 bg-green-500 rounded-sm"></div> Tích cực
                                                                </span>
                                                                <span className="text-gray-500">{pos} ({pPct}%)</span>
                                                            </div>
                                                            <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                                                                <div className="bg-green-500 h-1.5 rounded-full" style={{ width: `${pPct}%` }}></div>
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div className="flex justify-between text-sm mb-1.5">
                                                                <span className="flex items-center gap-1.5 text-gray-700">
                                                                    <div className="w-3 h-3 bg-yellow-500 rounded-sm"></div> Trung lập
                                                                </span>
                                                                <span className="text-gray-500">{neu} ({uPct}%)</span>
                                                            </div>
                                                            <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                                                                <div className="bg-yellow-500 h-1.5 rounded-full" style={{ width: `${uPct}%` }}></div>
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <div className="flex justify-between text-sm mb-1.5">
                                                                <span className="flex items-center gap-1.5 text-gray-700">
                                                                    <div className="w-3 h-3 bg-red-500 rounded-sm"></div> Tiêu cực
                                                                </span>
                                                                <span className="text-gray-500">{neg} ({nPct}%)</span>
                                                            </div>
                                                            <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                                                                <div className="bg-red-500 h-1.5 rounded-full" style={{ width: `${nPct}%` }}></div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })()}

                                        {/* REVIEW LIST */}
                                        <div className="space-y-4">
                                            {reviewModal.reviews.map((r, i) => {
                                                const s = (r.sentiment || '').toLowerCase();
                                                const isPos = s === 'tích cực' || s === 'positive';
                                                const isNeg = s === 'tiêu cực' || s === 'negative';

                                                return (
                                                    <div key={i} className="bg-white rounded-xl p-4 border border-blue-100">
                                                        <div className="flex justify-between items-start mb-2">
                                                            <div className="flex items-center gap-1 text-yellow-400">
                                                                {Array.from({ length: 5 }).map((_, j) => (
                                                                    <Icon key={j} name="star" size={12} className={j < r.rating ? "fill-yellow-400" : "text-gray-600"} />
                                                                ))}
                                                            </div>
                                                            <span className="text-xs text-gray-500">{r.created_at || ''}</span>
                                                        </div>
                                                        <p className="text-sm text-gray-700 leading-relaxed">
                                                            {r.content || <span className="italic text-gray-500">Đánh giá không có nội dung văn bản</span>}
                                                        </p>
                                                        {r.sentiment && (
                                                            <div className="mt-3">
                                                                <span className={`text-xs px-2 py-1 rounded-full ${isPos ? 'bg-green-900/30 text-green-600 border border-green-800' : isNeg ? 'bg-red-50 text-red-400 border border-red-800' : 'bg-yellow-900/30 text-yellow-400 border border-yellow-800'}`}>
                                                                    {isPos ? 'Tích cực' : isNeg ? 'Tiêu cực' : 'Trung lập'}
                                                                </span>
                                                            </div>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}
        </>
    );
}




