# ============================================================
# TIKI RAG API - FastAPI Server
# ============================================================

import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

from fastapi import FastAPI, HTTPException, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import time
import logging
from datetime import datetime
import io
from io import StringIO
import pandas as pd

from data_loader import DataLoader
from model_loader import ModelLoader
from search_engine_v2 import SearchEngine
from chat_assistant import AIBusinessAssistant
from config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Tiki RAG API",
    description="E-commerce search API with AI insights",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
rag_engine: Optional[Any] = None
data_loader: Optional[DataLoader] = None
model_loader: Optional[ModelLoader] = None
search_engine: Optional[SearchEngine] = None
assistant: Optional[Any] = None

# Request/Response models
class SearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    market: str = Field(default="US")
    limit: int = Field(default=9999, ge=1) 
    display_limit: int = Field(default=20, ge=1)
    context_id: Optional[str] = Field(default=None, max_length=50)

class ChatRequest(BaseModel):
    message: str
    session_id: str
    context_id: Optional[str] = None

class Product(BaseModel):
    product_id: str
    title: str
    categoryName: str
    price: float
    rating: float
    boughtInLastMonth: int
    estimated_revenue: float

class SearchResponse(BaseModel):
    success: bool
    data: Dict[str, Any]

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    rag_engine_loaded: bool
    data_loaded: bool
    models_loaded: Dict[str, bool]

@app.on_event("startup")
async def startup_event():
    global rag_engine, data_loader, model_loader, search_engine, assistant
    
    logger.info("🚀 Starting Tiki RAG API...")
    
    try:
        # 1. Initialize RAG engine (optional). If onnx/chromadb fails, continue without semantic RAG.
        logger.info("🧠 Initializing RAG engine...")
        rag_engine = None
        try:
            from rag_engine import RAGEngine
            rag_engine = RAGEngine(
                gemini_api_key=settings.GEMINI_API_KEY,
                chroma_db_path=settings.CHROMA_DB_PATH,
                embedding_model_name=settings.EMBEDDING_MODEL
            )
            logger.info("✅ RAG engine ready")
        except Exception as rag_error:
            logger.warning(f"⚠️ RAG disabled due to dependency/runtime issue: {rag_error}")

        # 2. Load data files
        logger.info("📥 Loading data...")
        data_loader = DataLoader(data_dir=settings.DATA_PATH)
        
        # 3. Load models
        logger.info("🤖 Loading models...")
        model_loader = ModelLoader(models_dir=settings.MODELS_PATH)
        
        # 4. Initialize search engine
        logger.info("🔍 Initializing search engine...")
        search_engine = SearchEngine(
            data_loader=data_loader,
            model_loader=model_loader,
            rag_engine=rag_engine,
            gemini_model=rag_engine.model if rag_engine else None
        )
        
        # 5. Initialize AI Business Assistant
        logger.info("🤖 Initializing AI Business Assistant...")
        try:
            assistant = AIBusinessAssistant(search_engine=search_engine)
            logger.info("✅ AI Business Assistant Ready!")
        except Exception as chat_error:
            logger.warning(f"⚠️ AI Business Assistant disabled due to issue: {chat_error}")
            
        logger.info("✅ API Ready!")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise

def get_search_engine() -> SearchEngine:
    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not initialized")
    return search_engine


class MarketReportRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    context_id: Optional[str] = Field(default=None, max_length=50)

@app.post("/api/market-report")
async def market_report(
    request: MarketReportRequest,
    engine: SearchEngine = Depends(get_search_engine)
):
    try:
        logger.info(f"📊 Market report request: '{request.keyword}'")
        all_products = engine.search_products(keyword=request.keyword, limit=9999, use_semantic=False)
        
        fallback_kw = None
        if len(all_products) == 0:
            from search_engine.normalizer import normalize
            from search_engine.synonym_map import detect_compound
            compound = detect_compound(normalize(request.keyword))
            if compound and "matched_phrase" in compound:
                fallback_kw = compound["matched_phrase"]
                logger.info(f"0 results, falling back to matched phrase: '{fallback_kw}'")
                all_products = engine.search_products(keyword=fallback_kw, limit=9999, use_semantic=False)
        
        ctx = engine.analyze_contexts(keyword=request.keyword, products=all_products, selected_context=request.context_id)
        filtered = ctx["filtered_products"]

        report = engine.generate_market_report(keyword=request.keyword, products=filtered)
        if fallback_kw and filtered:
            report["ai_report"] = f"⚠️ Không tìm thấy sản phẩm đúng chính xác với '{request.keyword}'. Dưới đây là đề xuất các sản phẩm '{fallback_kw}' liên quan nhất để bạn tham khảo.\n\n" + report.get("ai_report", "")
            
        report["context"] = {
            "primary_context": ctx["primary_context"],
            "selected_context": ctx["selected_context"],
            "primary_context_label": ctx.get("primary_context_label"),
            "selected_context_label": ctx.get("selected_context_label"),
            "context_counts": ctx["context_counts"],
            "suggestions": ctx["suggestions"],
            "total_found_before_filter": len(all_products),
            "total_found_after_filter": len(filtered),
        }
        return {"success": True, "data": report}
    except Exception as e:
        logger.error(f"Market report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/market-insight")
async def market_insight(category: Optional[str] = None):
    try:
        if not model_loader or not model_loader.kmeans_model:
            raise HTTPException(status_code=503, detail="KMeans model not loaded")
        if data_loader is None or data_loader.products_df is None or data_loader.products_df.empty:
            raise HTTPException(status_code=503, detail="Product data not loaded")
        
        def to_float(value: Any, default: float = 0.0) -> float:
            try:
                parsed = float(value)
                return parsed if pd.notna(parsed) else default
            except (TypeError, ValueError):
                return default

        df = data_loader.products_df.copy()
        
        # Calculate normalized features globally
        import math
        min_p, max_p = 1000.0, 72460000.0
        df['price_normalized'] = df['original_price'].apply(lambda x: min(1.0, max(0.0, (to_float(x) - min_p) / (max_p - min_p))) if (max_p - min_p) > 0 else 0.0)
        df['rating_normalized'] = df['original_rating'].apply(lambda x: min(1.0, max(0.0, to_float(x) / 5.0)))
        
        raw_pop = df.apply(lambda r: math.log1p(to_float(r.get('quantity_sold', 0)) * 0.7 + to_float(r.get('review_count', 0)) * 0.3), axis=1)
        min_pop = raw_pop.min()
        max_pop = raw_pop.max()
        if max_pop - min_pop > 0:
            df['popularity_score'] = (raw_pop - min_pop) / (max_pop - min_pop)
        else:
            df['popularity_score'] = 0.0

        # Filter by category if provided
        if category and category.strip():
            col = 'leaf_category' if 'leaf_category' in df.columns else 'category'
            df = df[df[col] == category.strip()]
            if df.empty:
                return {"success": True, "data": {
                    "cluster_summary": [], "blue_ocean_products": [],
                    "total_products": 0, "n_clusters": 5, "blue_ocean_count": 0,
                    "silhouette_score": 0.0, "max_popularity": 0.0,
                    "rating_threshold": 0.0, "market_avg_rating": 0.0,
                    "note": f"Không có sản phẩm nào trong danh mục '{category}'.",
                }}

        def safe_round(val: Any, decimals: int = 0, default: float = 0.0) -> float:
            import math
            try:
                fval = float(val)
                if pd.isna(fval) or math.isnan(fval) or math.isinf(fval):
                    return default
                return round(fval, decimals)
            except (TypeError, ValueError):
                return default

        def normalize_rating(row: pd.Series) -> float:
            original = to_float(row.get("original_rating"), 0.0)
            normalized = to_float(row.get("rating_normalized"), 0.0)
            if original > 0:
                return min(max(original, 0.0), 5.0)
            # Some datasets store normalized rating in 0-1 scale.
            if 0 < normalized <= 1.0:
                return min(max(normalized * 5.0, 0.0), 5.0)
            return min(max(normalized, 0.0), 5.0)

        if df.empty:
            silhouette = 0.464
            if model_loader and hasattr(model_loader, 'kmeans_metadata'):
                silhouette = model_loader.kmeans_metadata.get('metrics', {}).get('silhouette_score', silhouette)
            return {
                "success": True,
                "data": {
                    "cluster_summary": [],
                    "blue_ocean_products": [],
                    "total_products": 0,
                    "n_clusters": 5,
                    "blue_ocean_count": 0,
                    "silhouette_score": safe_round(silhouette, 4, 0.464),
                    "max_popularity": 0.0,
                    "note": "Không có đủ dữ liệu cho bộ lọc hiện tại.",
                },
            }

        df["effective_rating"] = df.apply(normalize_rating, axis=1)

        cluster_ids, cluster_names_col = [], []
        for _, row in df.iterrows():
            if 'cluster_id' in row and pd.notna(row['cluster_id']) and int(row['cluster_id']) >= 0:
                cid = int(row['cluster_id'])
                cname = row.get('cluster_name', model_loader.cluster_names.get(cid, f'Cluster {cid}'))
            else:
                cid, cname = model_loader.assign_cluster(
                    to_float(row.get('price_normalized', 0)),
                    to_float(row.get('rating_normalized', 0)),
                    to_float(row.get('popularity_score', 0)),
                )
            cluster_ids.append(cid)
            cluster_names_col.append(cname)
        df['cluster_id']   = cluster_ids
        df['cluster_name'] = cluster_names_col

        cluster_summary = []
        max_popularity = to_float(df['popularity_score'].max(), 10.0) if 'popularity_score' in df.columns else 10.0
        market_avg_rating = to_float(df['effective_rating'].mean(), 0.0) if not df.empty else 0.0
        rating_threshold = min(4.2, max(2.5, market_avg_rating - 0.4))
        pop_threshold = to_float(df['popularity_score'].quantile(0.6), 0.0) if 'popularity_score' in df.columns else 0.0
        avg_price_threshold = to_float(df['original_price'].mean(), 0.0) if not df.empty else 0.0

        for cid in sorted(df['cluster_id'].unique()):
            if cid < 0:
                continue
            sub = df[df['cluster_id'] == cid]
            avg_rating_orig = to_float(sub['effective_rating'].mean(), 0.0)
            avg_pop = to_float(sub['popularity_score'].mean(), 0.0)
            top3 = sub.nlargest(3, 'popularity_score')
            top_products = []
            for _, r in top3.iterrows():
                top_products.append({
                    'product_id': str(r['product_id']), 'name': str(r['name']),
                    'category': str(r['category']), 'price': safe_round(r['original_price'], 2, 0.0),
                    'rating': safe_round(r['original_rating'], 2, 0.0), 'quantity_sold': int(to_float(r['quantity_sold'], 0)),
                })
            
            mode_series = sub['category'].mode()
            top_cat = str(mode_series.iloc[0]) if not mode_series.empty else ''
            
            cluster_summary.append({
                'cluster_id': int(cid),
                'cluster_name': model_loader.cluster_names.get(cid, f'Cluster {cid}'),
                'product_count': int(len(sub)),
                'avg_price': safe_round(sub['original_price'].mean(), 0, 0.0),
                'avg_rating': safe_round(avg_rating_orig, 2, 0.0),
                'avg_popularity': safe_round(avg_pop, 3, 0.0),
                'avg_qty_sold': safe_round(sub['quantity_sold'].mean(), 0, 0.0),
                'top_category': top_cat,
                'is_blue_ocean': bool(avg_rating_orig <= rating_threshold and avg_pop >= pop_threshold),
                'top_products': top_products,
            })

        qty_q95 = to_float(df['quantity_sold'].quantile(0.95), 1.0) if 'quantity_sold' in df.columns else 1.0
        def product_opportunity(row: pd.Series) -> float:
            popularity = to_float(row.get('popularity_score'), 0.0)
            sold = to_float(row.get('quantity_sold'), 0.0)
            rating = to_float(row.get('effective_rating'), 0.0)
            pop_norm = popularity / max(max_popularity, 1.0)
            demand_norm = min(sold / max(qty_q95, 1.0), 1.0)
            quality_gap = max(rating_threshold - rating, 0.0) / max(rating_threshold, 1.0)
            return (0.5 * pop_norm + 0.3 * demand_norm + 0.2 * quality_gap) * 100

        df['product_opportunity_score'] = df.apply(product_opportunity, axis=1)
        blue_df = df[df['effective_rating'] <= (rating_threshold + 0.4)].nlargest(20, 'product_opportunity_score')
        if blue_df.empty:
            blue_df = df.nlargest(20, 'product_opportunity_score')
        blue_ocean_products = []
        for _, row in blue_df.iterrows():
            url = data_loader.resolve_product_url(row['product_id'], row['name'], row['category'])
            blue_ocean_products.append({
                'product_id': str(row['product_id']), 'name': str(row['name']),
                'category': str(row['category']), 'price': safe_round(row['original_price'], 2, 0.0),
                'rating': safe_round(row['effective_rating'], 2, 0.0), 'quantity_sold': int(to_float(row['quantity_sold'], 0)),
                'popularity_score': safe_round(row['popularity_score'], 3, 0.0),
                'opportunity_score': safe_round(row['product_opportunity_score'], 1, 0.0),
                'cluster_name': str(row['cluster_name']), 'url': url,
            })

        all_products_out = []
        for _, row in df.iterrows():
            url = data_loader.resolve_product_url(row['product_id'], row['name'], row['category'])
            all_products_out.append({
                'product_id': str(row['product_id']), 'name': str(row['name']),
                'category': str(row['category']), 'price': safe_round(row['original_price'], 2, 0.0),
                'rating': safe_round(row['effective_rating'], 2, 0.0), 'quantity_sold': int(to_float(row['quantity_sold'], 0)),
                'popularity_score': safe_round(row.get('popularity_score'), 3, 0.0),
                'opportunity_score': safe_round(row['product_opportunity_score'], 1, 0.0),
                'cluster_name': str(row['cluster_name']), 'url': url,
            })

        blue_ocean_count = int(((df['effective_rating'] <= rating_threshold) & (df['popularity_score'] >= pop_threshold)).sum()) if 'popularity_score' in df.columns else int((df['effective_rating'] <= rating_threshold).sum())
        silhouette = 0.464  # from model metadata: silhouette_score
        if model_loader and hasattr(model_loader, 'kmeans_metadata'):
            silhouette = model_loader.kmeans_metadata.get('metrics', {}).get('silhouette_score', silhouette)
        for c in cluster_summary:
            quality_gap = max(rating_threshold - c['avg_rating'], 0.0) / max(rating_threshold, 1.0)
            pop_norm = c['avg_popularity'] / max(max_popularity, 1.0)
            raw_opp = (0.7 * pop_norm + 0.3 * quality_gap) * 100
            c['opportunity_score'] = safe_round(raw_opp, 1, 0.0)
        return {'success': True, 'data': {
            'cluster_summary': cluster_summary,
            'blue_ocean_products': blue_ocean_products,
            'all_products': all_products_out,
            'total_products': int(len(df)),
            'n_clusters': 5,
            'blue_ocean_count': int(blue_ocean_count),
            'silhouette_score': safe_round(silhouette, 4, 0.464),
            'max_popularity': safe_round(max_popularity, 3, 10.0),
            'rating_threshold': safe_round(rating_threshold, 2, 4.0),
            'market_avg_rating': safe_round(market_avg_rating, 2, 4.0),
            'pop_threshold': safe_round(pop_threshold, 3, 5.0),
            'avg_price_threshold': safe_round(avg_price_threshold, 2, 0.0),
        }}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Market insight failed: {e}\n{tb}")
        return {"success": False, "error": str(e), "traceback": tb}


@app.get("/api/product-reviews/{product_id}")
async def get_product_reviews(product_id: str):
    if data_loader is None or data_loader.reviews_df is None or data_loader.reviews_df.empty:
        raise HTTPException(status_code=503, detail="Reviews data not loaded")
    
    try:
        df = data_loader.reviews_df
        pid = str(product_id).strip()
        reviews = df[df['product_id'].astype(str) == pid]
        
        result = []
        for _, row in reviews.head(50).iterrows():
            result.append({
                "rating": int(row.get("rating", 5)),
                "content": str(row.get("original_content", row.get("cleaned_content", ""))),
                "sentiment": str(row.get("sentiment_label", "")),
                "created_at": str(row.get("created_at", ""))
            })
            
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Reviews fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {
        "message": "Tiki RAG API",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "search": "POST /api/search",
            "batch": "POST /api/analyze-batch",
            "health": "GET /health"
        }
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        rag_engine_loaded=rag_engine is not None,
        data_loaded=data_loader is not None and not data_loader.products_df.empty,
        models_loaded={
            "kmeans": model_loader.kmeans_model is not None if model_loader else False,
            "prophet": model_loader.prophet_models is not None if model_loader else False,
            "phobert": model_loader.phobert_available if model_loader else False
        }
    )

@app.get("/api/categories")
async def get_categories():
    """Return sorted list of unique product categories from the loaded CSV data."""
    if data_loader is None or data_loader.products_df is None or data_loader.products_df.empty:
        return {"success": True, "categories": []}
    try:
        col = 'leaf_category' if 'leaf_category' in data_loader.products_df.columns else 'category'
        cats = sorted(data_loader.products_df[col].dropna().unique().tolist())
        return {"success": True, "categories": cats}
    except Exception as e:
        logger.error(f"get_categories failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search", response_model=SearchResponse)
async def search_products(
    request: SearchRequest,
    engine: SearchEngine = Depends(get_search_engine)
):
    """
    Search products by keyword (matches website expected format)
    
    Request:
    {
        "keyword": "tai nghe bluetooth",
        "market": "US",
        "limit": 20
    }
    
    Response:
    {
        "success": true,
        "data": {
            "products": [...],
            "ai_insight": "...",
            "total_found": 15
        }
    }
    """
    try:
        logger.info(f"🔍 Search request: '{request.keyword}' (limit: {request.limit})")
        
        # Search products
        # Bước 1: Tìm TẤT CẢ (không giới hạn)
        all_products = engine.search_products(
            keyword=request.keyword,
            limit=request.limit,       # = 9999 → lấy toàn bộ
            use_semantic=False
        )
        
        fallback_kw = None
        if len(all_products) == 0:
            from search_engine.normalizer import normalize
            from search_engine.synonym_map import detect_compound
            compound = detect_compound(normalize(request.keyword))
            if compound and "matched_phrase" in compound:
                fallback_kw = compound["matched_phrase"]
                logger.info(f"0 results, falling back to matched phrase: '{fallback_kw}'")
                all_products = engine.search_products(keyword=fallback_kw, limit=request.limit, use_semantic=False)

        # Bước 2: Detect context + filter dataset (no crawl; re-analyze on existing dataset)
        ctx = engine.analyze_contexts(
            keyword=request.keyword,
            products=all_products,
            selected_context=request.context_id,
        )
        filtered = ctx["filtered_products"]

        # Bước 3: Insight phân tích từ sản phẩm ĐÚNG NGỮ CẢNH (primary/selected)
        ai_insight = engine.generate_insight(products=filtered, keyword=request.keyword, include_ml_insights=True)
        if fallback_kw and filtered:
            ai_insight = f"⚠️ Không tìm thấy sản phẩm đúng chính xác với '{request.keyword}'. Dưới đây là đề xuất các sản phẩm '{fallback_kw}' liên quan nhất để bạn tham khảo.\n\n" + ai_insight

        # Bước 3.5: Analytics MUST use the full filtered dataset
        if filtered:
            total_revenue = sum(float(p.get("estimated_revenue", float(p.get("price", 0)) * float(p.get("boughtInLastMonth", 0)))) for p in filtered)
            total_sold = sum(int(p.get("boughtInLastMonth", 0)) for p in filtered)
            avg_price = sum(float(p.get("price", 0)) for p in filtered) / len(filtered)
            avg_rating = sum(float(p.get("rating", 0)) for p in filtered) / len(filtered)
        else:
            total_revenue = 0.0
            total_sold = 0
            avg_price = 0.0
            avg_rating = 0.0

        # Bước 4: Chỉ trả về display_limit sản phẩm cho UI
        return SearchResponse(success=True,data={
            "products": filtered[:request.display_limit],  # = 20 hiển thị (đúng ngữ cảnh)
            "ai_insight": ai_insight,
            "total_found": len(filtered),   # số thực tế (đúng ngữ cảnh)
            "analytics": {
                "total_products": len(filtered),
                "total_sold": total_sold,
                "total_revenue": round(total_revenue, 0),
                "avg_price": round(avg_price, 2),
                "avg_rating": round(avg_rating, 2),
            },
            "context": {
                "primary_context": ctx["primary_context"],
                "selected_context": ctx["selected_context"],
                "primary_context_label": ctx.get("primary_context_label"),
                "selected_context_label": ctx.get("selected_context_label"),
                "context_counts": ctx["context_counts"],
                "suggestions": ctx["suggestions"],
                "total_found_before_filter": len(all_products),
                "total_found_after_filter": len(filtered),
            },
        })
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze-batch", response_model=SearchResponse)
async def analyze_batch(
    file: UploadFile = File(...),
    engine: SearchEngine = Depends(get_search_engine)
):
    """
    Analyze batch of keywords from CSV file
    
    CSV format:
    keyword
    tai nghe
    laptop
    ...
    
    Response same as /api/search
    """
    try:
        logger.info(f"📂 Batch analysis request: {file.filename}")
        
        # Read CSV or Excel file
        contents = await file.read()
        filename = (file.filename or '').lower()

        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            try:
                df = pd.read_excel(io.BytesIO(contents))
            except ImportError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Excel support requires 'openpyxl'. Please upload CSV or install openpyxl."
                ) from exc
        else:
            # Default to CSV to keep backward compatibility with current UI.
            # Try common encodings used by Excel/Windows exports so Vietnamese text is preserved.
            csv_text = None
            last_error = None
            for encoding in ('utf-8-sig', 'utf-8', 'cp1258', 'cp1252', 'latin1'):
                try:
                    csv_text = contents.decode(encoding)
                    break
                except UnicodeDecodeError as exc:
                    last_error = exc

            if csv_text is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not decode CSV file. Please save it as UTF-8 CSV. Details: {last_error}"
                )

            try:
                df = pd.read_csv(StringIO(csv_text))
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid CSV format: {exc}"
                ) from exc
        
        if 'keyword' not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="File must have a 'keyword' column"
            )
        
        keywords = df['keyword'].dropna().astype(str).tolist()
        
        if not keywords:
            raise HTTPException(
                status_code=400,
                detail="No valid keywords found in CSV"
            )
        
        # Analyze batch
        result = engine.analyze_batch(keywords=keywords, limit_per_keyword=5)
        
        return SearchResponse(
            success=True,
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_assistant(request: ChatRequest):
    if assistant is None:
        raise HTTPException(
            status_code=503,
            detail="AI Business Assistant is not initialized."
        )
    try:
        res = assistant.chat(session_id=request.session_id, message=request.message, context_id=request.context_id)
        return res
    except Exception as e:
        logger.error(f"AI Chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/chat/{session_id}")
async def delete_chat_session(session_id: str):
    if assistant is None:
        raise HTTPException(
            status_code=503,
            detail="AI Business Assistant is not initialized."
        )
    try:
        if session_id in assistant.sessions:
            del assistant.sessions[session_id]
            logger.info(f"🗑️ Deleted chat session: {session_id}")
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to delete chat session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get API statistics"""
    stats = {
        "data": data_loader.get_stats() if data_loader else {},
        "models": model_loader.get_model_stats() if model_loader else {},
        "rag_documents": rag_engine.get_document_count() if rag_engine else 0
    }
    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
