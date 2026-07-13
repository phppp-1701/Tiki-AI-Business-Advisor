// ============================================================
// 🔧 SHARED UTILITIES — Icon, calculateKPI, API, renderResult
// ============================================================

// --- ERROR BOUNDARY ---
class ErrorBoundary extends React.Component {
    constructor(props) { super(props); this.state = { hasError: false, error: null }; }
    static getDerivedStateFromError(error) { return { hasError: true, error }; }
    render() {
        if (this.state.hasError) {
            return <div className="p-5 bg-red-50 text-red-600 border border-red-500 rounded-xl max-w-4xl mx-auto mt-10"><h2>React Fatal Error:</h2><pre className="text-xs overflow-auto">{this.state.error.stack || this.state.error.message}</pre></div>;
        }
        return this.props.children;
    }
}

// --- ICONS COMPONENT ---
const Icon = ({ name, size = 20, className = "" }) => (
    <span className="inline-flex items-center justify-center" dangerouslySetInnerHTML={{ __html: `<i data-lucide="${name}" width="${size}" height="${size}" class="${className}"></i>` }} />
);

// --- FLEXIBLE VNĐ FORMATTER ---
const formatVND = (value) => {
    if (value === null || value === undefined || !Number.isFinite(value) || value === 0) return '0 VNĐ';
    const abs = Math.abs(value);
    const sign = value < 0 ? '-' : '';
    if (abs >= 1e9) {
        const v = abs / 1e9;
        return `${sign}${v % 1 === 0 ? v.toFixed(0) : v.toFixed(2)} tỷ VNĐ`;
    }
    if (abs >= 1e6) {
        const v = abs / 1e6;
        return `${sign}${v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)} triệu VNĐ`;
    }
    return `${sign}${abs.toLocaleString('vi-VN')} VNĐ`;
};

// --- INFO TOOLTIP COMPONENT ---
const InfoTooltip = ({ content }) => {
    const [open, setOpen] = React.useState(false);
    const ref = React.useRef(null);

    React.useEffect(() => {
        if (!open) return;
        const handler = (e) => {
            if (ref.current && !ref.current.contains(e.target)) setOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [open]);

    return (
        <span ref={ref} className="relative inline-flex items-center ml-1.5">
            <button
                onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
                className="w-5 h-5 rounded-full bg-blue-100 hover:bg-blue-500 hover:text-white text-blue-700 text-[11px] font-bold flex items-center justify-center transition-colors cursor-pointer"
                title="Giải thích cách tính"
            >?</button>
            {open && (
                <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-80 bg-white border border-blue-300/40 rounded-xl p-4 shadow-2xl shadow-blue-200/40 text-xs leading-relaxed text-gray-800 animate-fade-in"
                    style={{ minWidth: '300px' }}>
                    <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-white border-b border-r border-blue-300/40 rotate-45"></div>
                    {content}
                </div>
            )}
        </span>
    );
};

// --- PRICE SEGMENT TOOLTIP CONTENT ---
const PriceSegmentTooltip = () => (
    <InfoTooltip content={
        <div>
            <div className="font-bold text-blue-600 mb-2 text-sm">📐 Cách tính Phân Khúc Giá</div>
            <div className="mb-2 text-gray-500">Dựa trên <span className="text-gray-900 font-semibold">Giá Trung Bình (Giá TB)</span> của tất cả sản phẩm trong kết quả tìm kiếm:</div>
            <div className="space-y-2">
                <div className="flex items-start gap-2">
                    <span className="text-blue-400 font-bold text-sm mt-0.5">💙</span>
                    <div><span className="text-blue-300 font-semibold">Bình dân</span><br />
                        <span className="text-gray-700">Giá sản phẩm <span className="text-gray-900 font-mono font-bold">&lt; 70%</span> Giá TB</span>
                    </div>
                </div>
                <div className="flex items-start gap-2">
                    <span className="text-green-600 font-bold text-sm mt-0.5">💚</span>
                    <div><span className="text-green-300 font-semibold">Trung cấp</span><br />
                        <span className="text-gray-700">Giá sản phẩm từ <span className="text-gray-900 font-mono font-bold">70%</span> đến <span className="text-gray-900 font-mono font-bold">130%</span> Giá TB</span>
                    </div>
                </div>
                <div className="flex items-start gap-2">
                    <span className="text-purple-400 font-bold text-sm mt-0.5">💎</span>
                    <div><span className="text-purple-300 font-semibold">Cao cấp</span><br />
                        <span className="text-gray-700">Giá sản phẩm <span className="text-gray-900 font-mono font-bold">&gt; 130%</span> Giá TB</span>
                    </div>
                </div>
            </div>
            <div className="mt-3 pt-2 border-t border-blue-100 text-gray-500">
                <span className="text-yellow-400">💡</span> Ví dụ: Giá TB = 500.000đ → Bình dân &lt; 350.000đ, Trung cấp 350.000đ–650.000đ, Cao cấp &gt; 650.000đ
            </div>
        </div>
    } />
);

// --- CALCULATE KPI FROM PRODUCTS DATA ---
const calculateKPI = (products) => {
    if (!products || products.length === 0) {
        return { revenue: "$0", sold: "0", avg: "$0", growth: "N/A" };
    }

    const parseLocaleInteger = (value) => {
        if (value === null || value === undefined) return 0;
        const digits = String(value).replace(/\D/g, '');
        return digits ? parseInt(digits, 10) : 0;
    };

    const parseNumeric = (value) => {
        if (value === null || value === undefined || value === '') return null;
        if (typeof value === 'number') return Number.isFinite(value) ? value : null;
        const normalized = String(value).replace(/,/g, '.').replace(/[^\d.-]/g, '');
        if (!normalized) return null;
        const parsed = Number(normalized);
        return Number.isFinite(parsed) ? parsed : null;
    };

    const totalRevenue = products.reduce((sum, p) => sum + parseLocaleInteger(p.rev), 0);
    const totalSold = products.reduce((sum, p) => sum + parseLocaleInteger(p.sold), 0);
    const totalPrice = products.reduce((sum, p) => sum + parseLocaleInteger(p.price), 0);
    const avgPrice = products.length > 0 ? totalPrice / products.length : 0;

    const growthValues = products
        .map((p) => parseNumeric(p.growth_percent ?? p.monthly_growth ?? p.growth_rate ?? p.growth))
        .filter((v) => v !== null);

    let growth = 'N/A';
    if (growthValues.length > 0) {
        const avgGrowth = growthValues.reduce((sum, v) => sum + v, 0) / growthValues.length;
        const sign = avgGrowth > 0 ? '+' : '';
        growth = `${sign}${avgGrowth.toFixed(1)}%`;
    } else if (products.length > 0 && totalSold > 0) {
        const soldValues = products
            .map((p) => parseLocaleInteger(p.sold))
            .filter((v) => v > 0)
            .sort((a, b) => a - b);
        if (soldValues.length > 0) {
            const medianSold = soldValues.length % 2 === 0
                ? (soldValues[soldValues.length / 2 - 1] + soldValues[soldValues.length / 2]) / 2
                : soldValues[Math.floor(soldValues.length / 2)];
            const avgSoldPerProduct = totalSold / products.length;
            const growthPercent = ((avgSoldPerProduct / medianSold) - 1) * 100;
            const capped = Math.max(Math.min(growthPercent, 500), -100);
            const sign = capped > 0 ? '+' : '';
            growth = `${sign}${capped.toFixed(1)}%`;
        }
    }

    return {
        revenue: formatVND(totalRevenue),
        sold: totalSold.toLocaleString(),
        avg: formatVND(avgPrice),
        growth
    };
};

// ============================================================
// 🛑 API CONFIGURATION & FUNCTIONS
// ============================================================

const resolveApiBaseUrl = () => {
    const configured = (window.__API_BASE_URL__ || '').trim();
    if (configured) return configured.replace(/\/+$/, '');
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') return 'http://localhost:8000';
    return '';
};

const API_BASE_URL = resolveApiBaseUrl();

const executeAnalysis = async (type, payload) => {
    try {
        if (!API_BASE_URL) {
            throw new Error('Chưa cấu hình API_BASE_URL cho môi trường deploy (GitHub Pages).');
        }
        if (window.location.protocol === 'https:' && API_BASE_URL.startsWith('http://')) {
            throw new Error('Trang đang chạy HTTPS nhưng API là HTTP (mixed content sẽ bị chặn).');
        }

        let response;
        if (type === 'single') {
            response = await fetch(`${API_BASE_URL}/api/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    keyword: payload.keyword,
                    market: 'US',
                    limit: 9999,
                    display_limit: 20,
                    context_id: payload.context_id || null,
                })
            });
        } else {
            const formData = new FormData();
            formData.append('file', payload.file);
            response = await fetch(`${API_BASE_URL}/api/analyze-batch`, {
                method: 'POST',
                body: formData
            });
        }

        if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        const result = await response.json();
        if (!result.success) throw new Error(result.message || 'Unknown error');

        return {
            products: result.data.products.map((p, idx) => {
                // Preserve product_id exactly as returned by the API (may be numeric string)
                const apiPid = p.product_id || p.id || p.itemId || '';
                const rawPid = (apiPid !== undefined && apiPid !== null && apiPid !== '')
                    ? String(apiPid)
                    : '';
                return {
                    id: idx + 1,
                    product_id: rawPid,
                    name: p.title || p.name || p.product_name || 'N/A',
                    cat: p.categoryName || p.category || p.category_name || 'N/A',
                    price: `${(p.price || 0).toLocaleString()} VNĐ`,
                    sold: (p.boughtInLastMonth || p.quantity_sold || p.review_count || 0).toLocaleString(),
                    rev: (p.estimated_revenue || 0).toLocaleString() + ' VNĐ',
                    rating: Number(p.rating || p.avg_rating || 0).toFixed(1),
                    growth_percent: p.growth_percent ?? p.monthly_growth ?? p.growth_rate ?? p.growth ?? null,
                    url: p.product_url || p.url_path || (rawPid ? `https://tiki.vn/p/${rawPid}` : '')
                };
            }),
            insight: result.data.ai_insight || 'Không có insight',
            context: result.data.context || null,
            analytics: result.data.analytics || null,
        };
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
};

// ============================================================
// 📝 RENDER HELPERS
// ============================================================

const renderFormattedInsight = (insight) => {
    if (!insight) return <div className="text-sm text-gray-700">Không có insight để hiển thị.</div>;

    const blocks = insight.split(/\n{2,}/g).filter(Boolean);
    return blocks.map((block, index) => {
        const lines = block.split('\n').filter(Boolean);
        const firstLine = lines[0].trim();
        const isHeading = /^(?:\*\*|##|###|🎯|📈|💡|📊|💰|✅|🔥)/.test(firstLine);
        return (
            <div key={index} className={`rounded-xl p-4 mb-3 ${isHeading ? 'bg-blue-50 border border-blue-200 shadow-sm' : 'bg-white border border-gray-100'}`}>
                {lines.map((line, lineIndex) => {
                    const trimmed = line.trim();
                    if (/^\*\*([^\n]+)\*\*$/.test(trimmed)) {
                        return <div key={lineIndex} className="text-sm font-semibold uppercase text-amber-700 mb-2">{trimmed.replace(/^\*\*(.+)\*\*$/, '$1')}</div>;
                    }
                    if (/^##+\s+(.+)$/.test(trimmed)) {
                        return <div key={lineIndex} className="text-base font-bold uppercase text-blue-700 mb-2">{trimmed.replace(/^##+\s+(.+)$/, '$1')}</div>;
                    }
                    if (/^-\s+(.+)$/.test(trimmed)) {
                        return (
                            <div key={lineIndex} className="flex gap-3 text-sm text-gray-700 leading-6">
                                <span className="text-blue-500">•</span>
                                <span>{trimmed.replace(/^-\s+(.+)$/, '$1')}</span>
                            </div>
                        );
                    }
                    return <div key={lineIndex} className="text-sm text-gray-700 leading-6">{trimmed}</div>;
                })}
            </div>
        );
    });
};

const formatKpiFromAnalytics = (analytics) => {
    if (!analytics) return null;
    const totalRevenue = Number(analytics.total_revenue || 0);
    const totalSold = Number(analytics.total_sold || 0);
    const avgPrice = Number(analytics.avg_price || 0);
    return {
        revenue: formatVND(totalRevenue),
        sold: totalSold.toLocaleString(),
        avg: formatVND(avgPrice),
        growth: "N/A",
    };
};

// Shared result dashboard (used by SinglePage & BatchPage)
const renderResult = (result, insight, analytics = null, onOpenReviews = null) => {
    const kpi = formatKpiFromAnalytics(analytics) || calculateKPI(result);
    return (
        <div className="max-w-6xl mx-auto space-y-8 animate-fade-in pb-10 mt-8">
            {/* KPI CARDS */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                    { label: "Tổng Doanh Thu", val: kpi.revenue, icon: "dollar-sign", color: "text-green-600" },
                    { label: "Sản Phẩm Bán Ra", val: kpi.sold, icon: "shopping-bag", color: "text-blue-400" },
                    { label: "Giá TB Đơn Hàng", val: kpi.avg, icon: "tag", color: "text-purple-400" },
                    { label: "Tăng Trưởng", val: kpi.growth, icon: "trending-up", color: "text-blue-500" },
                ].map((item, idx) => (
                    <div key={idx} className="bg-white p-5 rounded-xl border border-blue-100 shadow-sm shadow-sm">
                        <div className="flex justify-between items-start mb-2">
                            <span className="text-gray-500 text-sm">{item.label}</span>
                            <Icon name={item.icon} size={18} className={item.color} />
                        </div>
                        <div className="text-2xl font-bold text-gray-900">{item.val}</div>
                    </div>
                ))}
            </div>

            {/* AI INSIGHT BOX */}
            <div className="ai-insight-gradient rounded-xl p-6 relative overflow-hidden border border-blue-200 shadow-sm">
                <div className="absolute top-0 right-0 w-64 h-64 bg-blue-200/30 rounded-full blur-3xl -mr-20 -mt-20"></div>
                <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="p-2 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg text-white shadow-md">
                            <Icon name="bot" size={24} />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-gray-900">AI Smart Insights</h3>
                            <p className="text-xs text-blue-500">Phân tích tự động bởi Gemini AI</p>
                        </div>
                    </div>
                    <div className="bg-white/80 backdrop-blur-sm rounded-xl p-4 border border-blue-100 text-sm leading-relaxed">
                        {renderFormattedInsight(insight)}
                    </div>
                </div>
            </div>

            {/* PRODUCT TABLE */}
            <div className="bg-white rounded-xl border border-blue-100 overflow-hidden shadow-lg">
                <div className="p-4 border-b border-blue-100 flex justify-between items-center bg-blue-50">
                    <h3 className="font-bold text-gray-900 flex items-center gap-2">
                        <Icon name="trophy" size={18} className="text-yellow-500" /> Top Sản Phẩm
                    </h3>
                    <span className="text-xs text-gray-500">Dữ liệu từ Backend API</span>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="text-xs text-gray-500 uppercase bg-white border-b border-blue-100">
                            <tr>
                                <th className="px-6 py-3 w-12 text-center">Thứ tự</th>
                                <th className="px-6 py-3">Sản phẩm</th>
                                <th className="px-6 py-3">Danh mục</th>
                                <th className="px-6 py-3 text-right">Giá bán</th>
                                <th className="px-6 py-3 text-right">Đã bán</th>
                                <th className="px-6 py-3 text-right">Doanh Thu</th>
                                <th className="px-6 py-3 text-right">⭐ Đánh giá</th>
                                {onOpenReviews && <th className="px-6 py-3 text-center">Đánh Giá</th>}
                                <th className="px-6 py-3 text-center">Link</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {result.map((item, idx) => {
                                const isTop3 = idx < 3;
                                const rank = idx + 1;
                                const rankBadge = isTop3 ? `TOP ${rank}` : rank;
                                const productLink = item.url || (item.product_id ? `https://tiki.vn/p/${item.product_id}` : '#');
                                return (
                                    <tr key={item.id} className={`${isTop3 ? 'bg-gradient-to-r from-blue-50 to-indigo-50 border-l-4 border-blue-400' : 'hover:bg-blue-50'} transition-colors`}>
                                        <td className="px-6 py-4 text-center text-gray-500 font-mono">
                                            {isTop3
                                                ? <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-bold bg-blue-600 text-white">{rankBadge}</span>
                                                : <span className="text-gray-500">{rank}</span>}
                                        </td>
                                        <td className="px-6 py-4 font-medium text-gray-900 truncate max-w-[200px]" title={item.name}>
                                            {isTop3 && <span className="text-blue-500 mr-1">🏆</span>}{item.name}
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${isTop3 ? 'bg-blue-100 text-blue-800 border border-blue-300' : 'bg-gray-100 text-gray-700 border border-gray-200'}`}>
                                                {item.cat}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-right text-gray-600">{item.price}</td>
                                        <td className="px-6 py-4 text-right text-green-600 font-medium">{item.sold}</td>
                                        <td className="px-6 py-4 text-right text-blue-600 font-bold">{item.rev}</td>
                                        <td className="px-6 py-4 text-right">
                                            {Number(item.rating) > 0 ? (
                                                <span className="inline-flex items-center gap-1">
                                                    <span className="font-bold text-amber-500">{item.rating}</span>
                                                    <span className="text-yellow-400 text-xs">★★★★★</span>
                                                </span>
                                            ) : <span className="text-gray-400 text-xs">N/A</span>}
                                        </td>
                                        {onOpenReviews && (
                                            <td className="px-6 py-4 text-center">
                                                <button onClick={() => onOpenReviews(item)} className="inline-flex items-center px-2 py-1 rounded-lg text-xs bg-gray-200 hover:bg-blue-200 text-gray-900 transition-colors gap-1">
                                                    <Icon name="message-square" size={11} /> Đánh giá
                                                </button>
                                            </td>
                                        )}
                                        <td className="px-6 py-4 text-center">
                                            <a href={productLink} target="_blank" rel="noopener noreferrer"
                                                className="inline-flex items-center px-3 py-1 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors">
                                                <Icon name="external-link" size={12} className="mr-1" />Xem
                                            </a>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

// Shared PDF export helper (used by single & batch pages)
const buildPdfHtml = (resultData, insightData, titleKeyword, isSingle) => `
    <div style="font-family: 'Arial', sans-serif; padding: 20px; background: white; color: black;">
        <h1 style="color: #1e293b; margin-bottom: 5px;">Báo Cáo Phân Tích Thị Trường E-Commerce</h1>
        <p style="color: #666; font-size: 14px; margin: 5px 0;">
            Nguồn: ${isSingle ? `Từ khóa: ${titleKeyword}` : `File: ${titleKeyword}`}
        </p>
        <p style="color: #666; font-size: 14px; margin: 5px 0;">
            Ngày tạo: ${new Date().toLocaleDateString('vi-VN')}
        </p>
        <h2 style="color: #1e293b; margin-top: 20px; margin-bottom: 10px; border-bottom: 2px solid #e11d48; padding-bottom: 10px;">AI Insights</h2>
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; white-space: pre-wrap; font-family: monospace; font-size: 12px; line-height: 1.6;">
            ${(insightData || "Không có dữ liệu.").replace(/</g, '&lt;').replace(/>/g, '&gt;')}
        </div>
        <h2 style="color: #1e293b; margin-top: 20px; margin-bottom: 10px; border-bottom: 2px solid #e11d48; padding-bottom: 10px;">Top Sản Phẩm</h2>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
            <thead>
                <tr style="background-color: #e11d48; color: white;">
                    <th style="border: 1px solid #ddd; padding: 10px; text-align: center;">STT</th>
                    <th style="border: 1px solid #ddd; padding: 10px; text-align: left;">Sản phẩm</th>
                    <th style="border: 1px solid #ddd; padding: 10px; text-align: left;">Danh mục</th>
                    <th style="border: 1px solid #ddd; padding: 10px; text-align: right;">Giá bán</th>
                    <th style="border: 1px solid #ddd; padding: 10px; text-align: right;">Đã bán</th>
                    <th style="border: 1px solid #ddd; padding: 10px; text-align: right;">Doanh Thu</th>
                </tr>
            </thead>
            <tbody>
                ${resultData.map((item, idx) => `
                    <tr style="background-color: ${idx % 2 === 0 ? '#f9f9f9' : 'white'};">
                        <td style="border: 1px solid #ddd; padding: 10px; text-align: center;">${idx + 1}</td>
                        <td style="border: 1px solid #ddd; padding: 10px;">${item.name}</td>
                        <td style="border: 1px solid #ddd; padding: 10px;">${item.cat}</td>
                        <td style="border: 1px solid #ddd; padding: 10px; text-align: right;">${item.price}</td>
                        <td style="border: 1px solid #ddd; padding: 10px; text-align: right;">${item.sold}</td>
                        <td style="border: 1px solid #ddd; padding: 10px; text-align: right; color: #e11d48; font-weight: bold;">${item.rev}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    </div>
`;




