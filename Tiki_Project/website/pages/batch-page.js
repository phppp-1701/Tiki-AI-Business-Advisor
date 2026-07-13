// ============================================================
// 📂 BATCH PAGE — Phân tích loạt (CSV)
// ============================================================

const parseMarkdown = (text) => {
    if (!text) return '';
    let html = text;
    
    // Escape standard tags to prevent XSS but preserve layout
    html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // Bold: **text** -> <strong>text</strong>
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italic: *text* -> <em>text</em>
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Inline code: `code` -> <code>code</code>
    html = html.replace(/`(.*?)`/g, '<code class="bg-gray-100 text-red-600 px-1 rounded">$1</code>');
    
    const lines = html.split('\n');
    let inTable = false;
    let tableHtml = '';
    let finalLines = [];
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line.startsWith('|') && line.endsWith('|')) {
            if (!inTable) {
                inTable = true;
                tableHtml = '<div class="overflow-x-auto my-3"><table class="min-w-full divide-y divide-gray-200 border border-gray-200 rounded-lg text-[10px] bg-white">';
            }
            
            const cells = line.split('|').slice(1, -1).map(c => c.trim());
            // Skip the separator row |---|---|
            if (cells.every(c => c.match(/^:?-+:?$/))) {
                continue;
            }
            
            const isHeader = !tableHtml.includes('<tbody');
            if (isHeader && !tableHtml.includes('<thead')) {
                tableHtml += '<thead><tr class="bg-blue-50/70">';
                cells.forEach(c => {
                    tableHtml += `<th class="px-2 py-1.5 text-left font-bold text-blue-900 border-b border-gray-200">${c}</th>`;
                });
                tableHtml += '</tr></thead><tbody>';
            } else {
                tableHtml += '<tr class="hover:bg-gray-50 border-b border-gray-100">';
                cells.forEach(c => {
                    tableHtml += `<td class="px-2 py-1.5 text-gray-700">${c}</td>`;
                });
                tableHtml += '</tr>';
            }
        } else {
            if (inTable) {
                inTable = false;
                tableHtml += '</tbody></table></div>';
                finalLines.push(tableHtml);
                tableHtml = '';
            }
            finalLines.push(lines[i]);
        }
    }
    if (inTable) {
        tableHtml += '</tbody></table></div>';
        finalLines.push(tableHtml);
    }
    
    html = finalLines.map(line => {
        const trimmed = line.trim();
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
            return `<li class="ml-4 list-disc my-0.5 text-gray-700">${trimmed.substring(2)}</li>`;
        }
        if (trimmed.startsWith('1. ') || trimmed.startsWith('2. ') || trimmed.startsWith('3. ')) {
            return `<li class="ml-4 list-decimal my-0.5 text-gray-700">${trimmed.substring(3)}</li>`;
        }
        if (trimmed.startsWith('### ')) {
            return `<h4 class="font-bold text-gray-900 text-xs mt-3 mb-1">${trimmed.substring(4)}</h4>`;
        }
        if (trimmed.startsWith('## ')) {
            return `<h3 class="font-bold text-blue-800 text-sm mt-3.5 mb-1.5">${trimmed.substring(3)}</h3>`;
        }
        if (trimmed.startsWith('# ')) {
            return `<h2 class="font-bold text-blue-900 text-base mt-4 mb-2 border-b border-blue-100 pb-0.5">${trimmed.substring(2)}</h2>`;
        }
        return line;
    }).join('\n');
    
    return html.replace(/\n/g, '<br/>');
};

function BatchPage() {
    const { useState, useEffect } = React;

    const quickCommands = [
        { id: 'overview', label: 'Tóm tắt nhanh', prompt: 'Tóm tắt tổng quan cho từ khóa {keyword}' },
        { id: 'price', label: 'Giá trung bình', prompt: 'Giá trung bình hiện tại là bao nhiêu?' },
        { id: 'revenue', label: 'Tổng doanh thu', prompt: 'Tổng doanh thu ước tính của kết quả này là gì?' },
        { id: 'sold', label: 'Số lượng bán', prompt: 'Tổng số lượng bán của nhóm sản phẩm này là bao nhiêu?' },
        { id: 'top3', label: 'Top 3 sản phẩm', prompt: 'Top 3 sản phẩm đang nổi bật là gì?' },
        { id: 'top1', label: 'Phân tích top 1', prompt: 'Phân tích kỹ sản phẩm {top_product} cho tôi' },
        { id: 'segment', label: 'Phân khúc giá', prompt: 'Nhóm sản phẩm này đang tập trung vào phân khúc giá nào?' },
        { id: 'action', label: 'Gợi ý hành động', prompt: 'Đề xuất 3 hành động tối ưu để tăng doanh thu cho từ khóa {keyword}' },
    ];

    const [selectedFile, setSelectedFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [keywords, setKeywords] = useState([]);
    const [activeKeyword, setActiveKeyword] = useState('');
    const [analysisLoading, setAnalysisLoading] = useState(false);
    const [analysisResult, setAnalysisResult] = useState(null);
    const [analysisInsight, setAnalysisInsight] = useState('');
    const [analysisAnalytics, setAnalysisAnalytics] = useState(null);
    const [analysisCache, setAnalysisCache] = useState({});
    const [error, setError] = useState('');

    const chatContainerRef = React.useRef(null);

    // Persistent Session ID & List
    const [sessions, setSessions] = useState(() => {
        const key = 'tiki_chat_sessions_list';
        let list = localStorage.getItem(key);
        if (!list) {
            list = JSON.stringify([{ id: 'sess_default', name: 'Tư vấn chung' }]);
            localStorage.setItem(key, list);
        }
        return JSON.parse(list);
    });

    const [activeSessionId, setActiveSessionId] = useState(() => {
        const key = 'tiki_chat_active_session_id';
        let activeId = localStorage.getItem(key);
        if (!activeId) {
            activeId = 'sess_default';
            localStorage.setItem(key, activeId);
        }
        return activeId;
    });

    const [isSessionListOpen, setIsSessionListOpen] = useState(false);
    const [chatMessages, setChatMessages] = useState([]);

    useEffect(() => {
        const key = `tiki_chat_messages_${activeSessionId}`;
        let msgs = localStorage.getItem(key);
        if (!msgs) {
            const defaultWelcome = [
                {
                    role: 'assistant',
                    text: '👋 Xin chào! Tôi là Trợ lý AI Tư vấn Kinh doanh trên sàn Tiki.\n\nTôi có thể đề xuất các mô hình kinh doanh phù hợp với vốn, phân tích doanh thu/lợi nhuận thực tế, đánh giá rủi ro và lập kế hoạch triển khai từng bước.\n\n👉 Để bắt đầu, bạn dự kiến đầu tư số vốn khoảng bao nhiêu không?'
                }
            ];
            localStorage.setItem(key, JSON.stringify(defaultWelcome));
            setChatMessages(defaultWelcome);
        } else {
            setChatMessages(JSON.parse(msgs));
        }
    }, [activeSessionId]);


    const saveMessages = (msgs) => {
        setChatMessages(msgs);
        localStorage.setItem(`tiki_chat_messages_${activeSessionId}`, JSON.stringify(msgs));
    };

    const handleCreateSession = (name = null) => {
        const newId = 'sess_' + Math.random().toString(36).substring(2, 15);
        const sessName = name || `Hội thoại mới ${sessions.length + 1}`;
        const newSessions = [...sessions, { id: newId, name: sessName }];
        setSessions(newSessions);
        localStorage.setItem('tiki_chat_sessions_list', JSON.stringify(newSessions));
        
        setActiveSessionId(newId);
        localStorage.setItem('tiki_chat_active_session_id', newId);
        
        const welcomeMsg = [
            {
                role: 'assistant',
                text: `👋 Chào mừng bạn đến với cuộc hội thoại mới về: **${sessName}**.\n\nBạn dự kiến đầu tư số vốn khoảng bao nhiêu cho mô hình này?`
            }
        ];
        localStorage.setItem(`tiki_chat_messages_${newId}`, JSON.stringify(welcomeMsg));
        setChatMessages(welcomeMsg);
        setIsSessionListOpen(false);
    };

    const handleDeleteSession = async (idToDelete, e) => {
        if (e) e.stopPropagation();
        
        if (sessions.length <= 1) {
            alert("Không thể xóa cuộc hội thoại duy nhất còn lại!");
            return;
        }
        
        const confirmDelete = confirm(`Bạn có chắc chắn muốn xóa cuộc hội thoại này không?`);
        if (!confirmDelete) return;

        const newSessions = sessions.filter(s => s.id !== idToDelete);
        setSessions(newSessions);
        localStorage.setItem('tiki_chat_sessions_list', JSON.stringify(newSessions));
        
        localStorage.removeItem(`tiki_chat_messages_${idToDelete}`);
        
        try {
            await fetch(`${API_BASE_URL}/api/chat/${idToDelete}`, { method: 'DELETE' });
        } catch (err) {
            console.error("Backend session delete error:", err);
        }
        
        if (activeSessionId === idToDelete) {
            const nextId = newSessions[0].id;
            setActiveSessionId(nextId);
            localStorage.setItem('tiki_chat_active_session_id', nextId);
        }
    };

    // Profile & Context state
    const [userProfile, setUserProfile] = useState({ capital: null, location: 'TP.HCM', interest: null, experience: null });
    const [activeBusiness, setActiveBusiness] = useState(null);
    const [chatInput, setChatInput] = useState('');
    const [chatLoading, setChatLoading] = useState(false);
    const [isChatOpen, setIsChatOpen] = useState(false);
    const [batchPriceFilter, setBatchPriceFilter] = useState('all');
    const [batchPage, setBatchPage] = useState(1);
    const [reviewModal, setReviewModal] = useState({ open: false, product: null, reviews: [], loading: false, error: null });

    // Scroll to bottom when new messages arrive or chat opens
    useEffect(() => {
        if (chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
    }, [chatMessages, isChatOpen]);

    useEffect(() => {
        lucide.createIcons();
    }, [keywords, activeKeyword, analysisLoading, analysisResult, chatMessages, isChatOpen, reviewModal.open]);

    const normalizeBotText = (value) =>
        String(value || '')
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .trim();

    const renderChatMessageText = (text) => {
        const source = String(text || '');
        const renderLineWithBold = (line, lineIdx) => {
            const parts = [];
            const pattern = /\*\*(.*?)\*\*/g;
            let cursor = 0;
            let match;
            let partIdx = 0;

            while ((match = pattern.exec(line)) !== null) {
                if (match.index > cursor) {
                    parts.push(<React.Fragment key={`t-${lineIdx}-${partIdx}`}>{line.slice(cursor, match.index)}</React.Fragment>);
                    partIdx += 1;
                }
                parts.push(<strong key={`b-${lineIdx}-${partIdx}`} className="font-semibold text-gray-900">{match[1]}</strong>);
                partIdx += 1;
                cursor = match.index + match[0].length;
            }

            if (cursor < line.length) {
                parts.push(<React.Fragment key={`t-${lineIdx}-${partIdx}`}>{line.slice(cursor)}</React.Fragment>);
            }

            return <div key={`line-${lineIdx}`}>{parts.length ? parts : line}</div>;
        };

        return source.split('\n').map((line, idx) => renderLineWithBold(line, idx));
    };

    const parseFlexibleNumber = (value) => {
        if (value === null || value === undefined || value === '') return 0;
        if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
        const normalized = String(value).replace(/,/g, '.').replace(/[^\d.-]/g, '');
        const parsed = Number(normalized);
        return Number.isFinite(parsed) ? parsed : 0;
    };

    const extractBudgetFromText = (text) => {
        const normalized = normalizeBotText(text);
        const match = normalized.match(/(\d+(?:[\.,]\d+)?)\s*(trieu|tr|k|nghin|ngan|m|million)/);
        if (!match) return 0;
        const amount = parseFloat(match[1].replace(',', '.'));
        const unit = match[2];
        if (['trieu', 'tr', 'm', 'million'].includes(unit)) return amount * 1000000;
        if (['k', 'nghin', 'ngan'].includes(unit)) return amount * 1000;
        return amount;
    };

    const formatCompactMoney = (value) => {
        if (!value || value <= 0) return '0 VNĐ';
        if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M VNĐ`;
        if (value >= 1000) return `${(value / 1000).toFixed(0)}K VNĐ`;
        return `${value.toLocaleString('vi-VN')} VNĐ`;
    };

    const fetchMarketReport = async (keyword, contextId = null) => {
        if (!API_BASE_URL) {
            throw new Error('Chưa cấu hình API_BASE_URL cho môi trường deploy (GitHub Pages).');
        }
        if (window.location.protocol === 'https:' && API_BASE_URL.startsWith('http://')) {
            throw new Error('Trang đang chạy HTTPS nhưng API là HTTP (mixed content sẽ bị chặn).');
        }

        const res = await fetch(`${API_BASE_URL}/api/market-report`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword, context_id: contextId })
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        const json = await res.json();
        if (!json.success) throw new Error(json.detail || 'Unknown error');
        return json.data;
    };

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setSelectedFile(e.target.files[0]);
        }
    };

    const parseCsvLine = (line, delimiter = ',') => {
        const cells = [];
        let current = '';
        let inQuotes = false;

        for (let i = 0; i < line.length; i += 1) {
            const ch = line[i];
            if (ch === '"') {
                if (inQuotes && line[i + 1] === '"') {
                    current += '"';
                    i += 1;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (ch === delimiter && !inQuotes) {
                cells.push(current.trim());
                current = '';
            } else {
                current += ch;
            }
        }

        cells.push(current.trim());
        return cells;
    };

    const decodeCsvText = async (file) => {
        const buffer = await file.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        const decoders = ['utf-8', 'utf-8-sig', 'windows-1258', 'windows-1252', 'iso-8859-1'];

        const looksReadable = (text) => {
            if (!text || !text.trim()) return false;
            if (text.includes('\uFFFD')) return false;
            return true;
        };

        for (const encoding of decoders) {
            try {
                const text = new TextDecoder(encoding, { fatal: false }).decode(bytes);
                if (looksReadable(text)) return text;
            } catch (_) {
                // Try next decoder
            }
        }

        return new TextDecoder('utf-8', { fatal: false }).decode(bytes);
    };

    const parseKeywordsFromCsv = async (file) => {
        const text = await decodeCsvText(file);
        const lines = text
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter(Boolean);

        if (lines.length === 0) return [];

        const delimiter = lines[0].includes(';') ? ';' : ',';
        const headers = parseCsvLine(lines[0], delimiter).map((h) => h.replace(/^"|"$/g, '').trim().toLowerCase());
        const keywordIdx = headers.findIndex((h) => ['keyword', 'tu_khoa', 'tu khoa', 'từ khóa', 'query'].includes(h));
        const fromDataRow = keywordIdx >= 0;
        const startIndex = fromDataRow ? 1 : 0;

        const values = [];
        for (let i = startIndex; i < lines.length; i += 1) {
            const cols = parseCsvLine(lines[i], delimiter).map((c) => c.replace(/^"|"$/g, '').trim());
            const value = keywordIdx >= 0 ? (cols[keywordIdx] || '') : (cols[0] || '');
            if (value) values.push(value);
        }

        const unique = [];
        const seen = new Set();
        for (const item of values) {
            const key = item.toLowerCase();
            if (!seen.has(key)) {
                seen.add(key);
                unique.push(item);
            }
        }

        return unique.slice(0, 100);
    };

    const runSingleAnalysis = async (keyword, force = false, contextId = null) => {
        const cleaned = (keyword || '').trim();
        if (!cleaned) return;

        setActiveKeyword(cleaned);
        setError('');

        const cacheKey = `${cleaned}::${contextId || 'all'}`;

        if (!force && analysisCache[cacheKey]) {
            const cached = analysisCache[cacheKey];
            setAnalysisResult(cached.report);
            setAnalysisInsight(cached.insight);
            setAnalysisAnalytics(cached.analytics);
            return;
        }

        setAnalysisLoading(true);
        setAnalysisResult(null);
        setAnalysisInsight('');
        setAnalysisAnalytics(null);

        try {
            const report = await fetchMarketReport(cleaned, contextId);
            setAnalysisResult(report);
            setAnalysisInsight(report.ai_report || 'Không có insight');
            setAnalysisAnalytics(report.analytics || null);
            setAnalysisCache((prev) => ({
                ...prev,
                [cacheKey]: {
                    report,
                    insight: report.ai_report || 'Không có insight',
                    analytics: report.analytics || null,
                }
            }));
        } catch (err) {
            setError(`❌ Lỗi phân tích từ khóa "${cleaned}": ${err.message}`);
        } finally {
            setAnalysisLoading(false);
            setTimeout(() => lucide.createIcons(), 100);
        }
    };

    const handleExecute = async () => {
        if (!selectedFile) return;

        setLoading(true);
        setError('');
        setKeywords([]);
        setActiveKeyword('');
        setAnalysisResult(null);
        setAnalysisInsight('');
        setAnalysisAnalytics(null);
        setAnalysisCache({});

        try {
            const list = await parseKeywordsFromCsv(selectedFile);
            if (list.length === 0) {
                setError('❌ Không đọc được từ khóa từ file CSV. Vui lòng kiểm tra cột keyword hoặc cột đầu tiên có dữ liệu.');
                setLoading(false);
                return;
            }

            setKeywords(list);
            await runSingleAnalysis(list[0], true);
        } catch (err) {
            setError(`❌ Không xử lý được file CSV: ${err.message}`);
        } finally {
            setLoading(false);
            setTimeout(() => lucide.createIcons(), 100);
        }
    };

    const handleSelectContext = async (contextId) => {
        if (!activeKeyword) return;
        return runSingleAnalysis(activeKeyword, true, contextId);
    };

    const generateAdvisoryAnswer = (choice) => {
        if (!analysisResult || !analysisResult.overview) {
            return `Bạn hãy bấm chọn 1 keyword trong thanh menu CSV trước, sau đó chọn lại số từ 1 đến 5.\n\n${chatHint}`;
        }

        const ov = analysisResult.overview || {};
        const seg = analysisResult.price_segments || {};
        const topProducts = analysisResult.top_products || [];
        const topProduct = topProducts[0] || null;
        const topCategory = (analysisResult.top_categories || [])[0] || null;
        const sentiment = analysisResult.sentiment || {};
        const trend = analysisResult.price_trend || {};

        const avgPrice = Number(ov.avg_price || 0);
        const maxPrice = Number(ov.max_price || 0);
        const priceFloor = Math.round(avgPrice * 0.9);
        const priceCeil = Math.round(avgPrice * 1.05);
        const keywordLabel = activeKeyword || 'dữ liệu hiện tại';
        const withContext = (text) => `Dành cho "${keywordLabel}":\n${text}`;

        const budgetPct = Number(seg.budget?.pct || 0);
        const midPct = Number(seg.mid?.pct || 0);
        const premiumPct = Number(seg.premium?.pct || 0);

        const buildRecommendationHeader = (title, verdict) => `**${title}**\n${verdict}`;
        const buildRecommendationFooter = (nextSteps, caution) =>
            `\n**Việc nên làm ngay**\n${nextSteps}\n\n**Lưu ý**\n${caution}\n\n${chatHint}`;

        const sortedSegments = [
            { name: 'bình dân', pct: budgetPct },
            { name: 'trung cấp', pct: midPct },
            { name: 'cao cấp', pct: premiumPct },
        ].sort((a, b) => b.pct - a.pct);
        const best = sortedSegments[0];
        const second = sortedSegments[1] || sortedSegments[0];

        switch (choice) {
            case '1':
                return withContext(
                    buildRecommendationHeader(
                        'Kết luận nhanh',
                        `Nên ưu tiên phân khúc ${best.name} vì đang có độ phủ mạnh nhất (${best.pct}%).`
                    ) +
                    `\n**Vì sao nên chọn**\n- Phân khúc này đang có lực kéo tốt nhất để ra đơn nhanh hơn.\n- Tệp khách đã rõ, dễ tối ưu nội dung và giá.\n- Giảm rủi ro thử sai so với đổ ngân sách dàn trải.` +
                    buildRecommendationFooter(
                        `1) Dồn 70% ngân sách vào ${best.name}.\n2) Dành 30% thử nghiệm ở ${second.name}.\n3) Theo dõi chuyển đổi theo từng phân khúc mỗi 2 ngày.`,
                        `Không nên dàn đều cả 3 phân khúc; hãy chọn 1 phân khúc chính để thắng nhanh, sau đó mới mở rộng.`
                    )
                );
            case '2':
                return withContext(
                    buildRecommendationHeader(
                        'Kết luận nhanh',
                        `Nên đặt giá quanh ${priceFloor.toLocaleString('vi-VN')}đ - ${priceCeil.toLocaleString('vi-VN')}đ để vừa cạnh tranh vừa giữ biên lợi nhuận.`
                    ) +
                    `\n**Vì sao nên chọn vùng giá này**\n- Bám sát mặt bằng thị trường, không quá rẻ để mất lợi nhuận.\n- Không quá cao để tránh bị loại khỏi nhóm khách nhạy giá.\n- Có thể tạo 1 sản phẩm mồi và 1 sản phẩm lợi nhuận tách biệt.` +
                    buildRecommendationFooter(
                        `1) Đặt 1 SKU mồi ở mức thấp hơn giá trung bình khoảng 2% - 5%.\n2) Giữ SKU chủ lực ở quanh giá trung bình.\n3) Tạo gói combo để kéo giá trị đơn hàng cao hơn.`,
                        `Nếu vượt quá ${maxPrice.toLocaleString('vi-VN')}đ mà chưa có thương hiệu mạnh, khả năng chuyển đổi sẽ giảm rõ rệt.`
                    )
                );
            case '3':
                return withContext(
                    buildRecommendationHeader(
                        'Kết luận nhanh',
                        'Trong 7 ngày tới nên tập trung 3 việc: tăng click, tăng chuyển đổi, và tăng giá trị đơn hàng.'
                    ) +
                    `\n**Kế hoạch triển khai**\n- Tối ưu ngay 3 sản phẩm đầu bảng: ảnh, tiêu đề, 3 USP đầu mô tả.\n- Chạy ưu đãi ngắn hạn cho nhóm giá quanh ${avgPrice.toLocaleString('vi-VN')}đ để đẩy đơn nhanh.\n- Dùng danh mục mạnh nhất${topCategory ? ` (${topCategory.name})` : ''} làm mỏ neo nội dung và A/B test mô tả trong 72 giờ.` +
                    buildRecommendationFooter(
                        `1) Cập nhật ảnh chính và tiêu đề trong hôm nay.\n2) Chạy 1 ưu đãi có thời hạn 72 giờ.\n3) So sánh CTR và doanh thu giữa 2 phiên bản mô tả.`,
                        `Nếu chỉ chạy khuyến mãi mà không sửa nội dung sản phẩm, hiệu quả sẽ rất thấp.`
                    )
                );
            case '4': {
                const negPct = Number(sentiment.neg_pct || 0);
                const riskTrend = trend.direction === 'up' ? 'giá có xu hướng tăng' : trend.direction === 'down' ? 'giá có xu hướng giảm' : 'giá đang đi ngang';
                return withContext(
                    buildRecommendationHeader(
                        'Kết luận nhanh',
                        `${negPct >= 18 ? 'Rủi ro từ phản hồi tiêu cực đang khá đáng chú ý' : 'Rủi ro chính là bị cuốn vào cuộc chiến giá'} và ${riskTrend}.`
                    ) +
                    `\n**Cách xử lý**\n- Chuẩn hóa checklist chất lượng trước giao hàng.\n- Phản hồi đánh giá xấu trong 24 giờ.\n- Theo dõi giá mỗi ngày, điều chỉnh linh hoạt trong biên độ nhỏ.\n\n**Ngưỡng cảnh báo**\n- Sentiment tiêu cực > 20%.\n- Doanh số giảm liên tiếp 3 ngày.\n- Giá đối thủ biến động quá mạnh trong 48 giờ.` +
                    buildRecommendationFooter(
                        `1) Tạo checklist kiểm hàng trước khi xuất đơn.\n2) Gắn người theo dõi review tiêu cực.\n3) Thiết lập cảnh báo khi giá hoặc doanh số biến động bất thường.`,
                        `Nếu bỏ qua review xấu, bot chỉ ra số liệu đẹp nhưng tỉ lệ mua thật vẫn sẽ tụt.`
                    )
                );
            }
            case '5':
                return topProduct
                    ? withContext(
                        buildRecommendationHeader(
                            'Kết luận nhanh',
                            `Sản phẩm top "${topProduct.name}" nên được dùng làm mũi nhọn kéo traffic.`
                        ) +
                        `\n**Hướng tối ưu**\n- Viết lại phần đầu mô tả thành 3 lợi ích mua ngay.\n- Tạo combo hoặc phiên bản nâng cấp để tăng giá trị đơn hàng.\n- Gắn đề xuất chéo sang 2 sản phẩm cùng danh mục để tăng giỏ hàng.` +
                        buildRecommendationFooter(
                            `1) Làm lại 3 dòng đầu mô tả ngay hôm nay.\n2) Tạo combo/bundle cho sản phẩm top.\n3) Gắn 2 sản phẩm liên quan để bán kèm.`,
                            `Nếu chỉ giữ sản phẩm top như hiện tại mà không tối ưu nội dung, bạn đang để traffic trôi đi rất phí.`
                        )
                    )
                    : `Hiện chưa có dữ liệu top sản phẩm. Bạn hãy bấm chọn 1 keyword trước rồi chọn lại câu 5.\n\n${chatHint}`;
            default:
                return `Vui lòng chọn số từ 1 đến 5 theo bảng câu hỏi:\n\n${advisorQuestions.map((q) => `${q.id}. ${q.label}`).join('\n')}\n\n${chatHint}`;
        }
    };

    const buildBatchChatAdvice = (message) => {
        const keywordLabel = activeKeyword || 'dữ liệu hiện tại';
        const withContext = (text) => `Dành cho "${keywordLabel}":\n${text}`;
        const products = analysisResult?.top_products || [];
        if (!products.length) {
            return withContext('Chưa có dữ liệu để tư vấn. Hãy bấm 1 keyword trong menu CSV để tôi trả lời theo đúng từ khóa đó.');
        }

        const normalized = normalizeBotText(message);
        const metrics = products.map((p) => ({
            ...p,
            soldValue: parseFlexibleNumber(p.sold),
            priceValue: parseFlexibleNumber(p.price),
            revenueValue: parseFlexibleNumber(p.revenue),
            ratingValue: parseFlexibleNumber(p.rating),
        }));

        const topSell = [...metrics]
            .sort((a, b) => (b.soldValue + b.ratingValue * 1000) - (a.soldValue + a.ratingValue * 1000))
            .slice(0, 3);

        const topValue = [...metrics]
            .sort((a, b) => (b.revenueValue + b.ratingValue * 100000) - (a.revenueValue + a.ratingValue * 100000))
            .slice(0, 3);

        const budget = extractBudgetFromText(message);
        if (budget > 0 || /(von|ngan sach|budget)/i.test(normalized)) {
            const affordable = metrics
                .filter((item) => item.priceValue > 0 && item.priceValue <= budget)
                .sort((a, b) => (b.ratingValue + b.soldValue / 100000) - (a.ratingValue + a.soldValue / 100000))
                .slice(0, 3);

            if (affordable.length) {
                return withContext(`Với vốn khoảng ${formatCompactMoney(budget)}, nên ưu tiên:\n${affordable.map((item, idx) => `${idx + 1}. ${item.name} | giá ${Number(item.priceValue).toLocaleString('vi-VN')}đ | bán ${item.soldValue.toLocaleString('vi-VN')} | rating ${item.ratingValue.toFixed(1)}/5`).join('\n')}`);
            }
        }

        if (/(top|san pham|de ban|tien nang|ban gi)/i.test(normalized)) {
            return withContext(`Gợi ý nhanh theo keyword đang chọn:\n\nDễ bán nhất:\n${topSell.map((item, idx) => `${idx + 1}. ${item.name} | bán ${item.soldValue.toLocaleString('vi-VN')} | rating ${item.ratingValue.toFixed(1)}/5`).join('\n')}\n\nDoanh thu tốt:\n${topValue.map((item, idx) => `${idx + 1}. ${item.name} | doanh thu ${formatCompactMoney(item.revenueValue)} | giá ${Number(item.priceValue).toLocaleString('vi-VN')}đ`).join('\n')}`);
        }

        return withContext(`Tôi đang bám đúng keyword bạn đang chọn trong menu CSV. Bạn có thể:\n1. Bấm nhanh 1-5 để nhận tư vấn chiến lược\n2. Hỏi tự do: "vốn 2 triệu nên bán gì" hoặc "rủi ro hiện tại là gì"`);
    };

    const resolveQuickPrompt = (template) => {
        const currentKeyword = (activeKeyword || '').trim() || 'từ khóa hiện tại';
        const topProduct = analysisResult && analysisResult.top_products && analysisResult.top_products[0] ? analysisResult.top_products[0].name : 'sản phẩm top 1 hiện tại';
        return template
            .replace('{keyword}', currentKeyword)
            .replace('{top_product}', topProduct);
    };

    const sendChatQuestion = async (questionText) => {
        const question = (questionText || '').trim();
        if (!question || chatLoading) return;

        const newUserMessages = [...chatMessages, { role: 'user', text: question }];
        saveMessages(newUserMessages);
        setChatInput('');
        setChatLoading(true);

        try {
            const res = await fetch(`${API_BASE_URL}/api/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: question,
                    session_id: activeSessionId
                })
            });
            
            if (!res.ok) {
                throw new Error(`Server returned HTTP ${res.status}`);
            }
            
            const data = await res.json();
            if (data.success) {
                const newAssistantMessages = [...newUserMessages, { role: 'assistant', text: data.response }];
                saveMessages(newAssistantMessages);
                if (data.profile) {
                    setUserProfile(data.profile);
                }
                if (data.active_business) {
                    setActiveBusiness(data.active_business);
                }
            } else {
                saveMessages([...newUserMessages, { role: 'assistant', text: `❌ Lỗi: ${data.response || 'Không thể xử lý yêu cầu'}` }]);
            }
        } catch (error) {
            saveMessages([...newUserMessages, { role: 'assistant', text: `❌ Lỗi kết nối: ${error.message}` }]);
        } finally {
            setChatLoading(false);
            setTimeout(() => lucide.createIcons(), 100);
        }
    };

    const handleSendChat = async () => {
        await sendChatQuestion(chatInput);
    };

    const handleQuickCommand = async (promptTemplate) => {
        const prompt = resolveQuickPrompt(promptTemplate);
        setIsChatOpen(true);
        await sendChatQuestion(prompt);
    };

    const handleExportPDF = () => {
        if (!analysisResult) return;
        const titleKeyword = activeKeyword || (selectedFile ? selectedFile.name : 'File CSV');
        const element = document.createElement('div');
        const exportRows = (analysisResult.top_products || []).map((p, idx) => ({
            id: idx + 1,
            name: p.name,
            cat: p.category,
            price: `${Number(p.price || 0).toLocaleString('vi-VN')}đ`,
            sold: Number(p.sold || 0).toLocaleString('vi-VN'),
            rev: `${Number(p.revenue || 0).toLocaleString('vi-VN')}đ`,
            url: p.url || ''
        }));
        element.innerHTML = buildPdfHtml(exportRows, analysisInsight, titleKeyword, false);
        html2pdf().set({
            margin: 10,
            filename: `BaoCao_Batch_${Date.now()}.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2 },
            jsPDF: { orientation: 'portrait', unit: 'mm', format: 'a4' }
        }).from(element).save();
    };

    const handleOpenReviews = async (product) => {
        setReviewModal({ open: true, product, reviews: [], loading: true, error: null });
        try {
            const pid = product.product_id || product.id || '';
            if (!pid) throw new Error('Không tìm thấy product_id');
            const res = await fetch(`${API_BASE_URL}/api/product-reviews/${pid}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            setReviewModal({ open: true, product, reviews: json.data || [], loading: false, error: null });
        } catch (e) {
            setReviewModal(prev => ({ ...prev, loading: false, error: e.message }));
        }
    };

    return (
        <>
            <div>
                {/* FILE UPLOAD SECTION */}
                <div className="max-w-4xl mx-auto mb-8">
                    <div className="glass-panel p-8 rounded-xl text-center animate-fade-in">
                        <div
                            className="border-2 border-dashed border-gray-300 rounded-xl p-8 hover:border-blue-500 hover:bg-rose-500/5 transition-all cursor-pointer group"
                            onClick={() => document.getElementById('fileInput').click()}
                        >
                            <input id="fileInput" type="file" accept=".csv" className="hidden" onChange={handleFileChange} />
                            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform">
                                <Icon name="upload-cloud" size={32} className="text-blue-500" />
                            </div>
                            <h3 className="text-lg font-bold text-gray-900 mb-1">
                                {selectedFile ? selectedFile.name : 'Click để tải lên file CSV'}
                            </h3>
                            <p className="text-sm text-gray-500">
                                {selectedFile ? `${(selectedFile.size / 1024).toFixed(2)} KB` : 'Hỗ trợ .csv (Max 50MB)'}
                            </p>
                        </div>
                        {selectedFile && (
                            <div className="mt-4 flex justify-center">
                                <button
                                    onClick={handleExecute}
                                    disabled={loading}
                                    className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg flex items-center gap-2 transition-all shadow-lg shadow-blue-200"
                                >
                                    {loading ? <Icon name="loader-2" className="animate-spin" /> : <Icon name="play" className="fill-current" />}
                                    Phân tích File
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* LOADING */}
                {loading && (
                    <div className="flex flex-col items-center justify-center py-20 text-blue-500 animate-pulse">
                        <Icon name="bot" size={48} className="mb-4" />
                        <p className="text-lg font-medium">Đang đọc danh sách từ khóa từ CSV...</p>
                        <p className="text-sm text-gray-500">Vui lòng đợi</p>
                    </div>
                )}

                {/* KEYWORD MENU */}
                {!loading && keywords.length > 0 && (
                    <div className="max-w-6xl mx-auto mb-4 animate-fade-in">
                        <div className="bg-white rounded-xl border border-blue-100 p-4">
                            <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
                                <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                                    <Icon name="rows-3" size={16} className="text-blue-500" />
                                    Danh sách từ khóa trong file CSV ({keywords.length})
                                </h3>
                                <span className="text-xs text-gray-500">Bấm vào từ khóa để xem phân tích đơn ở phía dưới</span>
                            </div>
                            <div className="overflow-x-auto pb-1">
                                <div className="flex gap-2 min-w-max">
                                    {keywords.map((kw) => (
                                        <button
                                            key={kw}
                                            onClick={() => runSingleAnalysis(kw)}
                                            className={`px-4 py-2 rounded-full border text-sm font-medium whitespace-nowrap transition-all ${activeKeyword === kw
                                                    ? 'bg-blue-600 text-white border-blue-400'
                                                    : 'bg-white text-gray-700 border-gray-300 hover:border-blue-500 hover:text-blue-700'
                                                }`}
                                        >
                                            {kw}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* EXPORT BUTTON */}
                {!loading && analysisResult && (
                    <div className="max-w-6xl mx-auto flex justify-end mb-2">
                        <button
                            onClick={handleExportPDF}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg shadow-blue-900/20"
                        >
                            <Icon name="download" size={16} /> Xuất PDF
                        </button>
                    </div>
                )}

                {/* SELECTED KEYWORD ANALYSIS */}
                {!loading && keywords.length > 0 && (
                    <div className="max-w-6xl mx-auto">
                        <div className="mb-4 px-1 text-sm text-gray-700">
                            Đang xem phân tích đơn cho từ khóa: <span className="font-bold text-blue-700">{activeKeyword || '...'}</span>
                        </div>

                        {analysisLoading && (
                            <div className="bg-white rounded-xl border border-blue-100 p-6 text-blue-700 animate-pulse text-sm">
                                Đang phân tích báo cáo cho từ khóa "{activeKeyword}"...
                            </div>
                        )}

                        {!analysisLoading && error && (
                            <div className="bg-red-50 border border-red-500 rounded-xl p-5 text-red-600 whitespace-pre-wrap">
                                {error}
                            </div>
                        )}

                        {!analysisLoading && analysisResult && (() => {
                            const d = analysisResult;
                            const ov = d.overview || {};
                            const seg = d.price_segments || {};
                            const trend = d.price_trend || {};
                            const sent = d.sentiment || {};
                            const ctx = d.context || null;
                            const topProducts = d.top_products || [];
                            const topCategories = d.top_categories || [];

                            return (
                                <div className="space-y-6 animate-fade-in pb-10 mt-2">
                                    {ctx && (
                                        <div className="bg-white rounded-xl border border-blue-100 p-5">
                                            <div className="flex items-center justify-between gap-3 flex-wrap">
                                                <h3 className="font-bold text-gray-900 flex items-center gap-2">
                                                    <Icon name="sparkles" size={18} className="text-blue-500" /> Bạn có đang tìm kiếm...?
                                                </h3>
                                                {ctx.selected_context && (
                                                    <span className="text-xs text-gray-500">
                                                        Ngữ cảnh đang chọn: <span className="text-blue-700 font-semibold">{ctx.selected_context_label || ctx.selected_context}</span>
                                                    </span>
                                                )}
                                            </div>

                                            <div className="mt-4 flex flex-wrap gap-2">
                                                {ctx.selected_context && (
                                                    <span className="px-3 py-1.5 rounded-full text-xs font-semibold border bg-blue-600 text-white border-blue-400">
                                                        {ctx.selected_context_label || ctx.selected_context}
                                                    </span>
                                                )}
                                                {ctx.suggestions && ctx.suggestions.map((s) => (
                                                    <button
                                                        key={s.context_id}
                                                        onClick={() => handleSelectContext(s.context_id)}
                                                        disabled={analysisLoading}
                                                        className="px-3 py-1.5 rounded-full text-xs font-semibold border transition-all bg-white text-gray-800 border-gray-300 hover:border-blue-500 hover:text-blue-700"
                                                        title={`${s.count} sản phẩm`}
                                                    >
                                                        {s.label} <span className="opacity-70">({s.count})</span>
                                                    </button>
                                                ))}
                                            </div>

                                            {ctx.total_found_before_filter !== undefined && (
                                                <div className="mt-3 text-xs text-gray-500">
                                                    Lọc theo ngữ cảnh: {(ctx.total_found_after_filter ?? 0).toLocaleString('vi-VN')} / {(ctx.total_found_before_filter ?? 0).toLocaleString('vi-VN')} sản phẩm
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        {[
                                            { label: 'Tổng Sản Phẩm', val: Number(ov.total_products || 0).toLocaleString('vi-VN'), icon: 'package', color: 'text-blue-400' },
                                            { label: 'Tổng Đã Bán', val: Number(ov.total_sold || 0).toLocaleString('vi-VN'), icon: 'shopping-cart', color: 'text-green-600' },
                                            { label: 'Tổng Doanh Thu', val: formatVND(Number(ov.total_revenue || 0)), icon: 'dollar-sign', color: 'text-yellow-400' },
                                            { label: 'Rating TB', val: `${Number(ov.avg_rating || 0).toFixed(2)} ⭐`, icon: 'star', color: 'text-blue-500' },
                                        ].map((item, idx) => (
                                            <div key={idx} className="bg-white p-5 rounded-xl border border-blue-100">
                                                <div className="flex justify-between items-start mb-2">
                                                    <span className="text-gray-500 text-xs">{item.label}</span>
                                                    <Icon name={item.icon} size={16} className={item.color} />
                                                </div>
                                                <div className="text-xl font-bold text-gray-900">{item.val}</div>
                                                {item.label === 'Tổng Sản Phẩm' && (
                                                    <div className="text-xs text-gray-500 mt-1">{Number(ov.min_price || 0).toLocaleString('vi-VN')}đ – {Number(ov.max_price || 0).toLocaleString('vi-VN')}đ</div>
                                                )}
                                                {item.label === 'Tổng Đã Bán' && (
                                                    <div className="text-xs text-gray-500 mt-1">Giá TB: {Number(ov.avg_price || 0).toLocaleString('vi-VN')}đ</div>
                                                )}
                                            </div>
                                        ))}
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div className="bg-white rounded-xl border border-blue-100 p-5">
                                            <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                                                <Icon name="layers" size={16} className="text-purple-400" />Phân Khúc Giá
                                                <PriceSegmentTooltip />
                                            </h3>
                                            {[
                                                { label: '💙 Bình dân', data: seg.budget || { count: 0, pct: 0 }, color: 'bg-blue-500' },
                                                { label: '💚 Trung cấp', data: seg.mid || { count: 0, pct: 0 }, color: 'bg-green-500' },
                                                { label: '💎 Cao cấp', data: seg.premium || { count: 0, pct: 0 }, color: 'bg-purple-500' },
                                            ].map((s, i) => (
                                                <div key={i} className="mb-3">
                                                    <div className="flex justify-between text-sm mb-1">
                                                        <span className="text-gray-700">{s.label}</span>
                                                        <span className="text-gray-500">{s.data.count} SP ({s.data.pct}%)</span>
                                                    </div>
                                                    <div className="w-full bg-gray-200 rounded-full h-2">
                                                        <div className={`${s.color} h-2 rounded-full transition-all`} style={{ width: `${s.data.pct}%` }}></div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>

                                        <div className="bg-white rounded-xl border border-blue-100 p-5">
                                            <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                                                <Icon name="message-circle" size={16} className="text-blue-500" />Sentiment Đánh Giá
                                            </h3>
                                            {sent.total > 0 ? (
                                                <>
                                                    <div className="text-xs text-gray-500 mb-3">Từ {Number(sent.total || 0).toLocaleString('vi-VN')} đánh giá</div>
                                                    {[
                                                        { label: '✅ Tích cực', count: sent.positive || 0, pct: sent.pos_pct || 0, color: 'bg-green-500' },
                                                        { label: '⚠️ Trung lập', count: sent.neutral || 0, pct: sent.neu_pct || 0, color: 'bg-yellow-500' },
                                                        { label: '❌ Tiêu cực', count: sent.negative || 0, pct: sent.neg_pct || 0, color: 'bg-red-500' },
                                                    ].map((s, i) => (
                                                        <div key={i} className="mb-3">
                                                            <div className="flex justify-between text-sm mb-1">
                                                                <span className="text-gray-700">{s.label}</span>
                                                                <span className="text-gray-500">{Number(s.count).toLocaleString('vi-VN')} ({s.pct}%)</span>
                                                            </div>
                                                            <div className="w-full bg-gray-200 rounded-full h-2">
                                                                <div className={`${s.color} h-2 rounded-full`} style={{ width: `${s.pct}%` }}></div>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </>
                                            ) : (
                                                <div className="text-gray-500 text-sm">Không có đánh giá cho từ khóa này</div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 gap-4">
                                        <div className="bg-white rounded-xl border border-blue-100 p-5">
                                            <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                                                <Icon name="folder-open" size={16} className="text-orange-400" />Top Danh Mục
                                            </h3>
                                            <div className="space-y-2">
                                                {topCategories.map((cat, i) => (
                                                    <div key={i} className="flex items-center gap-3">
                                                        <span className="text-gray-500 text-xs w-4">{i + 1}</span>
                                                        <span className="text-gray-700 text-sm flex-1 truncate" title={cat.name}>{cat.name}</span>
                                                        <span className="text-xs text-gray-500">{cat.count} SP</span>
                                                        <div className="w-16 bg-gray-200 rounded-full h-1.5">
                                                            <div className="bg-orange-500 h-1.5 rounded-full" style={{ width: `${cat.pct}%` }}></div>
                                                        </div>
                                                        <span className="text-xs text-orange-400 w-10 text-right">{cat.pct}%</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>

                                    <div className="bg-white rounded-xl border border-blue-100 overflow-hidden shadow-sm">
                                        {/* Header + Price Filter */}
                                        <div className="p-4 border-b border-blue-100 bg-blue-50 flex flex-col gap-3">
                                            <div className="flex flex-wrap items-center justify-between gap-3">
                                                <h3 className="font-bold text-gray-900 flex items-center gap-2">
                                                    <Icon name="trophy" size={18} className="text-yellow-500" />Top 10 Sản Phẩm Bán Chạy
                                                </h3>
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    <span className="text-xs text-gray-500 mr-1">Phân khúc giá:</span>
                                                    {[
                                                        { key: 'all', label: 'Tất cả', icon: '📦', activeClass: 'bg-gray-500 text-white border-gray-400' },
                                                        { key: 'budget', label: 'Bình dân', icon: '💙', activeClass: 'bg-blue-600 text-white border-blue-400' },
                                                        { key: 'mid', label: 'Trung cấp', icon: '💚', activeClass: 'bg-green-600 text-white border-green-400' },
                                                        { key: 'premium', label: 'Cao cấp', icon: '💎', activeClass: 'bg-purple-600 text-white border-purple-400' },
                                                    ].map(({ key, label, icon, activeClass }) => (
                                                        <button
                                                            key={key}
                                                            onClick={() => { setBatchPriceFilter(key); setBatchPage(1); }}
                                                            className={`px-3 py-1 rounded-full text-xs font-semibold border transition-all ${batchPriceFilter === key
                                                                ? activeClass
                                                                : 'bg-transparent text-gray-700 border-gray-300 hover:border-gray-400 hover:text-gray-900'
                                                                }`}
                                                        >
                                                            {icon} {label}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>

                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm">
                                                <thead className="text-xs text-gray-500 uppercase border-b border-blue-100">
                                                    <tr>
                                                        <th className="px-4 py-3 text-center w-10">#</th>
                                                        <th className="px-4 py-3 text-left">Sản phẩm</th>
                                                        <th className="px-4 py-3 text-right">Giá</th>
                                                        <th className="px-4 py-3 text-right">Đã bán</th>
                                                        <th className="px-4 py-3 text-right">Doanh thu</th>
                                                        <th className="px-4 py-3 text-right">Rating</th>
                                                        <th className="px-4 py-3 text-center">Đánh Giá</th>
                                                        <th className="px-4 py-3 text-center">Link</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-gray-100">
                                                    {(() => {
                                                        const avgPrice = analysisAnalytics ? Number(analysisAnalytics.avg_price || 0) : 0;
                                                        const budgetMax = avgPrice * 0.7;
                                                        const premiumMin = avgPrice * 1.3;

                                                        const filtered = topProducts.filter(p => {
                                                            const price = Number(p.price || 0);
                                                            if (batchPriceFilter === 'budget') return price < budgetMax;
                                                            if (batchPriceFilter === 'mid') return price >= budgetMax && price <= premiumMin;
                                                            if (batchPriceFilter === 'premium') return price > premiumMin;
                                                            return true;
                                                        });

                                                        if (filtered.length === 0) return (
                                                            <tr><td colSpan={8} className="px-4 py-10 text-center text-gray-500">
                                                                Không có sản phẩm nào trong phân khúc này.
                                                            </td></tr>
                                                        );

                                                        const itemsPerPage = 10;
                                                        const totalPages = Math.ceil(filtered.length / itemsPerPage);
                                                        const safePage = Math.min(batchPage, totalPages);
                                                        const startIdx = (safePage - 1) * itemsPerPage;
                                                        const pageItems = filtered.slice(startIdx, startIdx + itemsPerPage);

                                                        return pageItems.map((p, idx) => {
                                                            const globalIdx = topProducts.indexOf(p);
                                                            const isTop3 = globalIdx < 3;
                                                            return (
                                                                <tr key={idx} className={`${isTop3 ? 'bg-blue-50 border-l-2 border-blue-400' : 'hover:bg-blue-50/50'} transition-colors`}>
                                                                    <td className="px-4 py-3 text-center">
                                                                        {isTop3
                                                                            ? <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-blue-600 text-white">TOP {globalIdx + 1}</span>
                                                                            : <span className="text-gray-500">{startIdx + idx + 1}</span>}
                                                                    </td>
                                                                    <td className="px-4 py-3 text-gray-900 max-w-[220px] truncate" title={p.name}>
                                                                        {isTop3 && <span className="text-blue-500 mr-1">🏆</span>}{p.name}
                                                                    </td>
                                                                    <td className="px-4 py-3 text-right text-gray-600">{Number(p.price || 0).toLocaleString('vi-VN')}đ</td>
                                                                    <td className="px-4 py-3 text-right text-green-600 font-medium">{Number(p.sold || 0).toLocaleString('vi-VN')}</td>
                                                                    <td className="px-4 py-3 text-right text-blue-600 font-bold">{formatVND(Number(p.revenue || 0))}</td>
                                                                    <td className="px-4 py-3 text-right text-yellow-500 font-medium">{Number(p.rating || 0).toFixed(2)} ⭐</td>
                                                                    <td className="px-4 py-3 text-center">
                                                                        <button onClick={() => handleOpenReviews(p)} className="inline-flex items-center px-2 py-1 rounded-lg text-xs bg-gray-200 hover:bg-blue-200 text-gray-900 transition-colors gap-1">
                                                                            <Icon name="message-square" size={11} /> Đánh giá
                                                                        </button>
                                                                    </td>
                                                                    <td className="px-4 py-3 text-center">
                                                                        <a href={p.url || `https://tiki.vn/p/${p.name}`} target="_blank" rel="noopener noreferrer"
                                                                            className="inline-flex items-center px-3 py-1 rounded-lg text-xs bg-blue-600 hover:bg-blue-700 text-white transition-colors">
                                                                            <Icon name="external-link" size={12} className="mr-1" />Xem
                                                                        </a>
                                                                    </td>
                                                                </tr>
                                                            );
                                                        });
                                                    })()}
                                                </tbody>
                                            </table>
                                        </div>

                                        {/* Pagination */}
                                        {(() => {
                                            const avgPrice = analysisAnalytics ? Number(analysisAnalytics.avg_price || 0) : 0;
                                            const budgetMax = avgPrice * 0.7;
                                            const premiumMin = avgPrice * 1.3;
                                            const filtered = topProducts.filter(p => {
                                                const price = Number(p.price || 0);
                                                if (batchPriceFilter === 'budget') return price < budgetMax;
                                                if (batchPriceFilter === 'mid') return price >= budgetMax && price <= premiumMin;
                                                if (batchPriceFilter === 'premium') return price > premiumMin;
                                                return true;
                                            });
                                            const totalPages = Math.ceil(filtered.length / 10);
                                            const safePage = Math.min(batchPage, Math.max(totalPages, 1));
                                            const start = (safePage - 1) * 10 + 1;
                                            const end = Math.min(safePage * 10, filtered.length);
                                            if (filtered.length <= 10) return null;
                                            return (
                                                <div className="p-4 border-t border-blue-100 bg-blue-50 flex justify-between items-center">
                                                    <span className="text-sm text-gray-500">
                                                        Hiển thị {start}–{end} / {filtered.length} sản phẩm
                                                        {batchPriceFilter !== 'all' && <span className="ml-2 text-xs text-blue-500">(đã lọc)</span>}
                                                    </span>
                                                    <div className="flex gap-2">
                                                        <button
                                                            onClick={() => setBatchPage(p => Math.max(p - 1, 1))}
                                                            disabled={safePage <= 1}
                                                            className="px-3 py-1.5 bg-white border border-gray-200 hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-gray-900 text-sm font-medium transition-colors"
                                                        >Trước</button>
                                                        <span className="px-3 py-1.5 text-sm text-gray-700">{safePage} / {totalPages}</span>
                                                        <button
                                                            onClick={() => setBatchPage(p => Math.min(p + 1, totalPages))}
                                                            disabled={safePage >= totalPages}
                                                            className="px-3 py-1.5 bg-white border border-gray-200 hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-gray-900 text-sm font-medium transition-colors"
                                                        >Sau</button>
                                                    </div>
                                                </div>
                                            );
                                        })()}
                                    </div>

                                    <div className="ai-insight-gradient rounded-xl p-6 relative overflow-hidden border border-blue-200 shadow-sm">
                                        <div className="absolute top-0 right-0 w-64 h-64 bg-blue-200/30 rounded-full blur-3xl -mr-20 -mt-20"></div>
                                        <div className="relative z-10">
                                            <div className="flex items-center gap-3 mb-4">
                                                <div className="p-2 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg text-white shadow-md">
                                                    <Icon name="bot" size={24} />
                                                </div>
                                                <div>
                                                    <h3 className="text-lg font-bold text-gray-900">Báo Cáo Phân Tích AI</h3>
                                                    <p className="text-xs text-blue-500">Phân tích chuyên sâu từ Gemini AI</p>
                                                </div>
                                            </div>
                                            <div className="bg-white/70 backdrop-blur-sm rounded-lg p-4 border border-blue-100 text-sm leading-relaxed text-gray-800">
                                                {renderFormattedInsight(analysisInsight)}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })()}
                    </div>
                )}

                {/* EMPTY STATE */}
                {!loading && keywords.length === 0 && !selectedFile && (
                    <div className="flex flex-col items-center justify-center h-64 text-gray-500 opacity-60">
                        <Icon name="bar-chart-2" size={64} className="mb-4" />
                        <p className="text-lg">Tải lên CSV để phân tích</p>
                    </div>
                )}

                {!loading && keywords.length === 0 && selectedFile && error && (
                    <div className="max-w-4xl mx-auto bg-red-50 border border-red-500 rounded-xl p-5 text-red-600 whitespace-pre-wrap">
                        {error}
                    </div>
                )}

                {/* FLOATING CHATBOT */}
                <div className="fixed bottom-6 right-6 z-40">
                    <button
                        onClick={() => setIsChatOpen((prev) => !prev)}
                        className="w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-600 text-white shadow-xl shadow-blue-200/60 flex items-center justify-center border border-cyan-400/40"
                        title="Mở chatbot"
                    >
                        <Icon name={isChatOpen ? 'x' : 'message-circle'} size={24} />
                    </button>
                </div>

                {isChatOpen && (
                    <div className="fixed bottom-24 right-3 left-3 sm:left-auto sm:right-6 sm:w-[410px] z-40">
                        <div className="bg-white rounded-xl border border-blue-100 overflow-hidden shadow-2xl flex flex-col max-h-[500px]">
                            {/* Header */}
                            <div className="p-3 border-b border-blue-100 bg-blue-600 text-white flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2 flex-1 min-w-0">
                                    <button 
                                        onClick={() => setIsSessionListOpen(!isSessionListOpen)}
                                        className="p-1 hover:bg-blue-700 rounded text-white flex items-center justify-center transition-colors"
                                        title="Danh sách cuộc hội thoại"
                                        type="button"
                                    >
                                        <Icon name="menu" size={16} />
                                    </button>
                                    <Icon name="sparkles" size={16} className="text-white fill-current animate-pulse flex-shrink-0" />
                                    <h3 className="font-bold text-xs truncate" title={sessions.find(s => s.id === activeSessionId)?.name || 'AI Assistant'}>
                                        {sessions.find(s => s.id === activeSessionId)?.name || 'AI Assistant'}
                                    </h3>
                                </div>
                                <div className="flex items-center gap-1 flex-shrink-0">
                                    <button
                                        onClick={() => {
                                            const name = prompt("Nhập tên cuộc hội thoại mới:", `Hội thoại ${sessions.length + 1}`);
                                            if (name && name.trim()) {
                                                handleCreateSession(name.trim());
                                            } else if (name !== null) {
                                                handleCreateSession();
                                            }
                                        }}
                                        className="p-1 hover:bg-blue-700 rounded text-white flex items-center justify-center transition-colors"
                                        title="Tạo hội thoại mới"
                                        type="button"
                                    >
                                        <Icon name="plus" size={16} />
                                    </button>
                                    <button
                                        onClick={(e) => handleDeleteSession(activeSessionId, e)}
                                        className="p-1 hover:bg-blue-700 rounded text-white flex items-center justify-center transition-colors"
                                        title="Xóa hội thoại hiện tại"
                                        type="button"
                                    >
                                        <Icon name="trash-2" size={16} />
                                    </button>
                                    <button
                                        onClick={() => setIsChatOpen(false)}
                                        className="p-1 hover:bg-blue-700 rounded text-white flex items-center justify-center transition-colors flex-shrink-0"
                                    >
                                        <Icon name="x" size={16} />
                                    </button>
                                </div>
                            </div>

                            {/* Session List Panel */}
                            {isSessionListOpen && (
                                <div className="bg-blue-50 border-b border-blue-100 p-3 space-y-2 max-h-[220px] overflow-y-auto animate-fade-in text-[11px] text-gray-800">
                                    <div className="flex justify-between items-center mb-1">
                                        <span className="font-bold text-blue-900">Các cuộc hội thoại</span>
                                        <button 
                                            onClick={() => {
                                                const name = prompt("Nhập tên cuộc hội thoại mới:", `Hội thoại ${sessions.length + 1}`);
                                                if (name && name.trim()) {
                                                    handleCreateSession(name.trim());
                                                } else if (name !== null) {
                                                    handleCreateSession();
                                                }
                                            }}
                                            className="px-2 py-1 bg-blue-600 text-white rounded font-bold hover:bg-blue-700 transition-colors flex items-center gap-1"
                                        >
                                            <Icon name="plus" size={10} /> Mới
                                        </button>
                                    </div>
                                    <div className="space-y-1">
                                        {sessions.map((s) => (
                                            <div 
                                                key={s.id}
                                                onClick={() => {
                                                    setActiveSessionId(s.id);
                                                    localStorage.setItem('tiki_chat_active_session_id', s.id);
                                                    setIsSessionListOpen(false);
                                                }}
                                                className={`p-2 rounded flex justify-between items-center cursor-pointer transition-colors ${
                                                    s.id === activeSessionId 
                                                        ? 'bg-blue-600 text-white font-semibold' 
                                                        : 'bg-white hover:bg-blue-100 text-gray-700 border border-gray-150'
                                                }`}
                                            >
                                                <span className="truncate max-w-[200px]">{s.name}</span>
                                                {sessions.length > 1 && (
                                                    <button 
                                                        onClick={(e) => handleDeleteSession(s.id, e)}
                                                        className={`p-1 rounded transition-colors ${
                                                            s.id === activeSessionId 
                                                                ? 'text-blue-200 hover:text-white hover:bg-blue-700' 
                                                                : 'text-gray-400 hover:text-red-500 hover:bg-gray-100'
                                                        }`}
                                                        title="Xóa hội thoại"
                                                    >
                                                        <Icon name="trash-2" size={12} />
                                                    </button>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* User Profile Bar (if capital is set) */}
                            {userProfile.capital && (
                                <div className="px-3 py-1.5 bg-blue-50 border-b border-blue-100 text-[10px] text-blue-800 flex justify-between items-center font-medium">
                                    <span>💰 Vốn: {Number(userProfile.capital).toLocaleString('vi-VN')}đ</span>
                                    <span>📍 Khu vực: {userProfile.location}</span>
                                    {activeBusiness && <span className="truncate max-w-[120px]" title={activeBusiness}>🎯 Đang chọn: {activeBusiness}</span>}
                                </div>
                            )}

                            {/* Shortcut Commands */}
                            <div className="p-2.5 border-b border-blue-100 bg-gray-50/50">
                                <p className="text-[10px] text-gray-500 mb-1">Gợi ý phân tích nhanh cho "{activeKeyword || 'từ khóa'}":</p>
                                <div className="grid grid-cols-4 gap-1">
                                    {quickCommands.slice(0, 4).map((cmd) => (
                                        <button
                                            key={cmd.id}
                                            onClick={() => handleQuickCommand(cmd.prompt)}
                                            disabled={chatLoading}
                                            className="text-[9px] truncate px-1 py-1 rounded border border-gray-300 text-gray-700 hover:border-blue-500 hover:text-blue-700 bg-white transition-all disabled:opacity-50"
                                            title={cmd.label}
                                        >
                                            {cmd.label}
                                        </button>
                                    ))}
                                    {quickCommands.slice(4, 8).map((cmd) => (
                                        <button
                                            key={cmd.id}
                                            onClick={() => handleQuickCommand(cmd.prompt)}
                                            disabled={chatLoading}
                                            className="text-[9px] truncate px-1 py-1 rounded border border-gray-300 text-gray-700 hover:border-blue-500 hover:text-blue-700 bg-white transition-all disabled:opacity-50"
                                            title={cmd.label}
                                        >
                                            {cmd.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Messages area */}
                            <div ref={chatContainerRef} className="h-64 overflow-y-auto p-3 space-y-3 bg-gray-50 flex-1">
                                {chatMessages.map((m, idx) => (
                                    <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                        <div 
                                            className={`max-w-[90%] px-3 py-2 rounded-lg text-xs leading-relaxed shadow-sm ${
                                                m.role === 'user' 
                                                    ? 'bg-blue-600 text-white rounded-br-none' 
                                                    : 'bg-white border border-gray-100 text-gray-800 rounded-bl-none'
                                            }`}
                                            dangerouslySetInnerHTML={{ __html: parseMarkdown(m.text) }}
                                        />
                                    </div>
                                ))}
                                {chatLoading && (
                                    <div className="text-[10px] text-gray-500 flex items-center gap-1">
                                        <Icon name="loader-2" size={10} className="animate-spin text-blue-500" />
                                        Trợ lý AI đang phân tích dữ liệu...
                                    </div>
                                )}
                            </div>

                            {/* Smart followups */}
                            {activeBusiness && (
                                <div className="px-3 py-1.5 border-t border-blue-55 bg-blue-50/30 flex flex-wrap gap-1">
                                    <button
                                        onClick={() => sendChatQuestion(`Ước tính lợi nhuận chi tiết của ý tưởng ${activeBusiness}`)}
                                        disabled={chatLoading}
                                        className="text-[9px] px-2 py-0.5 rounded bg-blue-100 hover:bg-blue-200 text-blue-800 font-medium transition-colors"
                                    >
                                        📊 Lợi nhuận
                                    </button>
                                    <button
                                        onClick={() => sendChatQuestion(`Đánh giá rủi ro và phản hồi của khách hàng về sản phẩm ${activeBusiness}`)}
                                        disabled={chatLoading}
                                        className="text-[9px] px-2 py-0.5 rounded bg-amber-100 hover:bg-amber-200 text-amber-800 font-medium transition-colors"
                                    >
                                        ⚠️ Rủi ro & Đánh giá
                                    </button>
                                    <button
                                        onClick={() => sendChatQuestion(`Cho tôi một lộ trình/roadmap triển khai cụ thể để bắt đầu bán ${activeBusiness}`)}
                                        disabled={chatLoading}
                                        className="text-[9px] px-2 py-0.5 rounded bg-green-100 hover:bg-green-200 text-green-800 font-medium transition-colors"
                                    >
                                        🚀 Lộ trình triển khai
                                    </button>
                                </div>
                            )}

                            {/* Chat input form */}
                            <div className="p-2.5 border-t border-blue-100 flex items-center gap-1.5 bg-white">
                                <input
                                    type="text"
                                    value={chatInput}
                                    onChange={(e) => setChatInput(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleSendChat()}
                                    placeholder="Đặt câu hỏi tư vấn (ví dụ: tôi có 200M vốn...)"
                                    className="flex-1 bg-white border border-gray-300 rounded-lg px-3 py-1.5 text-xs focus:border-blue-500 focus:ring-1 focus:ring-blue-400 outline-none transition-all"
                                />
                                <button
                                    onClick={handleSendChat}
                                    disabled={chatLoading || !chatInput.trim()}
                                    className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 disabled:cursor-not-allowed text-white text-xs font-bold transition-all shadow shadow-blue-200"
                                >
                                    Gửi
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* REVIEW MODAL */}
            {reviewModal.open && (
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
                                                    {[{ label: 'Tích cực', count: pos, pct: pPct, color: 'bg-green-500' },
                                                    { label: 'Trung lập', count: neu, pct: uPct, color: 'bg-yellow-500' },
                                                    { label: 'Tiêu cực', count: neg, pct: nPct, color: 'bg-red-500' }].map((s, i) => (
                                                        <div key={i}>
                                                            <div className="flex justify-between text-sm mb-1.5">
                                                                <span className="flex items-center gap-1.5 text-gray-700">
                                                                    <div className={`w-3 h-3 ${s.color} rounded-sm`}></div> {s.label}
                                                                </span>
                                                                <span className="text-gray-500">{s.count} ({s.pct}%)</span>
                                                            </div>
                                                            <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                                                                <div className={`${s.color} h-1.5 rounded-full`} style={{ width: `${s.pct}%` }}></div>
                                                            </div>
                                                        </div>
                                                    ))}
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




