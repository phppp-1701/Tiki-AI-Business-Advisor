# ============================================================
# AI BUSINESS ASSISTANT - Conversational Engine
# ============================================================

import logging
import time
import json
import re
from typing import Dict, List, Any, Optional
import google.generativeai as genai
import google.ai.generativelanguage as glm
from config import settings
from gemini_helper import gemini_manager

logger = logging.getLogger(__name__)

# Global reference for Gemini tools to access the active assistant instance
_assistant_instance: Optional['AIBusinessAssistant'] = None

# ============================================================
# 🛠️ GLOBAL STANDALONE FUNCTIONS (TOOLS FOR GEMINI)
# ============================================================

def recommend_business(capital: float, location: str = "TP.HCM", interest: Optional[str] = None, experience: Optional[str] = None) -> str:
    """
    Đề xuất danh sách các mô hình kinh doanh trên Tiki phù hợp nhất với điều kiện tài chính và sở thích.

    Args:
        capital: Số vốn đầu tư dự kiến (VND). Ví dụ: 100000000.
        location: Địa điểm kinh doanh (mặc định: "TP.HCM").
        interest: Lĩnh vực quan tâm hoặc từ khóa tìm kiếm (ví dụ: "fashion", "electronics", "houseware", "toy").
        experience: Mức độ kinh nghiệm của người dùng ("beginner", "intermediate", "expert").
    """
    if _assistant_instance:
        return _assistant_instance.recommend_business(capital, location, interest, experience)
    return json.dumps({"success": False, "message": "Hệ thống chưa sẵn sàng."})

def get_business_detail(business_name_or_id: str) -> str:
    """
    Lấy thông tin chi tiết của một sản phẩm/mô hình cụ thể trong hệ thống.

    Args:
        business_name_or_id: Tên sản phẩm hoặc ID sản phẩm cần tra cứu (ví dụ: "Tai nghe", "277544974").
    """
    if _assistant_instance:
        return _assistant_instance.get_business_detail(business_name_or_id)
    return json.dumps({"success": False, "message": "Hệ thống chưa sẵn sàng."})

def analyze_profit(business_name_or_id: str) -> str:
    """
    Phân tích tài chính, ước tính doanh thu và lợi nhuận hàng tháng, thời gian hoàn vốn cho một sản phẩm/ý tưởng.

    Args:
        business_name_or_id: Tên hoặc ID sản phẩm cần tính lợi nhuận.
    """
    if _assistant_instance:
        return _assistant_instance.analyze_profit(business_name_or_id)
    return json.dumps({"success": False, "message": "Hệ thống chưa sẵn sàng."})

def analyze_risk(business_name_or_id: str) -> str:
    """
    Phân tích rủi ro, đánh giá khách hàng (review sentiment), tỷ lệ tiêu cực và tìm ra các khoảng trống chất lượng của sản phẩm/ý tưởng.

    Args:
        business_name_or_id: Tên hoặc ID sản phẩm cần kiểm tra rủi ro.
    """
    if _assistant_instance:
        return _assistant_instance.analyze_risk(business_name_or_id)
    return json.dumps({"success": False, "message": "Hệ thống chưa sẵn sàng."})

def _analyze_market(keyword: str) -> str:
    # Compatibility redirect for direct testing
    if _assistant_instance:
        return _assistant_instance.analyze_market(keyword)
    return json.dumps({"success": False, "message": "Hệ thống chưa sẵn sàng."})

def analyze_market(keyword: str) -> str:
    """
    Phân tích tổng thể một ngách thị trường dựa trên từ khóa tìm kiếm (số lượng đối thủ cạnh tranh, tổng dung lượng thị trường, khoảng giá bán và mức độ khả thi).

    Args:
        keyword: Từ khóa ngách thị trường cần phân tích (ví dụ: 'tai nghe bluetooth', 'xe may').
    """
    if _assistant_instance:
        return _assistant_instance.analyze_market(keyword)
    return json.dumps({"success": False, "message": "Hệ thống chưa sẵn sàng."})

def compare_businesses(business_a: str, business_b: str) -> str:
    """
    So sánh chi tiết 2 ý tưởng/sản phẩm kinh doanh dựa trên các tiêu chí vốn đầu tư, lợi nhuận, rủi ro, và dung lượng thị trường.

    Args:
        business_a: Tên hoặc ID sản phẩm thứ nhất.
        business_b: Tên hoặc ID sản phẩm thứ hai.
    """
    if _assistant_instance:
        return _assistant_instance.compare_businesses(business_a, business_b)
    return json.dumps({"success": False, "message": "Hệ thống chưa sẵn sàng."})

def generate_roadmap(business_name_or_id: str) -> str:
    """
    Tạo lập một kế hoạch hành động triển khai chi tiết từng bước (roadmap) để bắt đầu kinh doanh sản phẩm đã chọn trên sàn Tiki.

    Args:
        business_name_or_id: Tên hoặc ID sản phẩm muốn tạo kế hoạch triển khai.
    """
    if _assistant_instance:
        return _assistant_instance.generate_roadmap(business_name_or_id)
    return json.dumps({"success": False, "message": "Hệ thống chưa sẵn sàng."})


# ============================================================
# 🧹 CHAT HISTORY PRUNING HELPER (TOKEN SAVINGS)
# ============================================================

def prune_chat_history(history, max_turns=3) -> List[Any]:
    """
    Prunes the chat history to keep only the last `max_turns` of conversation,
    and strips out all intermediate tool calls and tool responses, 
    keeping only the final text messages. Also strips out old system instruction
    and context headers to avoid duplication.
    """
    if not history:
        return []
        
    clean_history = []
    # Filter to keep only text-only messages or simplify them
    for content in history:
        text_parts = []
        for part in content.parts:
            # Check if it has text attribute and it's not empty
            if hasattr(part, 'text') and part.text:
                text = part.text
                # Strip out any [SYSTEM INSTRUCTION: ...] and [Bối cảnh hiện tại: ...] to prevent repetition in history
                text = re.sub(r'\[SYSTEM INSTRUCTION:.*?\]\n\n?', '', text, flags=re.DOTALL)
                text = re.sub(r'\[Bối cảnh hiện tại:.*?\]\n\n?', '', text, flags=re.DOTALL)
                if text.strip():
                    text_parts.append(text.strip())
        
        if text_parts:
            # Create a clean Content object with only text
            combined_text = "\n".join(text_parts)
            clean_history.append(
                genai.protos.Content(
                    role=content.role,
                    parts=[genai.protos.Part(text=combined_text)]
                )
            )
            
    # Merge consecutive messages of the same role to maintain strict alternation
    final_history = []
    expected_role = "user"
    for msg in clean_history:
        if msg.role == expected_role:
            final_history.append(msg)
            expected_role = "model" if expected_role == "user" else "user"
        else:
            if final_history:
                # Merge with the last message
                last_msg = final_history[-1]
                last_text = last_msg.parts[0].text
                new_text = msg.parts[0].text
                last_msg.parts[0].text = f"{last_text}\n{new_text}"
            else:
                # If first message is not 'user', change role to user to satisfy Gemini start_chat structure
                msg.role = "user"
                final_history.append(msg)
                expected_role = "model"
                
    # Limit to last N turns (1 turn = 1 user + 1 model message)
    limit = max_turns * 2
    if len(final_history) > limit:
        final_history = final_history[-limit:]
        # Ensure the first message in the truncated list is from 'user'
        if final_history[0].role != "user":
            final_history = final_history[1:]
            
    return final_history


# ============================================================
# 🤖 CLASS DEFINITION
# ============================================================

class AIBusinessAssistant:
    def __init__(self, search_engine):
        global _assistant_instance
        _assistant_instance = self
        self.search_engine = search_engine
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
        # Configure Gemini API
        logger.info("🤖 Initializing Gemini Manager...")
        
        # System instructions
        self.system_instruction = """
Bạn là một AI Business Assistant (Chuyên gia Tư vấn Kinh doanh Sắc sảo) tại sàn thương mại điện tử Tiki.
Nhiệm vụ của bạn là tư vấn, định hướng và hỗ trợ người dùng xây dựng mô hình kinh doanh trên Tiki bằng ngôn ngữ tự nhiên.

# QUY TẮC CỐT LÕI (TRUYỆN THỐNG BẮT BUỘC):
1. KHÔNG ĐƯỢC TỰ BỊA RA CÁC SỐ LIỆU KINH DOANH (Doanh thu, lợi nhuận, giá trung bình, số lượng bán, đánh giá).
2. MỌI THÔNG TIN VÀ CỤ THỂ KINH DOANH PHẢI ĐƯỢC TRUY XUẤT TỪ CÁC HÀM (TOOLS) ĐƯỢC CUNG CẤP.
3. Nếu người dùng hỏi các câu hỏi cần dữ liệu tính toán mà bạn chưa gọi hàm, bạn BẮT BUỘC phải gọi hàm tương ứng trước khi trả lời.
4. LUÔN LUÔN ưu tiên Function Calling khi nhận diện được ý định (Intent) liên quan đến:
   - Gợi ý ý tưởng/mô hình: `recommend_business`
   - Chi tiết sản phẩm: `get_business_detail`
   - Phân tích lợi nhuận: `analyze_profit`
   - Phân tích rủi ro/đánh giá: `analyze_risk`
   - Phân tích thị trường tổng quan: `analyze_market`
   - So sánh các mô hình: `compare_businesses`
   - Kế hoạch triển khai (Roadmap): `generate_roadmap`

# HÀNH VI HỘI THOẠI (CONVERSATIONAL GUIDELINES):
- CHỦ ĐỘNG THU THẬP THÔNG TIN: Nếu người dùng nói chung chung muốn kinh doanh ("tôi muốn kinh doanh", "tư vấn giúp tôi"), bạn KHÔNG ĐƯỢC tự đề xuất ngẫu nhiên. Hãy lịch sự hỏi họ để thu thập:
  1. Số vốn đầu tư dự kiến (VND) - đây là thông tin bắt buộc.
  2. Địa điểm (location) - mặc định là TP.HCM nếu họ không nói.
  3. Lĩnh vực quan tâm hoặc kinh nghiệm (nếu có).
- DẪN DẮT HỘI THOẠI: Kết thúc câu trả lời bằng các câu hỏi gợi mở hoặc đề xuất hành động tiếp theo rõ ràng (Ví dụ: "Bạn có muốn xem phân tích lợi nhuận chi tiết của ý tưởng Cafe mang đi không?", "Tôi có thể lập bảng so sánh Cafe và Trà sữa cho bạn").
- KHẢ NĂNG GHI NHỚ: Người dùng có thể dùng các từ thay thế ("mô hình đầu tiên", "cái đó", "nó"). Bạn phải dựa trên ngữ cảnh hội thoại đã lưu để liên kết chính xác sản phẩm đó và gọi hàm với tham số đúng.
- TÔNG GIỌNG: Chuyên nghiệp, nhã nhặn, sắc bén, phân tích như một cố vấn cấp cao, sử dụng tiếng Việt và emoji hợp lý. Trả lời bằng định dạng Markdown đẹp mắt, có bảng biểu khi so sánh.
"""
        
        # Schemas for tools
        recommend_business_fd = glm.FunctionDeclaration(
            name="recommend_business",
            description="Đề xuất danh sách các mô hình kinh doanh trên Tiki phù hợp nhất với điều kiện tài chính, địa điểm, sở thích và kinh nghiệm của người dùng.",
            parameters=glm.Schema(
                type=glm.Type.OBJECT,
                properties={
                    "capital": glm.Schema(type=glm.Type.NUMBER, description="Số vốn đầu tư dự kiến (VND), ví dụ: 100000000"),
                    "location": glm.Schema(type=glm.Type.STRING, description="Địa điểm kinh doanh (mặc định: 'TP.HCM')"),
                    "interest": glm.Schema(type=glm.Type.STRING, description="Lĩnh vực quan tâm hoặc từ khóa tìm kiếm (ví dụ: 'fashion', 'electronics')"),
                    "experience": glm.Schema(type=glm.Type.STRING, description="Mức độ kinh nghiệm của người dùng ('beginner', 'intermediate', 'expert')")
                },
                required=["capital"]
            )
        )
        
        get_business_detail_fd = glm.FunctionDeclaration(
            name="get_business_detail",
            description="Lấy thông tin chi tiết (tên, giá bán, lượt bán, doanh thu) của một sản phẩm/mô hình cụ thể trong cơ sở dữ liệu.",
            parameters=glm.Schema(
                type=glm.Type.OBJECT,
                properties={
                    "business_name_or_id": glm.Schema(type=glm.Type.STRING, description="Tên sản phẩm hoặc ID sản phẩm cần tra cứu (ví dụ: 'Tai nghe', '277544974')")
                },
                required=["business_name_or_id"]
            )
        )
        
        analyze_profit_fd = glm.FunctionDeclaration(
            name="analyze_profit",
            description="Phân tích tài chính, ước tính doanh thu và lợi nhuận hàng tháng, tính chi phí nhập hàng dự kiến và thời gian hoàn vốn cho sản phẩm/ý tưởng.",
            parameters=glm.Schema(
                type=glm.Type.OBJECT,
                properties={
                    "business_name_or_id": glm.Schema(type=glm.Type.STRING, description="Tên hoặc ID sản phẩm cần tính toán chi phí và lợi nhuận.")
                },
                required=["business_name_or_id"]
            )
        )
        
        analyze_risk_fd = glm.FunctionDeclaration(
            name="analyze_risk",
            description="Phân tích rủi ro, tỷ lệ đánh giá tiêu cực và phản hồi cụ thể của khách hàng (review sentiment) từ cơ sở dữ liệu cho sản phẩm/ý tưởng.",
            parameters=glm.Schema(
                type=glm.Type.OBJECT,
                properties={
                    "business_name_or_id": glm.Schema(type=glm.Type.STRING, description="Tên hoặc ID sản phẩm cần kiểm tra các phản hồi đánh giá tiêu cực.")
                },
                required=["business_name_or_id"]
            )
        )
        
        analyze_market_fd = glm.FunctionDeclaration(
            name="analyze_market",
            description="Phân tích tổng thể một ngách thị trường dựa trên từ khóa tìm kiếm (số lượng đối thủ cạnh tranh, tổng dung lượng thị trường, khoảng giá bán và mức độ khả thi).",
            parameters=glm.Schema(
                type=glm.Type.OBJECT,
                properties={
                    "keyword": glm.Schema(type=glm.Type.STRING, description="Từ khóa ngách thị trường cần phân tích (ví dụ: 'tai nghe bluetooth', 'xe may')")
                },
                required=["keyword"]
            )
        )
        
        compare_businesses_fd = glm.FunctionDeclaration(
            name="compare_businesses",
            description="So sánh chi tiết 2 ý tưởng/sản phẩm kinh doanh dựa trên các chỉ số vốn đầu tư, doanh thu, lợi nhuận dự kiến, thời gian hoàn vốn và rủi ro.",
            parameters=glm.Schema(
                type=glm.Type.OBJECT,
                properties={
                    "business_a": glm.Schema(type=glm.Type.STRING, description="Tên hoặc ID sản phẩm/ý tưởng kinh doanh thứ nhất"),
                    "business_b": glm.Schema(type=glm.Type.STRING, description="Tên hoặc ID sản phẩm/ý tưởng kinh doanh thứ hai")
                },
                required=["business_a", "business_b"]
            )
        )
        
        generate_roadmap_fd = glm.FunctionDeclaration(
            name="generate_roadmap",
            description="Tạo lập kế hoạch hành động từng bước cụ thể (roadmap) từ khâu tìm nguồn hàng, làm hình ảnh, đăng ký gian hàng và quảng cáo để bắt đầu bán sản phẩm đã chọn.",
            parameters=glm.Schema(
                type=glm.Type.OBJECT,
                properties={
                    "business_name_or_id": glm.Schema(type=glm.Type.STRING, description="Tên hoặc ID sản phẩm muốn lập kế hoạch triển khai.")
                },
                required=["business_name_or_id"]
            )
        )
        
        self.tool = glm.Tool(
            function_declarations=[
                recommend_business_fd,
                get_business_detail_fd,
                analyze_profit_fd,
                analyze_risk_fd,
                analyze_market_fd,
                compare_businesses_fd,
                generate_roadmap_fd
            ]
        )
        
        self.tools = [
            recommend_business,
            get_business_detail,
            analyze_profit,
            analyze_risk,
            analyze_market,
            compare_businesses,
            generate_roadmap
        ]
        
        # Initialize generative model
        self.model = gemini_manager.get_model(
            model_name="gemini-flash-latest",
            tools=[self.tool]
        )
        logger.info("✅ AI Business Assistant Ready!")

    # ============================================================
    # 🛠️ SERVICE IMPLEMENTATIONS
    # ============================================================

    def recommend_business(self, capital: float, location: str = "TP.HCM", interest: Optional[str] = None, experience: Optional[str] = None) -> str:
        try:
            logger.info(f"[Service: recommend_business] Capital: {capital}, Interest: {interest}")
            df = self.search_engine.data_loader.products_df
            if df is None or df.empty:
                return json.dumps({"success": False, "message": "Không tìm thấy dữ liệu sản phẩm trong hệ thống."})
            
            categories = df['category'].dropna().unique().tolist()
            
            matched_categories = []
            if interest:
                interest_norm = self.search_engine.data_loader._normalize_text(interest)
                for cat in categories:
                    if interest_norm in self.search_engine.data_loader._normalize_text(cat):
                        matched_categories.append(cat)
                
                if not matched_categories:
                    search_results = self.search_engine.data_loader.search_products(interest, limit=30)
                    if search_results:
                        matched_categories = list(set(p['categoryName'] for p in search_results))
            
            if not matched_categories:
                matched_categories = categories

            recommendations = []
            for cat in matched_categories:
                cat_products = df[df['category'] == cat]
                if cat_products.empty:
                    continue
                
                avg_price = float(cat_products['original_price'].mean())
                avg_qty_sold = float(cat_products['quantity_sold'].mean())
                initial_stock_cost = avg_price * 100
                
                if initial_stock_cost <= capital:
                    capital_score = 40
                else:
                    ratio = capital / initial_stock_cost
                    capital_score = max(5, int(40 * ratio))
                
                max_qty = float(df['quantity_sold'].max()) if not df.empty else 1000
                demand_ratio = min(avg_qty_sold / (max_qty * 0.1), 1.0)
                demand_score = int(35 * demand_ratio)
                
                if experience == "beginner":
                    exp_score = 25 if avg_price < 150000 else (15 if avg_price < 500000 else 5)
                elif experience == "expert":
                    exp_score = 25 if avg_price > 500000 else 15
                else:
                    exp_score = 25 if 100000 <= avg_price <= 600000 else 18
                
                total_score = capital_score + demand_score + exp_score
                
                top3_df = cat_products.nlargest(3, 'quantity_sold')
                examples = []
                for _, r in top3_df.iterrows():
                    examples.append({
                        "product_id": str(r['product_id']),
                        "name": r['name'],
                        "price": float(r['original_price']),
                        "sold": int(r['quantity_sold'])
                    })
                
                monthly_rev = avg_price * avg_qty_sold * 0.5
                monthly_profit = monthly_rev * 0.25
                payback_months = round(initial_stock_cost / monthly_profit, 1) if monthly_profit > 0 else 6.0
                payback_months = min(max(payback_months, 1.5), 12.0)
                
                recommendations.append({
                    "category": cat,
                    "matching_score": total_score,
                    "average_price": round(avg_price, 0),
                    "estimated_initial_stock_cost": round(initial_stock_cost, 0),
                    "examples": examples,
                    "payback_time_months": payback_months,
                    "demand_level": "Rất cao 🔥" if avg_qty_sold > 500 else ("Cao 📈" if avg_qty_sold > 150 else "Trung bình 📊")
                })
            
            recommendations = sorted(recommendations, key=lambda x: x['matching_score'], reverse=True)[:3]
            
            return json.dumps({
                "success": True,
                "capital": capital,
                "location": location,
                "recommendations": recommendations
            }, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Error in recommend_business: {e}")
            return json.dumps({"success": False, "message": str(e)})

    def get_business_detail(self, business_name_or_id: str) -> str:
        try:
            logger.info(f"[Service: get_business_detail] Query: {business_name_or_id}")
            df = self.search_engine.data_loader.products_df
            if df is None or df.empty:
                return json.dumps({"success": False, "message": "Dữ liệu trống."})

            product = None
            if business_name_or_id.isdigit():
                pid = int(business_name_or_id)
                product = self.search_engine.data_loader.get_product_by_id(pid)
            
            if not product or not product.get("product_id"):
                results = self.search_engine.data_loader.search_products(business_name_or_id, limit=1)
                if results:
                    product = results[0]
            
            if not product or not product.get("product_id"):
                return json.dumps({"success": False, "message": f"Không tìm thấy sản phẩm nào phù hợp với '{business_name_or_id}'"})
            
            return json.dumps({"success": True, "product": product}, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error in get_business_detail: {e}")
            return json.dumps({"success": False, "message": str(e)})

    def analyze_profit(self, business_name_or_id: str) -> str:
        try:
            logger.info(f"[Service: analyze_profit] Query: {business_name_or_id}")
            detail_res = json.loads(self.get_business_detail(business_name_or_id))
            if not detail_res.get("success"):
                return json.dumps(detail_res)
            
            p = detail_res["product"]
            price = p["price"]
            sold = p["boughtInLastMonth"]
            revenue = p["estimated_revenue"]
            cat = p["categoryName"]
            
            margin = 0.25
            cat_lower = cat.lower()
            if "thoi trang" in cat_lower or "my pham" in cat_lower:
                margin = 0.45
            elif "dien thoai" in cat_lower or "thiet bi" in cat_lower or "laptop" in cat_lower:
                margin = 0.12
            elif "do gia dung" in cat_lower or "the thao" in cat_lower or "o to" in cat_lower:
                margin = 0.28
            
            profit = revenue * margin
            initial_stock = 100
            inventory_cost = price * initial_stock
            marketing_cost = max(2000000.0, inventory_cost * 0.15)
            other_setup_costs = max(3000000.0, inventory_cost * 0.2)
            
            total_initial_investment = inventory_cost + marketing_cost + other_setup_costs
            payback_months = round(total_initial_investment / profit, 1) if profit > 0 else 6.0
            payback_months = min(max(payback_months, 1.0), 18.0)
            
            analysis = {
                "product_name": p["title"],
                "product_id": p["product_id"],
                "category": cat,
                "monthly_sold_units": sold,
                "average_price": price,
                "monthly_revenue": revenue,
                "profit_margin_pct": round(margin * 100, 1),
                "estimated_monthly_profit": round(profit, 0),
                "breakdown": {
                    "inventory_cost_100_units": round(inventory_cost, 0),
                    "marketing_cost": round(marketing_cost, 0),
                    "other_setup_costs": round(other_setup_costs, 0),
                    "total_initial_investment": round(total_initial_investment, 0)
                },
                "estimated_payback_months": payback_months
            }
            
            return json.dumps({"success": True, "analysis": analysis}, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error in analyze_profit: {e}")
            return json.dumps({"success": False, "message": str(e)})

    def analyze_risk(self, business_name_or_id: str) -> str:
        try:
            logger.info(f"[Service: analyze_risk] Query: {business_name_or_id}")
            detail_res = json.loads(self.get_business_detail(business_name_or_id))
            if not detail_res.get("success"):
                return json.dumps(detail_res)
            
            p = detail_res["product"]
            pid = int(float(p["product_id"]))
            
            rv_df = self.search_engine.data_loader.reviews_df
            product_reviews = rv_df[rv_df["product_id"] == pid] if rv_df is not None and not rv_df.empty else None
            total_reviews = len(product_reviews) if product_reviews is not None else 0
            
            sentiment_stats = {"positive": 0, "neutral": 0, "negative": 0}
            negative_examples = []
            positive_examples = []
            
            if total_reviews > 0:
                pos = int((product_reviews["sentiment_label"] == "positive").sum())
                neg = int((product_reviews["sentiment_label"] == "negative").sum())
                neu = total_reviews - pos - neg
                
                sentiment_stats = {
                    "positive": pos,
                    "neutral": neu,
                    "negative": neg,
                    "pos_pct": round(pos / total_reviews * 100, 1),
                    "neu_pct": round(neu / total_reviews * 100, 1),
                    "neg_pct": round(neg / total_reviews * 100, 1)
                }
                
                neg_reviews = product_reviews[product_reviews["sentiment_label"] == "negative"].head(3)
                for _, r in neg_reviews.iterrows():
                    content = r.get("original_content", r.get("cleaned_content", ""))
                    if content and len(str(content).strip()) > 3:
                        negative_examples.append(str(content))
                        
                pos_reviews = product_reviews[product_reviews["sentiment_label"] == "positive"].head(2)
                for _, r in pos_reviews.iterrows():
                    content = r.get("original_content", r.get("cleaned_content", ""))
                    if content and len(str(content).strip()) > 3:
                        positive_examples.append(str(content))
            else:
                rating = p["rating"]
                if rating >= 4.5:
                    sentiment_stats = {"positive": 90, "neutral": 8, "negative": 2, "pos_pct": 90.0, "neu_pct": 8.0, "neg_pct": 2.0, "total": 0}
                elif rating >= 4.0:
                    sentiment_stats = {"positive": 75, "neutral": 15, "negative": 10, "pos_pct": 75.0, "neu_pct": 15.0, "neg_pct": 10.0, "total": 0}
                else:
                    sentiment_stats = {"positive": 50, "neutral": 20, "negative": 30, "pos_pct": 50.0, "neu_pct": 20.0, "neg_pct": 30.0, "total": 0}
            
            rating = p["rating"]
            competition_risk = "Cao (Lượng đối thủ lớn)" if p["boughtInLastMonth"] > 300 else "Trung bình (Thị trường ngách)"
            quality_risk = "Thấp" if rating >= 4.5 else ("Trung bình (Có khiếu nại về chất lượng)" if rating >= 4.0 else "Cao (Rating kém, tỷ lệ trả hàng cao)")
            
            risk_analysis = {
                "product_name": p["title"],
                "product_id": p["product_id"],
                "rating": rating,
                "total_reviews_analyzed": total_reviews,
                "sentiment_distribution": sentiment_stats,
                "customer_complaints": negative_examples,
                "customer_praises": positive_examples,
                "risk_profile": {
                    "competition_risk_level": competition_risk,
                    "product_quality_risk_level": quality_risk,
                    "return_rate_estimate": "Dưới 2%" if rating >= 4.5 else ("2% - 5%" if rating >= 4.0 else "Trên 8%")
                }
            }
            
            return json.dumps({"success": True, "risk_analysis": risk_analysis}, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error in analyze_risk: {e}")
            return json.dumps({"success": False, "message": str(e)})

    def _analyze_market(self, keyword: str) -> str:
        # Compatibility redirect for direct testing
        return self.analyze_market(keyword)

    def analyze_market(self, keyword: str, context_id: Optional[str] = None) -> str:
        try:
            logger.info(f"[Service: analyze_market] Keyword: {keyword}, Context: {context_id}")
            products = self.search_engine.search_products(keyword, limit=9999, use_semantic=False)
            
            fallback_kw = None
            if not products:
                from search_engine.normalizer import normalize
                from search_engine.synonym_map import detect_compound
                compound = detect_compound(normalize(keyword))
                if compound and "matched_phrase" in compound:
                    fallback_kw = compound["matched_phrase"]
                    logger.info(f"[Service: analyze_market] 0 results for '{keyword}', falling back to matched phrase: '{fallback_kw}'")
                    products = self.search_engine.search_products(keyword=fallback_kw, limit=9999, use_semantic=False)
                    
            if not products:
                return json.dumps({"success": False, "message": f"Không có dữ liệu thị trường cho từ khóa '{keyword}'"})
            
            # Apply context filtering to match the search UI behavior
            ctx = self.search_engine.analyze_contexts(keyword=keyword, products=products, selected_context=context_id)
            filtered_products = ctx.get("filtered_products", [])
            
            # Fallback to all products if context filtering returns empty list
            if not filtered_products:
                filtered_products = products
                
            products = filtered_products
            
            avg_price = sum(p["price"] for p in products) / len(products) if products else 0
            avg_rating = sum(p["rating"] for p in products) / len(products) if products else 0
            total_sold = sum(p["boughtInLastMonth"] for p in products) if products else 0
            total_revenue = sum(p.get("estimated_revenue", p["price"] * p["boughtInLastMonth"]) for p in products) if products else 0
            max_price = max(p["price"] for p in products) if products else 0
            min_price = min(p["price"] for p in products) if products else 0
            
            budget_count = len([p for p in products if p["price"] < avg_price * 0.7]) if products else 0
            mid_count = len([p for p in products if avg_price * 0.7 <= p["price"] <= avg_price * 1.3]) if products else 0
            premium_count = len([p for p in products if p["price"] > avg_price * 1.3]) if products else 0
            
            market = {
                "keyword": keyword,
                "total_competitor_listings": len(products),
                "total_monthly_sales_volume": total_sold,
                "estimated_monthly_market_size_revenue": round(total_revenue, 0),
                "average_price": round(avg_price, 0),
                "price_range": {
                    "min": min_price,
                    "max": max_price
                },
                "average_rating": round(avg_rating, 2),
                "price_segments": {
                    "budget_pct": round(budget_count / len(products) * 100, 1) if products else 0.0,
                    "mid_pct": round(mid_count / len(products) * 100, 1) if products else 0.0,
                    "premium_pct": round(premium_count / len(products) * 100, 1) if products else 0.0
                },
                "market_feasibility_score": 90 if avg_rating < 4.2 and total_sold > 500 else (75 if total_sold > 100 else 55)
            }
            
            return json.dumps({"success": True, "market": market}, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error in analyze_market: {e}")
            return json.dumps({"success": False, "message": str(e)})

    def compare_businesses(self, business_a: str, business_b: str) -> str:
        try:
            logger.info(f"[Service: compare_businesses] Comparing '{business_a}' and '{business_b}'")
            res_a = json.loads(self.analyze_profit(business_a))
            res_b = json.loads(self.analyze_profit(business_b))
            
            risk_a = json.loads(self.analyze_risk(business_a))
            risk_b = json.loads(self.analyze_risk(business_b))
            
            if not res_a.get("success"):
                return json.dumps({"success": False, "message": f"Không phân tích được sản phẩm A: {res_a.get('message')}"})
            if not res_b.get("success"):
                return json.dumps({"success": False, "message": f"Không phân tích được sản phẩm B: {res_b.get('message')}"})
            
            pa = res_a["analysis"]
            pb = res_b["analysis"]
            
            ra = risk_a.get("risk_analysis", {})
            rb = risk_b.get("risk_analysis", {})
            
            comparison = {
                "item_a": {
                    "name": pa["product_name"],
                    "category": pa["category"],
                    "average_price": pa["average_price"],
                    "initial_investment": pa["breakdown"]["total_initial_investment"],
                    "monthly_sales": pa["monthly_sold_units"],
                    "monthly_revenue": pa["monthly_revenue"],
                    "estimated_profit": pa["estimated_monthly_profit"],
                    "payback_months": pa["estimated_payback_months"],
                    "satisfaction_rating": ra.get("rating", 4.5),
                    "risk_level": ra.get("risk_profile", {}).get("product_quality_risk_level", "Thấp")
                },
                "item_b": {
                    "name": pb["product_name"],
                    "category": pb["category"],
                    "average_price": pb["average_price"],
                    "initial_investment": pb["breakdown"]["total_initial_investment"],
                    "monthly_sales": pb["monthly_sold_units"],
                    "monthly_revenue": pb["monthly_revenue"],
                    "estimated_profit": pb["estimated_monthly_profit"],
                    "payback_months": pb["estimated_payback_months"],
                    "satisfaction_rating": rb.get("rating", 4.5),
                    "risk_level": rb.get("risk_profile", {}).get("product_quality_risk_level", "Thấp")
                }
            }
            
            return json.dumps({"success": True, "comparison": comparison}, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error in compare_businesses: {e}")
            return json.dumps({"success": False, "message": str(e)})

    def generate_roadmap(self, business_name_or_id: str) -> str:
        try:
            logger.info(f"[Service: generate_roadmap] Roadmap for {business_name_or_id}")
            detail_res = json.loads(self.get_business_detail(business_name_or_id))
            if not detail_res.get("success"):
                return json.dumps(detail_res)
            
            p = detail_res["product"]
            cat = p["categoryName"]
            name = p["title"]
            
            cat_lower = cat.lower()
            if "thoi trang" in cat_lower:
                steps = [
                    {"step": 1, "title": "Khảo sát & Chọn nguồn hàng", "description": "Tìm kiếm nguồn xưởng may/đại lý sỉ quần áo nam/nữ có giá sỉ tối ưu và có chính sách đổi trả tốt. Đặt mẫu thử chất lượng vải."},
                    {"step": 2, "title": "Chụp ảnh sản phẩm & Thiết kế Mockup", "description": "Thời trang cần hình ảnh visual cực tốt. Thuê mẫu ảnh hoặc tự setup studio mini chụp ảnh thật của sản phẩm. Thiết kế bảng size chi tiết."},
                    {"step": 3, "title": "Mở gian hàng & Đăng tải tối ưu SEO", "description": "Đăng ký tài khoản nhà bán hàng Tiki. Viết tên sản phẩm chứa từ khóa ('Váy lụa', 'Quần đũi Nữ') kèm mô tả chi tiết chất liệu, bảng size."},
                    {"step": 4, "title": "Gói hàng & Kiểm soát chất lượng", "description": "Chuẩn bị hộp carton cứng cáp và túi bọc nilon bảo vệ sản phẩm chống thấm nước khi vận chuyển. Đóng gói chỉn chu, thêm thư cảm ơn."},
                    {"step": 5, "title": "Chạy Ads nội sàn & Tăng đánh giá tích cực", "description": "Kích hoạt chiến dịch Tiki Ads cho từ khóa liên quan. Nhờ bạn bè hoặc khách hàng cũ mua và để lại review 5 sao có kèm hình ảnh thực tế."}
                ]
            elif "dien thoai" in cat_lower or "thiet bi" in cat_lower or "electronics" in cat_lower:
                steps = [
                    {"step": 1, "title": "Liên hệ nhà phân phối chính hãng & Kiểm tra giấy tờ CO/CQ", "description": "Lĩnh vực điện tử yêu cầu xuất xứ rõ ràng. Làm việc với hãng/nhà bán buôn lớn để có giấy chứng nhận phân phối và hóa đơn GTGT."},
                    {"step": 2, "title": "Setup chính sách bảo hành & Đổi trả", "description": "Xây dựng quy trình xử lý lỗi kỹ thuật của sản phẩm. Đảm bảo hỗ trợ đổi mới trong 7 ngày đầu tiên và bảo hành 6-12 tháng rõ ràng trên trang mô tả sản phẩm."},
                    {"step": 3, "title": "Hoàn thiện hồ sơ pháp lý & Đăng ký Tiki Official Store", "description": "Gửi các giấy chứng nhận ủy quyền thương hiệu, giấy phép kinh doanh để được gắn tag chính hãng trên Tiki nhằm tăng tỷ lệ tin cậy của khách."},
                    {"step": 4, "title": "Tối ưu hóa kho bãi & Bảo quản sản phẩm", "description": "Thiết bị điện tử nhạy cảm với độ ẩm. Lưu giữ hàng hóa trong môi trường kho thoáng, chống bụi bẩn và chống sốc vật lý tuyệt đối."},
                    {"step": 5, "title": "Khởi chạy phễu marketing đa kênh & Chăm sóc khách hàng sau mua", "description": "Xây dựng video review sản phẩm trên TikTok/Youtube trỏ link về Tiki. Chăm sóc tận tình qua chatbot của shop khi khách gặp khó khăn lắp đặt."}
                ]
            else:
                steps = [
                    {"step": 1, "title": "Nghiên cứu thị trường & Tìm nguồn sỉ", "description": f"Tìm kiếm nguồn hàng đại lý sỉ cho danh mục {cat} với giá chiết khấu tốt (mục tiêu giá gốc bằng 50-60% giá bán Tiki)."},
                    {"step": 2, "title": "Đánh giá chất lượng hàng mẫu", "description": f"Nhập số lượng nhỏ 5-10 sản phẩm để kiểm thử chất lượng sử dụng, độ bền thực tế và bao bì đóng gói của nhà sản xuất."},
                    {"step": 3, "title": "Tạo gian hàng Tiki & Viết nội dung chuẩn SEO", "description": f"Mở gian hàng nhà bán hàng. Đăng tải sản phẩm '{name}' với đầy đủ thuộc tính, từ khóa SEO và hình ảnh chuẩn studio."},
                    {"step": 4, "title": "Chuẩn bị quy trình vận hành & Đóng gói", "description": "Chuẩn bị đầy đủ hộp đóng gói, xốp bong bóng khí để bọc chống vỡ hỏng khi giao nhận qua đối tác vận chuyển của Tiki."},
                    {"step": 5, "title": "Marketing khởi động & Chạy Tiki Ads", "description": "Tối ưu hóa lượt bán ban đầu bằng các chương trình khuyến mãi mua kèm deal sốc và quảng cáo từ khóa Tiki Ads để tiếp cận khách hàng tiềm năng."}
                ]
                
            roadmap = {
                "product_name": name,
                "category": cat,
                "steps": steps
            }
            return json.dumps({"success": True, "roadmap": roadmap}, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error in generate_roadmap: {e}")
            return json.dumps({"success": False, "message": str(e)})

    def _send_chat_message_with_retry(self, chat, message_or_content):
        """
        Sends a message to the Gemini chat session with automatic key rotation,
        model recreation, and chat reconstruction from history if rate limits are hit.
        Returns (response, active_chat, using_groq)
        """
        max_attempts = max(8, len(gemini_manager.api_keys) * len(gemini_manager.models) * 2)
        delay = 2.0
        active_chat = chat
        
        for attempt in range(max_attempts):
            try:
                # Ensure the current active key is globally configured
                gemini_manager.configure_current_key()
                response = active_chat.send_message(message_or_content)
                return response, active_chat, False
            except Exception as e:
                err_str = str(e)
                err_type = type(e).__name__
                is_rate_limit = (
                    "429" in err_str or 
                    "quota" in err_str.lower() or 
                    "ResourceExhausted" in err_type or 
                    "ResourceExhausted" in err_str
                )
                
                logger.warning(f"⚠️ Chat API send_message failed (attempt {attempt + 1}/{max_attempts}): [{err_type}] {e}")
                
                if True:
                    logger.info("🔄 Chat message rate limited or quota exceeded. Rotating API key or model...")
                    if gemini_manager.rotate_key_or_model():
                        # Key or Model rotated. Recreate the model using current active model in rotation
                        self.model = gemini_manager.get_model(
                            model_name="gemini-flash-latest",
                            tools=[self.tool]
                        )
                        # Re-hydrate the chat from the previous chat's history
                        chat_history = list(active_chat.history)
                        active_chat = self.model.start_chat(history=chat_history)
                        logger.info("✅ Gemini model and chat session reconstructed. Retrying...")
                        continue
                    else:
                        logger.warning("⚠️ Key or model rotation failed.")
                            
                if attempt == max_attempts - 1:
                    raise e
                        
                logger.info(f"⏳ Sleeping for {delay:.1f}s before retrying chat message...")
                time.sleep(delay)
                delay = min(delay * 2, 15.0)

    def _groq_send_with_tools(self, groq_mgr, history, user_message):
        """
        Send a message via Groq and handle the full function-calling loop locally.
        Returns the final text response string.
        """
        response = groq_mgr.send_chat_message(
            system_instruction=self.system_instruction,
            gemini_history=history,
            new_message=user_message
        )
        
        loop_limit = 5
        loop_count = 0
        
        while response.candidates and response.candidates[0].content.parts and loop_count < loop_limit:
            function_calls = [
                part.function_call for part in response.candidates[0].content.parts 
                if part.function_call and part.function_call.name
            ]
            
            if not function_calls:
                break
            
            loop_count += 1
            logger.info(f"[Groq Fallback] Loop {loop_count}: Groq requested {len(function_calls)} function call(s)")
            
            tool_results_text = []
            for call in function_calls:
                func_name = call.name
                args = dict(call.args) if hasattr(call.args, '__iter__') and not isinstance(call.args, str) else {}
                logger.info(f"   [Groq] Executing Tool: {func_name} with args: {args}")
                
                tool_result = self._execute_tool(func_name, args)
                tool_results_text.append(f"Tool '{func_name}' returned: {tool_result}")
            
            # Send all tool results back to Groq as a combined message
            combined_results = "\n\n".join(tool_results_text)
            follow_up = f"Here are the results from the tools you requested:\n\n{combined_results}\n\nPlease analyze these results and provide a comprehensive response to the user in Vietnamese."
            
            response = groq_mgr.send_chat_message(
                system_instruction=self.system_instruction,
                gemini_history=history,
                new_message=follow_up
            )
        
        return response.text if hasattr(response, 'text') and response.text else ""

    def _execute_tool(self, func_name, args, session=None):
        """Execute a tool function by name and return the JSON result string."""
        try:
            if func_name == "recommend_business":
                capital_val = args.get("capital")
                if capital_val:
                    if isinstance(capital_val, str):
                        digits = re.findall(r'\d+', capital_val)
                        if digits:
                            num = float("".join(digits))
                            if "triệu" in capital_val or "m" in capital_val.lower():
                                num *= 1000000
                            capital_val = num
                        else:
                            capital_val = 100000000.0
                    else:
                        capital_val = float(capital_val)
                else:
                    capital_val = 100000000.0
                return self.recommend_business(
                    capital=capital_val,
                    location=args.get("location", "TP.HCM"),
                    interest=args.get("interest"),
                    experience=args.get("experience")
                )
            elif func_name == "get_business_detail":
                return self.get_business_detail(business_name_or_id=args.get("business_name_or_id", ""))
            elif func_name == "analyze_profit":
                return self.analyze_profit(business_name_or_id=args.get("business_name_or_id", ""))
            elif func_name == "analyze_risk":
                return self.analyze_risk(business_name_or_id=args.get("business_name_or_id", ""))
            elif func_name == "analyze_market":
                context_id = session.get("context_id") if session else None
                return self.analyze_market(keyword=args.get("keyword", ""), context_id=context_id)
            elif func_name == "compare_businesses":
                return self.compare_businesses(business_a=args.get("business_a", ""), business_b=args.get("business_b", ""))
            elif func_name == "generate_roadmap":
                return self.generate_roadmap(business_name_or_id=args.get("business_name_or_id", ""))
            else:
                return json.dumps({"success": False, "message": f"Hàm {func_name} không khả dụng."})
        except Exception as e:
            logger.error(f"Error executing tool {func_name}: {e}")
            return json.dumps({"success": False, "message": str(e)})

    # ============================================================
    # 💬 CORE CHAT LOGIC (DISPATCHER & MULTI-TURN CONTROL)
    # ============================================================

    def _get_chat_provider(self):
        """
        Determine which AI provider to use for chat.
        Always use Gemini.
        """
        logger.info("🔵 Using Gemini as primary chat provider")
        return "gemini", None

    def chat(self, session_id: str, message: str, context_id: Optional[str] = None) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],
                "profile": {
                    "capital": None,
                    "location": "TP.HCM",
                    "interest": None,
                    "experience": None
                },
                "active_business": None,
                "raw_messages": []
            }
            
        session = self.sessions[session_id]
        if context_id is not None:
            session["context_id"] = context_id
            
        session["raw_messages"].append({"role": "user", "text": message})
        
        try:
            modified_message = message
            active_business = session.get("active_business")
            
            if active_business:
                lower_msg = message.lower()
                if any(kw in lower_msg for kw in ["cái đó", "cái này", "đó", "nó", "mô hình này", "mô hình đầu", "đầu tiên", "thứ nhất", "thứ 1", "ở trên"]):
                    modified_message += f"\n(Context Hint: The active business currently discussed is '{active_business}'. Call functions with '{active_business}' if applicable.)"
            
            provider, groq_mgr = self._get_chat_provider()
            
            if provider == "groq":
                return self._chat_via_groq(groq_mgr, session, session_id, modified_message)
            else:
                return self._chat_via_gemini(session, session_id, modified_message)
            
        except Exception as e:
            logger.error(f"Error in chat assistant logic: {e}", exc_info=True)
            return {
                "success": False,
                "response": f"❌ Trợ lý AI đang gặp sự cố kết nối: {e}. Vui lòng thử lại sau.",
                "session_id": session_id,
                "profile": session.get("profile", {}),
                "active_business": session.get("active_business")
            }

    # ============================================================
    # 🟢 GROQ CHAT PATH (PRIMARY - Llama-3 70B via Groq)
    # ============================================================

    def _chat_via_groq(self, groq_mgr, session, session_id, message):
        """Handle the entire chat conversation via Groq API (Llama-3)."""
        logger.info(f"[Groq Chat] Sending message: {message[:100]}...")
        
        # Build history from raw messages for Groq
        groq_history = []
        for msg in session.get("raw_messages", [])[:-1]:  # Exclude the current message (already appended)
            role = msg["role"]
            text = msg.get("text", "")
            if text:
                groq_history.append({"role": role, "content": text})
        
        # Build the messages array for Groq
        messages = []
        messages.append({"role": "system", "content": self.system_instruction})
        messages.extend(groq_history)
        messages.append({"role": "user", "content": message})
        
        # Send to Groq with tools
        response = groq_mgr.send_chat_message(
            system_instruction=self.system_instruction,
            gemini_history=[],  # We pass raw history via messages above
            new_message=message
        )
        
        # Handle function calling loop
        loop_limit = 5
        loop_count = 0
        
        while response.candidates and response.candidates[0].content.parts and loop_count < loop_limit:
            function_calls = [
                part.function_call for part in response.candidates[0].content.parts 
                if part.function_call and part.function_call.name
            ]
            
            if not function_calls:
                break
            
            loop_count += 1
            logger.info(f"[Groq Chat] Loop {loop_count}: Processing {len(function_calls)} function call(s)")
            
            tool_results_text = []
            for call in function_calls:
                func_name = call.name
                args = dict(call.args) if hasattr(call.args, '__iter__') and not isinstance(call.args, str) else {}
                logger.info(f"   [Groq] Executing Tool: {func_name} with args: {args}")
                
                # Update session context
                self._update_session_context(session, func_name, args)
                
                tool_result = self._execute_tool(func_name, args, session)
                tool_results_text.append(f"[Tool: {func_name}]\n{tool_result}")
                
                # Update active business from recommend results
                if func_name == "recommend_business":
                    try:
                        res_json = json.loads(tool_result)
                        if res_json.get("success") and res_json.get("recommendations"):
                            session["active_business"] = res_json["recommendations"][0]["category"]
                    except Exception:
                        pass
            
            # Send tool results back to Groq
            combined = "\n\n".join(tool_results_text)
            follow_up = f"Đây là kết quả từ các công cụ phân tích:\n\n{combined}\n\nHãy phân tích kết quả trên và trả lời chi tiết cho người dùng bằng tiếng Việt, sử dụng Markdown đẹp mắt với bảng biểu khi cần."
            
            response = groq_mgr.send_chat_message(
                system_instruction=self.system_instruction,
                gemini_history=[],
                new_message=follow_up
            )
        
        # Extract final text
        final_text = ""
        if hasattr(response, 'text') and response.text:
            final_text = response.text
        elif response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    final_text += part.text
        
        session["raw_messages"].append({"role": "assistant", "text": final_text})
        
        return {
            "success": True,
            "response": final_text,
            "session_id": session_id,
            "profile": session["profile"],
            "active_business": session["active_business"]
        }

    # ============================================================
    # 🔵 GEMINI CHAT PATH (FALLBACK)
    # ============================================================

    def _chat_via_gemini(self, session, session_id, message):
        """Handle chat via Gemini API (original path, used when Groq is unavailable)."""
        modified_message = message
        
        # 1. Prune history to remove heavy function outputs and keep only last 3 turns of text
        chat_history = prune_chat_history(session.get("history", []), max_turns=3)
        
        # 2. Inject profile and active business context hints
        profile = session.get("profile", {})
        active_business = session.get("active_business")
        
        context_hints = []
        if profile.get("capital"):
            context_hints.append(f"Vốn: {profile['capital']:,} VND")
        if profile.get("location"):
            context_hints.append(f"Địa điểm: {profile['location']}")
        if profile.get("interest"):
            context_hints.append(f"Quan tâm: {profile['interest']}")
        if profile.get("experience"):
            context_hints.append(f"Kinh nghiệm: {profile['experience']}")
        if active_business:
            context_hints.append(f"Sản phẩm đang quan tâm: {active_business}")
            
        context_str = ""
        if context_hints:
            context_str = f"[Bối cảnh hiện tại: {', '.join(context_hints)}]\n"

        # 3. Prepend system instruction to the oldest user message in the history if history exists.
        # Otherwise, prepend to the current message.
        if chat_history:
            # Find the first user message in the pruned history
            for msg in chat_history:
                if msg.role == "user" and msg.parts:
                    old_text = msg.parts[0].text
                    msg.parts[0].text = f"[SYSTEM INSTRUCTION: {self.system_instruction}]\n\n{old_text}"
                    break
            # Just prepend current context to current user message
            modified_message = context_str + modified_message
        else:
            # Prepend both system instruction and current context to current user message
            modified_message = f"[SYSTEM INSTRUCTION: {self.system_instruction}]\n\n{context_str}{modified_message}"

        chat = self.model.start_chat(history=chat_history)
        
        logger.info(f"[Gemini Chat] Sending message: {modified_message[:100]}...")
        
        # Simple send with retry
        max_attempts = max(8, len(gemini_manager.api_keys) * len(gemini_manager.models) * 2)
        delay = 2.0
        response = None
        
        for attempt in range(max_attempts):
            try:
                gemini_manager.configure_current_key()
                response = chat.send_message(modified_message)
                break
            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "quota" in err_str.lower() or "ResourceExhausted" in err_str
                logger.warning(f"⚠️ Gemini failed (attempt {attempt + 1}): {e}")
                
                if is_rate_limit and gemini_manager.rotate_key_or_model():
                    self.model = gemini_manager.get_model(
                        model_name="gemini-flash-latest", 
                        tools=[self.tool]
                    )
                    chat_history_copy = list(chat.history)
                    chat = self.model.start_chat(history=chat_history_copy)
                    continue
                
                if attempt == max_attempts - 1:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 15.0)
        
        if response is None:
            raise RuntimeError("Failed to get response from Gemini after all retries")
        
        # Handle function calling loop
        loop_limit = 5
        loop_count = 0
        
        while response.candidates and response.candidates[0].content.parts and loop_count < loop_limit:
            function_calls = [part.function_call for part in response.candidates[0].content.parts if part.function_call]
            if not function_calls:
                break
            
            loop_count += 1
            logger.info(f"[Gemini Chat] Loop {loop_count}: {len(function_calls)} function call(s)")
            
            parts_to_send = []
            for call in function_calls:
                func_name = call.name
                args = dict(call.args)
                self._update_session_context(session, func_name, args)
                
                tool_result = self._execute_tool(func_name, args, session)
                
                if func_name == "recommend_business":
                    try:
                        res_json = json.loads(tool_result)
                        if res_json.get("success") and res_json.get("recommendations"):
                            session["active_business"] = res_json["recommendations"][0]["category"]
                    except Exception:
                        pass
                
                parts_to_send.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=func_name,
                            response={"result": tool_result}
                        )
                    )
                )
            
            content_to_send = genai.protos.Content(parts=parts_to_send)
            
            try:
                gemini_manager.configure_current_key()
                response = chat.send_message(content_to_send)
            except Exception as e:
                logger.warning(f"⚠️ Gemini failed during tool response: {e}")
                raise
        
        session["history"] = chat.history
        
        final_text = ""
        try:
            final_text = response.text
        except Exception:
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        final_text += part.text
        
        session["raw_messages"].append({"role": "assistant", "text": final_text})
        
        return {
            "success": True,
            "response": final_text,
            "session_id": session_id,
            "profile": session["profile"],
            "active_business": session["active_business"]
        }

    # ============================================================
    # 🛠️ SHARED HELPERS
    # ============================================================

    def _update_session_context(self, session, func_name, args):
        """Update session profile and active_business based on tool call."""
        if func_name == "recommend_business":
            capital_val = args.get("capital")
            if capital_val:
                if isinstance(capital_val, str):
                    digits = re.findall(r'\d+', capital_val)
                    if digits:
                        num = float("".join(digits))
                        if "triệu" in capital_val or "m" in capital_val.lower():
                            num *= 1000000
                        capital_val = num
                    else:
                        capital_val = 100000000.0
                else:
                    capital_val = float(capital_val)
            else:
                capital_val = 100000000.0
            session["profile"]["capital"] = capital_val
            session["profile"]["location"] = args.get("location", "TP.HCM")
            if args.get("interest"): session["profile"]["interest"] = args.get("interest")
            if args.get("experience"): session["profile"]["experience"] = args.get("experience")
        elif func_name in ("get_business_detail", "analyze_profit", "analyze_risk", "generate_roadmap"):
            biz = args.get("business_name_or_id") or session.get("active_business")
            if biz: session["active_business"] = biz
        elif func_name == "analyze_market":
            kw = args.get("keyword")
            if kw: session["active_business"] = kw
