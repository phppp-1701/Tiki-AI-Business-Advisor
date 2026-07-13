# ============================================================
# SEARCH ENGINE V2 - Enhanced AI Insights
# ============================================================

import json
import logging
from typing import Dict, List, Any
import google.generativeai as genai
from gemini_helper import gemini_manager

logger = logging.getLogger(__name__)

from context_detection import (
    detectContext,
    groupByContext,
    getSuggestedContexts,
    getContextLabel,
    pick_primary_context,
    filter_by_context,
)


class SearchEngine:
    """
    Product search engine with ENHANCED AI-powered insights
    """

    def __init__(self, data_loader, model_loader, rag_engine, gemini_model):
        self.data_loader = data_loader
        self.model_loader = model_loader
        self.rag_engine = rag_engine
        self.gemini_model = gemini_model

        logger.info("🔍 Search Engine V2 initialized")

    def search_products(
        self, keyword: str, limit: int = 20, use_semantic: bool = True
    ) -> List[Dict]:
        """Search products by keyword"""
        if use_semantic and self.rag_engine:
            try:
                docs = self.rag_engine.vector_store.similarity_search(
                    keyword, k=limit * 2
                )

                product_ids = []
                for doc in docs:
                    if doc.metadata.get("source") == "product":
                        pid = doc.metadata.get("product_id")
                        if pid and pid not in product_ids:
                            product_ids.append(pid)

                products = []
                for pid in product_ids[:limit]:
                    product = self.data_loader.get_product_by_id(int(pid))
                    if product:
                        products.append(product)

                if products:
                    return products

            except Exception as e:
                logger.warning(f"Semantic search failed: {e}")

        return self.data_loader.search_products(keyword, limit)

    def analyze_contexts(
        self,
        keyword: str,
        products: List[Dict[str, Any]],
        selected_context: str | None = None,
    ) -> Dict[str, Any]:
        """
        Detect contexts, pick primary context, and return filtered products + suggestions.
        """
        grouped = groupByContext(products or [], keyword=keyword)
        primary = pick_primary_context(grouped, keyword=keyword)
        chosen = selected_context or primary
        filtered = filter_by_context(products or [], keyword=keyword, context_id=chosen)
        suggestions = getSuggestedContexts(
            keyword=keyword,
            grouped=grouped,
            selected_context=chosen,
            max_suggestions=6,
        )

        # ZERO-RESULT FALLBACK: If no products, try to guess categories from synonym map
        if not products and not suggestions:
            from search_engine.synonym_map import detect_compound
            from search_engine.normalizer import normalize
            compound = detect_compound(normalize(keyword))
            if compound and "category_focus" in compound:
                for cat in compound["category_focus"]:
                    # map the slug to a more readable name if possible, or just use slug
                    from search_engine.synonym_map import REAL_CATEGORY_SLUGS
                    readable_cat = " ".join(cat.split("-")).title()
                    suggestions.append({
                        "context_id": cat,
                        "label": readable_cat,
                        "count": 0,
                        "is_template_generated": False,
                        "is_validated_by_data": False,
                        "evidence_count": 0,
                        "evidence_examples": [],
                    })
            else:
                # Add a generic fallback
                suggestions.append({
                    "context_id": "other",
                    "label": "Gợi ý: Thử từ khóa khác hoặc tìm theo danh mục lớn",
                    "count": 0,
                    "is_template_generated": False,
                    "is_validated_by_data": False,
                    "evidence_count": 0,
                    "evidence_examples": [],
                })

        context_counts = {k: len(v) for k, v in grouped.items()}
        return {
            "primary_context": primary,
            "selected_context": chosen,
            "primary_context_label": getContextLabel(keyword, primary),
            "selected_context_label": getContextLabel(keyword, chosen),
            "context_counts": context_counts,
            "filtered_products": filtered,
            "suggestions": suggestions,
        }

    def generate_insight(
        self, products: List[Dict], keyword: str, include_ml_insights: bool = True
    ) -> str:
        """
        🚀 Generate market insights using the offline fallback analyzer (does not call Gemini API for speed).
        """
        if not products:
            return f"Không tìm thấy sản phẩm nào phù hợp với '{keyword}'. Vui lòng thử từ khóa khác."

        # 1. Basic stats
        avg_price = sum(p["price"] for p in products) / len(products)
        avg_rating = sum(p["rating"] for p in products) / len(products)
        total_sold = sum(p["boughtInLastMonth"] for p in products)

        # 2. Price segmentation
        budget_products = [p for p in products if p["price"] < avg_price * 0.7]
        mid_products = [
            p for p in products if avg_price * 0.7 <= p["price"] <= avg_price * 1.3
        ]
        premium_products = [p for p in products if p["price"] > avg_price * 1.3]

        return self._generate_fallback_insight(
            keyword,
            products,
            avg_price,
            avg_rating,
            total_sold,
            budget_products,
            mid_products,
            premium_products,
        )

    def _get_detailed_ml_insights(self, products: List[Dict]) -> str:
        """Get ML insights: KMeans from CSV centroids, price trend from timeseries, sentiment from reviews"""
        insights = []

        # --- 1. KMeans Clustering ---
        if self.model_loader.kmeans_model and self.data_loader.products_df is not None:
            try:
                pid_list = []
                for p in products[:10]:
                    pid = str(p.get("product_id", "")).strip()
                    if pid.endswith(".0"):
                        pid = pid[:-2]
                    if pid:
                        pid_list.append(pid)

                cluster_info: Dict[str, int] = {}
                if pid_list:
                    df = self.data_loader.products_df
                    rows = df[df["product_id"].astype(str).isin(pid_list)]
                    for _, row in rows.iterrows():
                        if 'cluster_name' in row and pd.notna(row['cluster_name']) and row['cluster_name'] != "N/A":
                            cname = str(row['cluster_name'])
                        else:
                            _, cname = self.model_loader.assign_cluster(
                                float(row.get("price_normalized", 0)),
                                float(row.get("rating_normalized", 0)),
                                float(row.get("popularity_score", 0)),
                            )
                        cluster_info[cname] = cluster_info.get(cname, 0) + 1

                if cluster_info:
                    insights.append("**🎯 Phân khúc Cluster (KMeans):**")
                    for cname, count in sorted(
                        cluster_info.items(), key=lambda x: -x[1]
                    ):
                        insights.append(f"- {cname}: {count} sản phẩm")
            except Exception as e:
                logger.debug(f"KMeans insight failed: {e}")

        # --- 2. Price Trend (Prophet forecasts pkl nếu có, fallback timeseries.json) ---
        prophet_forecasts = getattr(self.model_loader, "prophet_forecasts", None)
        ts_df = getattr(self.data_loader, "timeseries_df", None)

        used_source = None
        forecasted = 0
        total_change = 0.0

        # Priority: Prophet pkl forecasts
        if prophet_forecasts:
            try:
                for p in products[:10]:
                    try:
                        pid = int(float(p["product_id"]))
                    except (ValueError, TypeError):
                        continue
                    if pid not in prophet_forecasts:
                        continue
                    fc_df = prophet_forecasts[pid]
                    if fc_df is None or len(fc_df) == 0:
                        continue
                    # Use last 7 predicted values vs current price
                    future_price = float(fc_df["yhat"].iloc[-7:].mean())
                    current_price = float(p["price"])
                    if current_price > 0:
                        total_change += (
                            (future_price - current_price) / current_price
                        ) * 100
                        forecasted += 1
                used_source = "Prophet"
            except Exception as e:
                logger.debug(f"Prophet forecast read failed: {e}")
                forecasted = 0

        # Fallback: timeseries.json historical trend
        if forecasted == 0 and ts_df is not None and not ts_df.empty:
            try:
                for p in products[:10]:
                    try:
                        pid = int(float(p["product_id"]))
                    except (ValueError, TypeError):
                        continue
                    rows = ts_df[ts_df["product_id"] == pid].sort_values("ds")
                    if len(rows) < 8:
                        continue
                    recent = rows["y"].iloc[-7:].mean()
                    prior = (
                        rows["y"].iloc[-14:-7].mean()
                        if len(rows) >= 14
                        else rows["y"].iloc[:-7].mean()
                    )
                    if prior > 0:
                        total_change += ((recent - prior) / prior) * 100
                        forecasted += 1
                used_source = "lịch sử"
            except Exception as e:
                logger.debug(f"Timeseries trend failed: {e}")

        if forecasted > 0:
            avg_change = total_change / forecasted
            source_label = (
                f"dự báo {used_source}"
                if used_source == "Prophet"
                else "xu hướng lịch sử"
            )
            insights.append(f"\n**📈 Phân tích giá ({source_label}):**")
            insights.append(
                f"- Có dữ liệu cho {forecasted}/{len(products[:10])} sản phẩm"
            )
            if avg_change > 5:
                insights.append(f"- Xu hướng: Giá dự kiến TĂNG {avg_change:.1f}% ⬆️")
            elif avg_change < -5:
                insights.append(
                    f"- Xu hướng: Giá dự kiến GIẢM {abs(avg_change):.1f}% ⬇️"
                )
            else:
                insights.append(
                    f"- Xu hướng: Giá ổn định, biến động nhẹ ({avg_change:+.1f}%) ➡️"
                )

        # --- 3. Sentiment từ reviews.json (PhoBERT pre-labeled) ---
        rv_df = getattr(self.data_loader, "reviews_df", None)
        if (
            self.model_loader.phobert_available
            and rv_df is not None
            and not rv_df.empty
        ):
            try:
                pid_list = []
                for p in products[:10]:
                    pid = str(p.get("product_id", "")).strip()
                    if pid.endswith(".0"):
                        pid = pid[:-2]
                    if pid:
                        pid_list.append(pid)

                if pid_list:
                    rv = rv_df[rv_df["product_id"].astype(str).isin(pid_list)]
                    total = len(rv)
                    if total > 0:
                        pos = int((rv["sentiment_label"] == "positive").sum())
                        neg = int((rv["sentiment_label"] == "negative").sum())
                        neu = total - pos - neg
                        insights.append(
                            "\n**💬 Phân tích Sentiment (PhoBERT pre-labeled):**"
                        )
                        insights.append(f"- Tổng {total} đánh giá được phân tích")
                        insights.append(f"- ✅ Tích cực: {pos} ({pos/total*100:.0f}%)")
                        insights.append(f"- ⚠️  Trung lập: {neu} ({neu/total*100:.0f}%)")
                        insights.append(f"- ❌ Tiêu cực: {neg} ({neg/total*100:.0f}%)")
            except Exception as e:
                logger.debug(f"Sentiment insight failed: {e}")

        return "\n".join(insights) if insights else ""

    def _generate_fallback_insight(
        self,
        keyword,
        products,
        avg_price,
        avg_rating,
        total_sold,
        budget_products,
        mid_products,
        premium_products,
    ) -> str:
        """Enhanced fallback when Gemini fails"""

        # Determine market competition
        if total_sold > 50000:
            competition = "RẤT CAO 🔥"
        elif total_sold > 10000:
            competition = "CAO 📈"
        elif total_sold > 1000:
            competition = "TRUNG BÌNH 📊"
        else:
            competition = "THẤP 🌱"

        # Determine best segment
        if len(premium_products) > len(budget_products):
            best_segment = "cao cấp (khách hàng sẵn sàng chi tiêu)"
        elif len(budget_products) > len(mid_products):
            best_segment = "bình dân (cạnh tranh giá)"
        else:
            best_segment = "trung cấp (cân bằng giá/chất lượng)"

        # Per-product dynamic descriptions for section 3
        top_3 = products[:3]
        sold_list = [p["boughtInLastMonth"] for p in top_3]
        median_sold = sorted(sold_list)[len(sold_list) // 2] if sold_list else 1

        def _desc(p):
            price_diff = (
                (p["price"] - avg_price) / avg_price * 100 if avg_price > 0 else 0
            )
            if price_diff < -15:
                price_label = (
                    f"giá thấp hơn trung bình thị trường {abs(price_diff):.0f}%"
                )
            elif price_diff > 15:
                price_label = f"định giá cao hơn thị trường {price_diff:.0f}%"
            else:
                price_label = "giá sát mức trung bình thị trường"

            rating_diff = p["rating"] - avg_rating
            if rating_diff >= 0.3:
                quality_label = f"chất lượng vượt trội ({p['rating']:.1f}⭐)"
            elif rating_diff <= -0.3:
                quality_label = (
                    f"rating dưới chuẩn ({p['rating']:.1f}⭐), cần cải thiện"
                )
            else:
                quality_label = f"chất lượng ổn định ({p['rating']:.1f}⭐)"

            sold = p["boughtInLastMonth"]
            if sold > median_sold * 1.5:
                sales_label = f"bán chạy nhất nhóm ({sold:,} sp/tháng)"
            elif sold < median_sold * 0.5:
                sales_label = f"lượng bán còn hạn chế ({sold:,} sp/tháng)"
            else:
                sales_label = f"lượng bán ổn định ({sold:,} sp/tháng)"

            return f"{price_label}, {quality_label}, {sales_label}"

        top_product_lines = (
            "".join(
                f"- {i}) {p['title']}: {_desc(p)}.\n" for i, p in enumerate(top_3, 1)
            )
            or "- Không có dữ liệu sản phẩm.\n"
        )

        # Extra context for sections 4 & 5
        cats = {}
        for p in products:
            cats[p["categoryName"]] = cats.get(p["categoryName"], 0) + 1
        top_cat_name, top_cat_count = (
            max(cats.items(), key=lambda x: x[1]) if cats else ("N/A", 0)
        )
        top_cat_pct = top_cat_count / len(products) * 100 if products else 0

        min_price = min(p["price"] for p in products)
        max_price = max(p["price"] for p in products)

        seg_counts = {
            "bình dân": len(budget_products),
            "trung cấp": len(mid_products),
            "cao cấp": len(premium_products),
        }
        least_segment = min(seg_counts, key=lambda k: seg_counts[k])

        top1_title = products[0]["title"]
        top1_short = top1_title[:57] + "..." if len(top1_title) > 60 else top1_title

        return f"""📊 **PHÂN TÍCH THỊ TRƯỜNG: \"{keyword}\"**
============================================================

**1. TỔNG QUAN THỊ TRƯỜNG**
- ✅ Tìm thấy {len(products)} sản phẩm liên quan
- 💰 Giá trung bình: {avg_price:,.0f} VND
- ⭐ Rating trung bình: {avg_rating:.1f}/5.0
- 🛒 Tổng đã bán: {total_sold:,} sản phẩm
- 🔥 Mức độ cạnh tranh: {competition}

**2. PHÂN KHÚC GIÁ**
- 💙 Bình dân: {len(budget_products)} sản phẩm ({len(budget_products)/len(products)*100:.0f}%)
- 💚 Trung cấp: {len(mid_products)} sản phẩm ({len(mid_products)/len(products)*100:.0f}%)
- 💎 Cao cấp: {len(premium_products)} sản phẩm ({len(premium_products)/len(products)*100:.0f}%)
- 📌 Phân khúc có nhiều sản phẩm nhất: {best_segment.upper()}

**3. TOP 3 SẢN PHẨM XUẤT SẮC**
{top_product_lines}
**4. CHIẾN LƯỢC KINH DOANH**
- Danh mục **{top_cat_name}** chiếm ưu thế với {top_cat_count} sản phẩm ({top_cat_pct:.0f}% thị phần) — đây là trận địa cạnh tranh chính cần theo dõi sát.
- Phân khúc **{best_segment}** đang dẫn đầu; nếu muốn ít cạnh tranh hơn, hãy nhắm vào phân khúc **{least_segment}** vốn còn ít đối thủ khai thác.
- Rating trung bình thị trường là {avg_rating:.1f}⭐ — {"cơ hội lớn nếu bạn cam kết chất lượng vượt mức này" if avg_rating < 4.0 else "thị trường đã khá chất lượng, cần cạnh tranh bằng giá hoặc dịch vụ"}.

**5. KẾ HOẠCH HÀNH ĐỘNG**
- ✅ Bước 1: Tối ưu trang sản phẩm cho **{top1_short}** — đang bán chạy nhất — bằng ảnh chất lượng cao và mô tả chi tiết trong danh mục **{top_cat_name}**.
- ✅ Bước 2: Định giá trong khoảng **{min_price:,.0f} – {max_price:,.0f} VND** (biên độ thực tế của thị trường); tránh ra ngoài vùng này nếu chưa có thương hiệu đủ mạnh.
- ✅ Bước 3: Khai thác phân khúc **{least_segment}** đang còn ít đối thủ — đây là "vùng xanh" tiềm năng để tạo lợi thế khác biệt.

**GHI CHÚ:**
- Dữ liệu phân tích dựa trên {len(products)} sản phẩm đại diện.
- Mỗi đề xuất ở trên được thiết kế để áp dụng ngay trong 2-4 tuần tới.
"""

    def generate_market_report(self, keyword: str, products: List[Dict]) -> Dict:
        """Generate structured market report for the Market Analysis tab"""
        if not products:
            return {
                "overview": {
                    "total_products": 0,
                    "total_sold": 0,
                    "total_revenue": 0,
                    "avg_price": 0,
                    "min_price": 0,
                    "max_price": 0
                },
                "price_segments": {
                    "budget": {"count": 0, "pct": 0.0},
                    "mid": {"count": 0, "pct": 0.0},
                    "premium": {"count": 0, "pct": 0.0}
                },
                "price_trend": {
                    "direction": "stable",
                    "avg_change_pct": 0.0,
                    "source": "N/A",
                    "products_analyzed": 0
                },
                "sentiment": {
                    "total": 0,
                    "positive": 0,
                    "neutral": 0,
                    "negative": 0,
                    "pos_pct": 0.0,
                    "neu_pct": 0.0,
                    "neg_pct": 0.0
                },
                "top_products": [],
                "top_categories": [],
                "ai_report": f"Không tìm thấy sản phẩm nào phù hợp với '{keyword}'. Vui lòng thử từ khóa khác hoặc tham khảo các gợi ý ngữ cảnh phía trên."
            }

        # --- Overview ---
        avg_price = sum(p["price"] for p in products) / len(products)
        avg_rating = sum(p["rating"] for p in products) / len(products)
        total_sold = sum(p["boughtInLastMonth"] for p in products)
        total_revenue = sum(
            p.get("estimated_revenue", p["price"] * p["boughtInLastMonth"])
            for p in products
        )
        max_price = max(p["price"] for p in products)
        min_price = min(p["price"] for p in products)

        # --- Price segments ---
        budget = [p for p in products if p["price"] < avg_price * 0.7]
        mid = [p for p in products if avg_price * 0.7 <= p["price"] <= avg_price * 1.3]
        premium = [p for p in products if p["price"] > avg_price * 1.3]

        # --- Categories ---
        from context_detection import detectContext
        categories: Dict[str, int] = {}
        for p in products:
            cat = detectContext(p, keyword)
            categories[cat] = categories.get(cat, 0) + 1
        top_categories = [
            {"name": k, "count": v, "pct": round(v / len(products) * 100, 1)}
            for k, v in sorted(categories.items(), key=lambda x: -x[1])[:5]
        ]


        # --- Top 10 products (already sorted by quantity_sold from data_loader) ---
        top_products = []
        for i, p in enumerate(products[:10], 1):
            top_products.append(
                {
                    "rank": i,
                    "name": p["title"],
                    "price": p["price"],
                    "sold": p["boughtInLastMonth"],
                    "revenue": p.get(
                        "estimated_revenue", p["price"] * p["boughtInLastMonth"]
                    ),
                    "rating": p["rating"],
                    "category": p["categoryName"],
                    "url": p.get("product_url", ""),
                    "product_id": str(p.get("product_id", "")),
                }
            )

        # --- Sentiment (từ reviews.json, không cần phobert_available) ---
        sentiment = {
            "total": 0,
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "pos_pct": 0,
            "neu_pct": 0,
            "neg_pct": 0,
        }
        rv_df = getattr(self.data_loader, "reviews_df", None)
        if rv_df is not None and not rv_df.empty:
            try:
                pid_list = []
                for p in products:
                    pid = str(p.get("product_id", "")).strip()
                    if pid.endswith(".0"):
                        pid = pid[:-2]
                    if pid:
                        pid_list.append(pid)
                if pid_list:
                    rv = rv_df[rv_df["product_id"].astype(str).isin(pid_list)]
                    total_rv = len(rv)
                    if total_rv > 0:
                        pos = int((rv["sentiment_label"] == "positive").sum())
                        neg = int((rv["sentiment_label"] == "negative").sum())
                        neu = total_rv - pos - neg
                        sentiment = {
                            "total": total_rv,
                            "positive": pos,
                            "neutral": neu,
                            "negative": neg,
                            "pos_pct": round(pos / total_rv * 100, 1),
                            "neu_pct": round(neu / total_rv * 100, 1),
                            "neg_pct": round(neg / total_rv * 100, 1),
                        }
            except Exception as e:
                logger.debug(f"Sentiment report failed: {e}")

        # --- Price trend (Prophet → timeseries fallback) ---
        price_trend = {
            "direction": "stable",
            "avg_change_pct": 0.0,
            "source": "N/A",
            "products_analyzed": 0,
        }
        prophet_forecasts = getattr(self.model_loader, "prophet_forecasts", None)
        ts_df = getattr(self.data_loader, "timeseries_df", None)
        forecasted = 0
        total_change = 0.0
        used_source = None

        if prophet_forecasts:
            try:
                for p in products[:20]:
                    try:
                        pid = int(float(p["product_id"]))
                    except (ValueError, TypeError):
                        continue
                    if pid not in prophet_forecasts:
                        continue
                    fc_df = prophet_forecasts[pid]
                    if fc_df is None or len(fc_df) == 0:
                        continue
                    future_price = float(fc_df["yhat"].iloc[-7:].mean())
                    current_price = float(p["price"])
                    if current_price > 0:
                        total_change += (
                            (future_price - current_price) / current_price
                        ) * 100
                        forecasted += 1
                used_source = "Prophet"
            except Exception as e:
                logger.debug(f"Prophet trend failed: {e}")

        if forecasted == 0 and ts_df is not None and not ts_df.empty:
            try:
                for p in products[:20]:
                    try:
                        pid = int(float(p["product_id"]))
                    except (ValueError, TypeError):
                        continue
                    rows = ts_df[ts_df["product_id"] == pid].sort_values("ds")
                    if len(rows) < 8:
                        continue
                    recent = rows["y"].iloc[-7:].mean()
                    prior = (
                        rows["y"].iloc[-14:-7].mean()
                        if len(rows) >= 14
                        else rows["y"].iloc[:-7].mean()
                    )
                    if prior > 0:
                        total_change += ((recent - prior) / prior) * 100
                        forecasted += 1
                used_source = "Lịch sử"
            except Exception as e:
                logger.debug(f"Timeseries trend failed: {e}")

        if forecasted > 0:
            avg_change = total_change / forecasted
            direction = (
                "up" if avg_change > 5 else ("down" if avg_change < -5 else "stable")
            )
            price_trend = {
                "direction": direction,
                "avg_change_pct": round(avg_change, 1),
                "source": used_source,
                "products_analyzed": forecasted,
            }

        # --- KMeans clusters ---
        clusters = []
        if self.model_loader.kmeans_model and self.data_loader.products_df is not None:
            try:
                df = self.data_loader.products_df
                cluster_map: Dict[str, Dict] = {}
                for _, row in df.iterrows():
                    if 'cluster_name' in row and pd.notna(row['cluster_name']) and row['cluster_name'] != "N/A":
                        cname = str(row['cluster_name'])
                    else:
                        _, cname = self.model_loader.assign_cluster(
                            float(row.get("price_normalized", 0)),
                            float(row.get("rating_normalized", 0)),
                            float(row.get("popularity_score", 0)),
                        )
                    if cname not in cluster_map:
                        cluster_map[cname] = {
                            "count": 0,
                            "price_sum": 0.0,
                            "rating_sum": 0.0,
                        }
                    cluster_map[cname]["count"] += 1
                    cluster_map[cname]["price_sum"] += float(
                        row.get("original_price", 0)
                    )
                    cluster_map[cname]["rating_sum"] += float(
                        row.get("original_rating", 0)
                    )
                for cname, data in sorted(
                    cluster_map.items(), key=lambda x: -x[1]["count"]
                ):
                    cnt = data["count"]
                    clusters.append(
                        {
                            "name": cname,
                            "count": cnt,
                            "avg_price": (
                                round(data["price_sum"] / cnt, 0) if cnt > 0 else 0
                            ),
                            "avg_rating": (
                                round(data["rating_sum"] / cnt, 2) if cnt > 0 else 0
                            ),
                        }
                    )
            except Exception as e:
                logger.debug(f"Cluster report failed: {e}")

        # --- AI Report ---
        ai_report = self.generate_insight(
            products=products, keyword=keyword, include_ml_insights=True
        )

        return {
            "keyword": keyword,
            "overview": {
                "total_products": len(products),
                "total_sold": total_sold,
                "total_revenue": round(total_revenue, 0),
                "avg_price": round(avg_price, 0),
                "avg_rating": round(avg_rating, 2),
                "min_price": round(min_price, 0),
                "max_price": round(max_price, 0),
            },
            "price_segments": {
                "budget": {
                    "count": len(budget),
                    "pct": round(len(budget) / len(products) * 100, 1),
                },
                "mid": {
                    "count": len(mid),
                    "pct": round(len(mid) / len(products) * 100, 1),
                },
                "premium": {
                    "count": len(premium),
                    "pct": round(len(premium) / len(products) * 100, 1),
                },
            },
            "top_categories": top_categories,
            "top_products": top_products,
            "sentiment": sentiment,
            "price_trend": price_trend,
            "clusters": clusters,
            "ai_report": ai_report,
        }

    def generate_market_report(self, keyword: str, products: List[Dict]) -> Dict:
        """Generate structured market report for the Market Analysis tab"""
        if not products:
            return {
                "overview": {
                    "total_products": 0,
                    "total_sold": 0,
                    "total_revenue": 0,
                    "avg_price": 0,
                    "min_price": 0,
                    "max_price": 0
                },
                "price_segments": {
                    "budget": {"count": 0, "pct": 0.0},
                    "mid": {"count": 0, "pct": 0.0},
                    "premium": {"count": 0, "pct": 0.0}
                },
                "price_trend": {
                    "direction": "stable",
                    "avg_change_pct": 0.0,
                    "source": "N/A",
                    "products_analyzed": 0
                },
                "sentiment": {
                    "total": 0,
                    "positive": 0,
                    "neutral": 0,
                    "negative": 0,
                    "pos_pct": 0.0,
                    "neu_pct": 0.0,
                    "neg_pct": 0.0
                },
                "top_products": [],
                "top_categories": [],
                "ai_report": f"Không tìm thấy sản phẩm nào phù hợp với '{keyword}'. Vui lòng thử từ khóa khác hoặc tham khảo các gợi ý ngữ cảnh phía trên."
            }

        # --- Overview ---
        avg_price = sum(p["price"] for p in products) / len(products)
        avg_rating = sum(p["rating"] for p in products) / len(products)
        total_sold = sum(p["boughtInLastMonth"] for p in products)
        total_revenue = sum(
            p.get("estimated_revenue", p["price"] * p["boughtInLastMonth"])
            for p in products
        )
        max_price = max(p["price"] for p in products)
        min_price = min(p["price"] for p in products)

        # --- Price segments ---
        budget = [p for p in products if p["price"] < avg_price * 0.7]
        mid = [p for p in products if avg_price * 0.7 <= p["price"] <= avg_price * 1.3]
        premium = [p for p in products if p["price"] > avg_price * 1.3]

        # --- Categories ---
        categories: Dict[str, int] = {}
        for p in products:
            cat = p["categoryName"]
            categories[cat] = categories.get(cat, 0) + 1
        top_categories = [
            {"name": k, "count": v, "pct": round(v / len(products) * 100, 1)}
            for k, v in sorted(categories.items(), key=lambda x: -x[1])[:5]
        ]

        # --- All products (already sorted by quantity_sold from data_loader) ---
        top_products = []
        for i, p in enumerate(products, 1):
            top_products.append(
                {
                    "rank": i,
                    "name": p["title"],
                    "price": p["price"],
                    "sold": p["boughtInLastMonth"],
                    "revenue": p.get(
                        "estimated_revenue", p["price"] * p["boughtInLastMonth"]
                    ),
                    "rating": p["rating"],
                    "category": p["categoryName"],
                    "url": p.get("product_url", ""),
                    "product_id": str(p.get("product_id", "")),
                }
            )

        # --- Sentiment (từ reviews.json, không cần phobert_available) ---
        sentiment = {
            "total": 0,
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            "pos_pct": 0,
            "neu_pct": 0,
            "neg_pct": 0,
        }
        rv_df = getattr(self.data_loader, "reviews_df", None)
        if rv_df is not None and not rv_df.empty:
            try:
                pid_list = []
                for p in products:
                    pid = str(p.get("product_id", "")).strip()
                    if pid.endswith(".0"):
                        pid = pid[:-2]
                    if pid:
                        pid_list.append(pid)
                if pid_list:
                    rv = rv_df[rv_df["product_id"].astype(str).isin(pid_list)]
                    total_rv = len(rv)
                    if total_rv > 0:
                        pos = int((rv["sentiment_label"] == "positive").sum())
                        neg = int((rv["sentiment_label"] == "negative").sum())
                        neu = total_rv - pos - neg
                        sentiment = {
                            "total": total_rv,
                            "positive": pos,
                            "neutral": neu,
                            "negative": neg,
                            "pos_pct": round(pos / total_rv * 100, 1),
                            "neu_pct": round(neu / total_rv * 100, 1),
                            "neg_pct": round(neg / total_rv * 100, 1),
                        }
            except Exception as e:
                logger.debug(f"Sentiment report failed: {e}")

        # --- Price trend (Prophet → timeseries fallback) ---
        price_trend = {
            "direction": "stable",
            "avg_change_pct": 0.0,
            "source": "N/A",
            "products_analyzed": 0,
        }
        prophet_forecasts = getattr(self.model_loader, "prophet_forecasts", None)
        ts_df = getattr(self.data_loader, "timeseries_df", None)
        forecasted = 0
        total_change = 0.0
        used_source = None

        if prophet_forecasts:
            try:
                for p in products[:20]:
                    try:
                        pid = int(float(p["product_id"]))
                    except (ValueError, TypeError):
                        continue
                    if pid not in prophet_forecasts:
                        continue
                    fc_df = prophet_forecasts[pid]
                    if fc_df is None or len(fc_df) == 0:
                        continue
                    future_price = float(fc_df["yhat"].iloc[-7:].mean())
                    current_price = float(p["price"])
                    if current_price > 0:
                        total_change += (
                            (future_price - current_price) / current_price
                        ) * 100
                        forecasted += 1
                used_source = "Prophet"
            except Exception as e:
                logger.debug(f"Prophet trend failed: {e}")

        if forecasted == 0 and ts_df is not None and not ts_df.empty:
            try:
                for p in products[:20]:
                    try:
                        pid = int(float(p["product_id"]))
                    except (ValueError, TypeError):
                        continue
                    rows = ts_df[ts_df["product_id"] == pid].sort_values("ds")
                    if len(rows) < 8:
                        continue
                    recent = rows["y"].iloc[-7:].mean()
                    prior = (
                        rows["y"].iloc[-14:-7].mean()
                        if len(rows) >= 14
                        else rows["y"].iloc[:-7].mean()
                    )
                    if prior > 0:
                        total_change += ((recent - prior) / prior) * 100
                        forecasted += 1
                used_source = "Lịch sử"
            except Exception as e:
                logger.debug(f"Timeseries trend failed: {e}")

        if forecasted > 0:
            avg_change = total_change / forecasted
            direction = (
                "up" if avg_change > 5 else ("down" if avg_change < -5 else "stable")
            )
            price_trend = {
                "direction": direction,
                "avg_change_pct": round(avg_change, 1),
                "source": used_source,
                "products_analyzed": forecasted,
            }

        # --- KMeans clusters ---
        clusters = []
        if self.model_loader.kmeans_model and self.data_loader.products_df is not None:
            try:
                df = self.data_loader.products_df
                cluster_map: Dict[str, Dict] = {}
                for _, row in df.iterrows():
                    if 'cluster_name' in row and pd.notna(row['cluster_name']) and row['cluster_name'] != "N/A":
                        cname = str(row['cluster_name'])
                    else:
                        _, cname = self.model_loader.assign_cluster(
                            float(row.get("price_normalized", 0)),
                            float(row.get("rating_normalized", 0)),
                            float(row.get("popularity_score", 0)),
                        )
                    if cname not in cluster_map:
                        cluster_map[cname] = {
                            "count": 0,
                            "price_sum": 0.0,
                            "rating_sum": 0.0,
                        }
                    cluster_map[cname]["count"] += 1
                    cluster_map[cname]["price_sum"] += float(
                        row.get("original_price", 0)
                    )
                    cluster_map[cname]["rating_sum"] += float(
                        row.get("original_rating", 0)
                    )
                for cname, data in sorted(
                    cluster_map.items(), key=lambda x: -x[1]["count"]
                ):
                    cnt = data["count"]
                    clusters.append(
                        {
                            "name": cname,
                            "count": cnt,
                            "avg_price": (
                                round(data["price_sum"] / cnt, 0) if cnt > 0 else 0
                            ),
                            "avg_rating": (
                                round(data["rating_sum"] / cnt, 2) if cnt > 0 else 0
                            ),
                        }
                    )
            except Exception as e:
                logger.debug(f"Cluster report failed: {e}")

        # --- AI Report ---
        ai_report = self.generate_insight(
            products=products, keyword=keyword, include_ml_insights=True
        )

        return {
            "keyword": keyword,
            "overview": {
                "total_products": len(products),
                "total_sold": total_sold,
                "total_revenue": round(total_revenue, 0),
                "avg_price": round(avg_price, 0),
                "avg_rating": round(avg_rating, 2),
                "min_price": round(min_price, 0),
                "max_price": round(max_price, 0),
            },
            "price_segments": {
                "budget": {
                    "count": len(budget),
                    "pct": round(len(budget) / len(products) * 100, 1),
                },
                "mid": {
                    "count": len(mid),
                    "pct": round(len(mid) / len(products) * 100, 1),
                },
                "premium": {
                    "count": len(premium),
                    "pct": round(len(premium) / len(products) * 100, 1),
                },
            },
            "top_categories": top_categories,
            "top_products": top_products,
            "sentiment": sentiment,
            "price_trend": price_trend,
            "clusters": clusters,
            "ai_report": ai_report,
        }

    def analyze_batch(self, keywords: List[str], limit_per_keyword: int = 5) -> Dict:
        """Analyze multiple keywords (batch mode)"""
        all_products = []
        seen_ids = set()

        for keyword in keywords[:10]:
            products = self.search_products(
                keyword, limit_per_keyword, use_semantic=False
            )

            for p in products:
                if p["product_id"] not in seen_ids:
                    seen_ids.add(p["product_id"])
                    all_products.append(p)

        batch_insight = self._generate_batch_insight(keywords, all_products)

        return {
            "products": all_products[:20],
            "ai_insight": batch_insight,
            "keywords_processed": len(keywords),
            "total_found": len(all_products),
        }

    def _generate_batch_insight(self, keywords: List[str], products: List[Dict]) -> str:
        """Generate batch insight without calling Gemini API (offline fallback)"""
        if not products:
            return "Không tìm thấy sản phẩm nào cho các từ khóa đã nhập."

        # Aggregate stats
        categories = {}
        total_revenue = sum(p["price"] * p["boughtInLastMonth"] for p in products)
        avg_price = sum(p["price"] for p in products) / len(products)

        for p in products:
            cat = p["categoryName"]
            categories[cat] = categories.get(cat, 0) + 1

        top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
        
        top_cats_lines = []
        for i, (cat, count) in enumerate(top_cats[:3], 1):
            pct = count / len(products) * 100
            top_cats_lines.append(f"- {cat}: {count} sản phẩm ({pct:.1f}%)")
            
        top_cats_str = "\n".join(top_cats_lines)
            
        return f"""📊 **PHÂN TÍCH BATCH: {len(keywords)} TỪ KHÓA**

Đã phân tích {len(keywords)} từ khóa, tìm thấy {len(products)} sản phẩm độc nhất thuộc {len(categories)} danh mục.

**Danh mục nổi bật:**
{top_cats_str}

**Nhận định:**
Thị trường đa dạng với nhiều cơ hội. Tập trung vào các danh mục nổi bật để tối ưu doanh thu.
"""
