// ============================================================
// 🔍 SINGLE PAGE — Phân tích đơn (từ khóa)
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

function SinglePage() {
    const { useState, useEffect } = React;
    const chatContainerRef = React.useRef(null);
    const SEARCH_HISTORY_KEY = 'tiki_search_history_v1';
    const HISTORY_LIMIT = 12;

    const [keyword, setKeyword] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [insight, setInsight] = useState('');
    const [contextInfo, setContextInfo] = useState(null);
    const [analytics, setAnalytics] = useState(null);
    const [searchHistory, setSearchHistory] = useState([]);
    
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
    const [reviewModal, setReviewModal] = useState({ open: false, product: null, reviews: [], loading: false, error: null });

    // Scroll to bottom when new messages arrive or chat opens
    useEffect(() => {
        if (chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
    }, [chatMessages, isChatOpen]);

    const quickCommands = [
        { id: 'overview', label: 'Tom tat nhanh', prompt: 'Tom tat tong quan cho tu khoa {keyword}' },
        { id: 'price', label: 'Gia trung binh', prompt: 'Gia trung binh hien tai la bao nhieu?' },
        { id: 'revenue', label: 'Tong doanh thu', prompt: 'Tong doanh thu uoc tinh cua ket qua nay la gi?' },
        { id: 'sold', label: 'So luong ban', prompt: 'Tong so luong ban cua nhom san pham nay la bao nhieu?' },
        { id: 'top3', label: 'Top 3 san pham', prompt: 'Top 3 san pham dang noi bat la gi?' },
        { id: 'top1', label: 'Phan tich top 1', prompt: 'Phan tich ky san pham {top_product} cho toi' },
        { id: 'segment', label: 'Phan khuc gia', prompt: 'Nhom san pham nay dang tap trung vao phan khuc gia nao?' },
        { id: 'action', label: 'Goi y hanh dong', prompt: 'De xuat 3 hanh dong toi uu de tang doanh thu cho tu khoa {keyword}' },
    ];

    useEffect(() => {
        lucide.createIcons();
    }, [result, chatMessages, searchHistory, isChatOpen, isSessionListOpen, reviewModal.open]);

    useEffect(() => {
        try {
            const raw = localStorage.getItem(SEARCH_HISTORY_KEY);
            const parsed = raw ? JSON.parse(raw) : [];
            if (Array.isArray(parsed)) setSearchHistory(parsed.slice(0, HISTORY_LIMIT));
        } catch (_) {
            setSearchHistory([]);
        }
    }, []);

    const saveSearchHistory = (value) => {
        const cleaned = (value || '').trim();
        if (!cleaned) return;
        setSearchHistory((prev) => {
            const next = [cleaned, ...prev.filter((item) => item.toLowerCase() !== cleaned.toLowerCase())].slice(0, HISTORY_LIMIT);
            localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(next));
            return next;
        });
    };

    const clearSearchHistory = () => {
        localStorage.removeItem(SEARCH_HISTORY_KEY);
        setSearchHistory([]);
    };

    const runSingleAnalysis = async (inputKeyword, contextId = null) => {
        const normalized = (inputKeyword || '').trim();
        if (!normalized) return;

        setLoading(true);
        setResult(null);
        setInsight('');
        setContextInfo(null);
        setAnalytics(null);
        try {
            const data = await executeAnalysis('single', { keyword: normalized, context_id: contextId });
            setKeyword(normalized);
            setResult(data.products);
            setInsight(data.insight);
            setContextInfo(data.context);
            setAnalytics(data.analytics);
            saveSearchHistory(normalized);
            return data;
        } catch (error) {
            setInsight(
                `❌ Lỗi kết nối Backend:\n${error.message}\n\nVui lòng kiểm tra:\n` +
                `1. Backend đã chạy chưa? (python main.py)\n` +
                `2. URL API đúng chưa? (${API_BASE_URL || 'CHUA_CAU_HINH'})\n` +
                `3. Nếu chạy trên GitHub Pages: API phải là public URL (Render/Railway/Fly.io), không dùng localhost\n` +
                `4. Nếu web là HTTPS thì API cũng phải HTTPS\n` +
                `5. CORS đã cấu hình chưa?`
            );
            throw error;
        } finally {
            setLoading(false);
            setTimeout(() => lucide.createIcons(), 100);
        }
    };

    const handleExecute = async () => {
        if (!keyword.trim()) return;
        await runSingleAnalysis(keyword, null);
    };

    const handleSelectContext = async (nextContextId) => {
        if (!keyword.trim()) return;
        try {
            await runSingleAnalysis(keyword, nextContextId);
        } catch (error) {
            setInsight(`❌ Lỗi phân tích lại: ${error.message}`);
        }
    };

    const summarizeForChat = (questionText) => {
        const q = (questionText || '').toLowerCase();
        if (!result || !analytics) {
            return 'Ban hay phan tich mot tu khoa truoc de toi co du lieu tra loi chi tiet.';
        }
        if (q.includes('gia')) {
            return `Gia trung binh hien tai la ${Number(analytics.avg_price || 0).toLocaleString('vi-VN')} VND.`;
        }
        if (q.includes('doanh thu')) {
            return `Tong doanh thu uoc tinh la ${Number(analytics.total_revenue || 0).toLocaleString('vi-VN')} VND.`;
        }
        if (q.includes('ban') || q.includes('so luong')) {
            return `Tong luong ban uoc tinh la ${Number(analytics.total_sold || 0).toLocaleString('vi-VN')} san pham.`;
        }
        if (q.includes('top') || q.includes('san pham')) {
            const top = result.slice(0, 3).map((p, i) => `${i + 1}. ${p.name}`).join(' | ');
            return `Top san pham hien tai: ${top}.`;
        }
        if (q.includes('tom tat') || q.includes('tong quan')) {
            return `Tom tat nhanh: ${Number(analytics.total_products || 0).toLocaleString('vi-VN')} san pham, rating TB ${Number(analytics.avg_rating || 0).toFixed(2)}, doanh thu ${Number(analytics.total_revenue || 0).toLocaleString('vi-VN')} VND.`;
        }
        return 'Toi co the tra loi nhanh ve gia, doanh thu, so luong ban, top san pham, hoac ban co the nhap mot tu khoa moi de toi phan tich.';
    };

    const resolveQuickPrompt = (template) => {
        const currentKeyword = (keyword || '').trim() || 'tu khoa hien tai';
        const topProduct = result && result[0] ? result[0].name : 'san pham top 1 hien tai';
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
                    session_id: activeSessionId,
                    context_id: contextInfo ? contextInfo.selected_context : null
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
        if (!result) return;
        const element = document.createElement('div');
        element.innerHTML = buildPdfHtml(result, insight, keyword, true);
        html2pdf().set({
            margin: 10,
            filename: `BaoCao_Single_${Date.now()}.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2 },
            jsPDF: { orientation: 'portrait', unit: 'mm', format: 'a4' }
        }).from(element).save();
    };

    const handleOpenReviews = async (product) => {
        setReviewModal({ open: true, product, reviews: [], loading: true, error: null });
        try {
            const pid = product.product_id || '';
            console.debug('[Reviews] Opening reviews for product:', product.name, '| product_id:', pid);
            if (!pid) {
                console.warn('[Reviews] product_id missing. Full product object:', product);
                throw new Error(`Không tìm thấy product_id cho sản phẩm "${product.name || 'N/A'}"`);
            }
            const res = await fetch(`${API_BASE_URL}/api/product-reviews/${pid}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const json = await res.json();
            setReviewModal({ open: true, product, reviews: json.data || [], loading: false, error: null });
        } catch (e) {
            setReviewModal(prev => ({ ...prev, loading: false, error: e.message }));
        }
    };

    return (
        <ErrorBoundary>
            <div>
                {/* INPUT SECTION */}
                <div className="max-w-4xl mx-auto mb-8">
                    <div className="glass-panel p-6 rounded-xl flex gap-4 items-end animate-fade-in">
                        <div className="flex-1">
                            <label className="block text-sm font-medium text-gray-700 mb-2">Nhập từ khóa sản phẩm</label>
                            <input
                                type="text"
                                value={keyword}
                                onChange={(e) => setKeyword(e.target.value)}
                                placeholder="Ví dụ: tai nghe bluetooth, chuột không dây, sách..."
                                className="w-full bg-white border border-gray-300 rounded-lg px-4 py-3 text-gray-900 focus:border-blue-500 focus:ring-1 focus:ring-blue-400 outline-none transition-all"
                                onKeyDown={(e) => e.key === 'Enter' && handleExecute()}
                            />
                        </div>
                        <button
                            onClick={handleExecute}
                            disabled={loading || !keyword}
                            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 disabled:cursor-not-allowed text-white font-bold rounded-lg flex items-center gap-2 transition-all shadow-lg shadow-blue-200"
                        >
                            {loading ? <Icon name="loader-2" className="animate-spin" /> : <Icon name="play" className="fill-current" />}
                            Phân tích
                        </button>
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-3 flex-wrap">
                        <div className="flex flex-wrap gap-2">
                            {searchHistory.map((item) => (
                                <button
                                    key={item}
                                    onClick={() => runSingleAnalysis(item, null)}
                                    className="px-3 py-1.5 rounded-full text-xs font-medium border border-gray-300 text-gray-800 hover:border-blue-500 hover:text-gray-900 transition-all"
                                >
                                    {item}
                                </button>
                            ))}
                        </div>
                        {searchHistory.length > 0 && (
                            <button
                                onClick={clearSearchHistory}
                                className="text-xs px-3 py-1.5 rounded-lg border border-red-500/40 text-red-600 hover:bg-red-500/20 transition-all"
                            >
                                Xoa lich su
                            </button>
                        )}
                    </div>
                </div>

                {/* LOADING */}
                {loading && (
                    <div className="flex flex-col items-center justify-center py-20 text-blue-500 animate-pulse">
                        <Icon name="bot" size={48} className="mb-4" />
                        <p className="text-lg font-medium">Đang gọi Backend API...</p>
                        <p className="text-sm text-gray-500">Vui lòng đợi</p>
                    </div>
                )}

                {/* EXPORT BUTTON */}
                {!loading && result && (
                    <div className="max-w-6xl mx-auto flex justify-end mb-2">
                        <button
                            onClick={handleExportPDF}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors shadow-lg shadow-blue-900/20"
                        >
                            <Icon name="download" size={16} /> Xuất PDF
                        </button>
                    </div>
                )}

                {/* RESULTS */}
                {!loading && result && renderResult(result, insight, analytics, handleOpenReviews)}

                {/* FLOATING CHATBOT */}
                <div className="fixed bottom-6 right-6 z-40">
                    <button
                        onClick={() => setIsChatOpen((prev) => !prev)}
                        className="w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-600 text-white shadow-xl shadow-blue-200/60 flex items-center justify-center border border-cyan-400/40"
                        title="Mo chatbot"
                    >
                        <Icon name={isChatOpen ? 'x' : 'message-circle'} size={24} />
                    </button>
                </div>

                {isChatOpen && (
                    <div className={`fixed bottom-24 right-3 left-3 sm:left-auto sm:right-6 z-40 transition-all duration-300 ${isSessionListOpen ? 'sm:w-[610px]' : 'sm:w-[410px]'}`}>
                        <div className="bg-white rounded-xl border border-blue-100 overflow-hidden shadow-2xl flex flex-row h-[500px]">
                            {/* Session List Panel on the Left */}
                            {isSessionListOpen && (
                                <div className="w-[200px] bg-blue-50 border-r border-blue-100 p-3 flex flex-col h-full text-[11px] text-gray-800 flex-shrink-0">
                                    <div className="flex justify-between items-center mb-2 flex-shrink-0">
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
                                    <div className="space-y-1 overflow-y-auto flex-1 pr-1">
                                        {sessions.map((s) => (
                                            <div 
                                                key={s.id}
                                                onClick={() => {
                                                    setActiveSessionId(s.id);
                                                    localStorage.setItem('tiki_chat_active_session_id', s.id);
                                                }}
                                                className={`p-2 rounded flex justify-between items-center cursor-pointer transition-colors ${
                                                    s.id === activeSessionId 
                                                        ? 'bg-blue-600 text-white font-semibold' 
                                                        : 'bg-white hover:bg-blue-100 text-gray-700 border border-gray-150'
                                                }`}
                                            >
                                                <span className="truncate max-w-[120px]" title={s.name}>{s.name}</span>
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

                            {/* Main Chat Box on the Right */}
                            <div className="flex-1 flex flex-col h-full min-w-0">
                                {/* Header */}
                                <div className="p-3 border-b border-blue-100 bg-blue-600 text-white flex items-center justify-between gap-2 flex-shrink-0">
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

                                {/* User Profile Bar (if capital is set) */}
                                {userProfile.capital && (
                                    <div className="px-3 py-1.5 bg-blue-50 border-b border-blue-100 text-[10px] text-blue-800 flex justify-between items-center font-medium flex-shrink-0">
                                        <span>💰 Vốn: {Number(userProfile.capital).toLocaleString('vi-VN')}đ</span>
                                        <span>📍 Khu vực: {userProfile.location}</span>
                                        {activeBusiness && <span className="truncate max-w-[120px]" title={activeBusiness}>🎯 Đang chọn: {activeBusiness}</span>}
                                    </div>
                                )}

                                {/* Shortcut Commands */}
                                <div className="p-2.5 border-b border-blue-100 bg-gray-50/50 flex-shrink-0">
                                    <p className="text-[10px] text-gray-500 mb-1">Gợi ý phân tích nhanh cho "{keyword || 'từ khóa'}":</p>
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
                                <div ref={chatContainerRef} className="overflow-y-auto p-3 space-y-3 bg-gray-50 flex-1">
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
                                    <div className="px-3 py-1.5 border-t border-blue-50 bg-blue-50/30 flex flex-wrap gap-1 flex-shrink-0">
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
                                <div className="p-2.5 border-t border-blue-100 flex items-center gap-1.5 bg-white flex-shrink-0">
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

                {/* CONTEXT SUGGESTIONS */}
                {!loading && result && contextInfo && (
                    <div className="max-w-6xl mx-auto mt-6">
                        <div className="bg-white rounded-xl border border-blue-100 p-5">
                            <div className="flex items-center justify-between gap-3 flex-wrap">
                                <h3 className="font-bold text-gray-900 flex items-center gap-2">
                                    <Icon name="sparkles" size={18} className="text-blue-500" /> Bạn có đang tìm kiếm...?
                                </h3>
                                {contextInfo.selected_context && (
                                    <span className="text-xs text-gray-500">
                                        Ngữ cảnh đang chọn: <span className="text-blue-700 font-semibold">{contextInfo.selected_context_label || contextInfo.selected_context}</span>
                                    </span>
                                )}
                            </div>
                            <div className="mt-4 flex flex-wrap gap-2">
                                <span className="px-3 py-1.5 rounded-full text-xs font-semibold border bg-blue-600 text-white border-blue-400">
                                    {contextInfo.selected_context_label || contextInfo.selected_context}
                                </span>
                                {contextInfo.suggestions && contextInfo.suggestions.map((s) => (
                                    <button
                                        key={s.context_id}
                                        onClick={() => handleSelectContext(s.context_id)}
                                        disabled={loading}
                                        className="px-3 py-1.5 rounded-full text-xs font-semibold border transition-all bg-white text-gray-800 border-gray-300 hover:border-blue-500 hover:text-blue-700"
                                        title={`${s.count} sản phẩm`}
                                    >
                                        {s.label} <span className="opacity-70">({s.count})</span>
                                    </button>
                                ))}
                            </div>
                            {contextInfo.total_found_before_filter !== undefined && (
                                <div className="mt-3 text-xs text-gray-500">
                                    Lọc theo ngữ cảnh: {contextInfo.total_found_after_filter?.toLocaleString?.('vi-VN') || contextInfo.total_found_after_filter} / {contextInfo.total_found_before_filter.toLocaleString('vi-VN')} sản phẩm
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* EMPTY STATE */}
                {!loading && !result && (
                    <div className="flex flex-col items-center justify-center h-64 text-gray-500 opacity-60">
                        <Icon name="bar-chart-2" size={64} className="mb-4" />
                        <p className="text-lg">Nhập từ khóa để bắt đầu</p>
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
        </ErrorBoundary>
    );
}




