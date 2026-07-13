# ============================================================
# MODEL LOADER - Load All Trained Models
# ============================================================

import csv
import logging
import math
import pickle
from pathlib import Path
from typing import Dict, Any, Optional
import os

# Import pyspark stub FIRST to handle pickle compatibility
try:
    import pyspark_stub
except ImportError:
    pass

logger = logging.getLogger(__name__)

class ModelLoader:
    """
    Load and manage all trained models:
    - KMeans (clustering)
    - Prophet (forecasting)
    - PhoBERT (sentiment - config only)
    - ChromaDB already loaded by RAGEngine
    """
    
    def __init__(self, models_dir: str = "./models"):
        """
        Initialize model loader
        
        Args:
            models_dir: Path to models directory
        """
        self.models_dir = Path(models_dir)
        self.kmeans_model = None
        self.prophet_models = None
        self.prophet_metadata = None
        self.prophet_forecasts = None
        self.phobert_available = False
        self.cluster_centroids: Dict[int, Dict[str, float]] = {}
        self.cluster_names: Dict[int, str] = {}
        
        self._load_all_models()
    
    def _load_all_models(self):
        """Load all available models"""
        logger.info("🤖 Loading trained models...")
        
        # 1. Load KMeans
        self._load_kmeans()
        
        # 2. Load Prophet
        self._load_prophet()
        
        # 3. Check PhoBERT availability
        self._check_phobert()
    
    def _load_kmeans(self):
        """Load KMeans model from pkl, then load cluster names from CSV."""
        kmeans_dir = self.models_dir / "KMeans_CLustering"

        # --- Load cluster names/centroids from CSV ---
        csv_path = kmeans_dir / "cluster_summary.csv"
        if csv_path.exists():
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = list(csv.reader(f))

                headers = reader[0]
                col_map = {name.strip(): i for i, name in enumerate(headers)}

                price_col  = col_map.get('avg_price')
                rating_col = col_map.get('avg_rating')
                pop_col    = col_map.get('avg_popularity')

                if None not in (price_col, rating_col, pop_col):
                    for row in reader[1:]:
                        if not row or not row[0].strip().isdigit():
                            continue
                        cid = int(row[0].strip())
                        self.cluster_centroids[cid] = {
                            'price':  float(row[price_col]),
                            'rating': float(row[rating_col]),
                            'pop':    float(row[pop_col]),
                        }
                logger.info(f"   ✅ KMeans CSV centroids loaded ({len(self.cluster_centroids)} clusters)")
            except Exception as e:
                logger.warning(f"   ⚠️  KMeans CSV parse failed: {e}")

        self.cluster_names = {
            0: "Sản phẩm phổ biến",
            1: "Sản phẩm kém nổi bật",
            2: "Sản phẩm tiêu chuẩn",
            3: "Sản phẩm cực hot",
        }

        # --- Load pkl model ---
        try:
            pkl_files = sorted(kmeans_dir.glob("kmeans_model_*.pkl"))
            if pkl_files:
                with open(pkl_files[-1], 'rb') as f:
                    self.kmeans_model = pickle.load(f)
                logger.info(f"   ✅ KMeans pkl loaded: {pkl_files[-1].name}")
            elif self.cluster_centroids:
                self.kmeans_model = True  # fallback: centroids only
                logger.info("   ✅ KMeans using CSV centroids (no pkl)")
            else:
                logger.warning("   ⚠️  KMeans: no pkl and no CSV found")
        except Exception as e:
            logger.error(f"   ❌ Failed to load KMeans pkl: {e}")
            if self.cluster_centroids:
                self.kmeans_model = True
    
    def _load_prophet(self):
        """Load Prophet forecasts pkl from Prophet_models/ directory."""
        try:
            prophet_dir = self.models_dir / "Prophet_models"
            if not prophet_dir.exists():
                logger.warning("   ⚠️  Prophet_models directory not found")
                return

            # Load future forecasts
            forecast_files = sorted(prophet_dir.glob("future_forecasts_*.pkl"))
            if forecast_files:
                with open(forecast_files[-1], 'rb') as f:
                    self.prophet_forecasts = pickle.load(f)
                logger.info(f"   ✅ Prophet forecasts loaded: {forecast_files[-1].name} ({len(self.prophet_forecasts)} products)")

            # Load metadata
            metadata_files = sorted(prophet_dir.glob("metadata_*.pkl"))
            if metadata_files:
                with open(metadata_files[-1], 'rb') as f:
                    self.prophet_metadata = pickle.load(f)
                logger.info(f"   ✅ Prophet metadata loaded: {metadata_files[-1].name}")

        except Exception as e:
            logger.error(f"   ❌ Failed to load Prophet: {e}")

    
    def _check_phobert(self):
        """Check if PhoBERT configs are available"""
        try:
            phobert_dir = self.models_dir / "PhoBert"
            if not phobert_dir.exists():
                phobert_dir = self.models_dir / "phobert"
            if not phobert_dir.exists():
                phobert_dir = self.models_dir / "Phobert_model"
            
            if phobert_dir.exists():
                config_path = phobert_dir / "config.json"
                if config_path.exists():
                    self.phobert_available = True
                    logger.info(f"   ✅ PhoBERT config found (base model will be used)")
                else:
                    logger.warning("   ⚠️  PhoBERT config not found")
            else:
                logger.warning("   ⚠️  PhoBERT directory not found")
                
        except Exception as e:
            logger.error(f"   ❌ Failed to check PhoBERT: {e}")
    def assign_cluster(self, price_normalized: float, rating_normalized: float, popularity_score: float):
        """
        Assign a product to the nearest KMeans cluster.
        Uses sklearn predict() if pkl model loaded, otherwise Euclidean distance to CSV centroids.
        Returns (cluster_id, cluster_name). Returns (-1, 'N/A') if not loaded.
        """
        if self.kmeans_model is None:
            return -1, "N/A"

        # If a real sklearn model is loaded (not the bool sentinel)
        if self.kmeans_model is not True:
            try:
                import numpy as np
                features = np.array([[price_normalized, rating_normalized, popularity_score]])
                cid = int(self.kmeans_model.predict(features)[0])
                return cid, self.cluster_names.get(cid, f"Cluster {cid}")
            except Exception as e:
                logger.debug(f"sklearn predict failed, falling back to centroids: {e}")

        # Fallback: Euclidean distance to CSV centroids
        if not self.cluster_centroids:
            return -1, "N/A"
        best_id, best_dist = -1, float('inf')
        for cid, c in self.cluster_centroids.items():
            dist = math.sqrt(
                (price_normalized  - c['price'])  ** 2 +
                (rating_normalized - c['rating']) ** 2 +
                (popularity_score  - c['pop'])    ** 2
            )
            if dist < best_dist:
                best_dist = dist
                best_id = cid
        return best_id, self.cluster_names.get(best_id, f"Cluster {best_id}")

    def get_model_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded models"""
        return {
            'kmeans_loaded': bool(self.kmeans_model),
            'prophet_loaded': self.prophet_forecasts is not None,
            'prophet_num_models': len(self.prophet_forecasts) if self.prophet_forecasts else 0,
            'phobert_available': self.phobert_available
        }
