# ============================================================
# RAG ENGINE - Core RAG Logic
# ============================================================

import time
import logging
from typing import Dict, Any, List

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain.vectorstores import Chroma
from langchain.embeddings import SentenceTransformerEmbeddings
import google.generativeai as genai
from gemini_helper import gemini_manager

logger = logging.getLogger(__name__)

class RAGEngine:
    """
    RAG Engine for Tiki e-commerce Q&A
    
    Combines:
    - ChromaDB for vector storage
    - Sentence-Transformers for embeddings
    - Google Gemini for generation
    """
    
    def __init__(
        self,
        gemini_api_key: str,
        chroma_db_path: str = "./chroma_db",
        embedding_model_name: str = "paraphrase-multilingual-mpnet-base-v2"
    ):
        """
        Initialize RAG engine
        
        Args:
            gemini_api_key: Google Gemini API key
            chroma_db_path: Path to ChromaDB database
            embedding_model_name: Sentence-Transformers model name
        """
        logger.info("🔧 Initializing RAG Engine...")
        
        self.chroma_db_path = chroma_db_path
        self.embedding_model_name = embedding_model_name
        
        # 1. Initialize embedding model
        logger.info(f"   Loading embedding model: {embedding_model_name}...")
        self.embedding_model = SentenceTransformerEmbeddings(
            model_name=embedding_model_name
        )
        logger.info("   ✅ Embedding model loaded")
        
        # 2. Load ChromaDB vector store
        logger.info(f"   Loading vector store from: {chroma_db_path}...")
        try:
            self.chroma_client = chromadb.PersistentClient(path=chroma_db_path)
            
            self.vector_store = Chroma(
                client=self.chroma_client,
                collection_name="tiki_rag",
                embedding_function=self.embedding_model
            )
            
            doc_count = self.vector_store._collection.count()
            logger.info(f"   ✅ Vector store loaded ({doc_count:,} documents)")
            
        except Exception as e:
            logger.error(f"   ❌ Failed to load vector store: {e}")
            raise
        
        # 3. Configure Gemini API
        logger.info("   Configuring Gemini API via GeminiManager...")
        try:
            self.model_name = "gemini-flash-latest"
            self.model = gemini_manager.get_model(self.model_name)
            logger.info(f"   ✅ Gemini configured (model: {self.model_name})")
        except Exception as e:
            logger.error(f"   ❌ Failed to configure Gemini: {e}")
            raise
        
        logger.info("✅ RAG Engine ready!")
    
    def get_document_count(self) -> int:
        """Get total number of documents in vector store"""
        try:
            return self.vector_store._collection.count()
        except:
            return 0
    
    def ask(
        self,
        query: str,
        k: int = 5,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Ask a question using RAG pipeline
        
        Args:
            query: User question (Vietnamese or English)
            k: Number of documents to retrieve
            verbose: Include detailed logs
        
        Returns:
            Dictionary with answer, sources, and metadata
        """
        start_time = time.time()
        
        if verbose:
            logger.info(f"🔍 Query: {query}")
        
        # Step 1: Retrieval (semantic search)
        retrieval_start = time.time()
        docs = self.vector_store.similarity_search(query, k=k)
        retrieval_time = time.time() - retrieval_start
        
        if verbose:
            logger.info(f"   Retrieved {len(docs)} documents in {retrieval_time:.2f}s")
        
        # Step 2: Build context from retrieved documents
        context = "\n\n".join([
            f"Document {i+1}:\n{doc.page_content}" 
            for i, doc in enumerate(docs)
        ])
        
        # Step 3: Build prompt
        prompt = f"""You are a helpful assistant analyzing Tiki e-commerce data. Answer the question based ONLY on the context provided. If the context doesn't contain enough information, say so.

Context:
{context}

Question: {query}

Answer (be concise and factual):"""
        
        # Step 4: Generate answer with Gemini
        generation_start = time.time()
        
        def run_gen():
            model = gemini_manager.get_model(self.model_name)
            return model.generate_content(prompt)
            
        response = gemini_manager.execute_with_retry(run_gen)
        generation_time = time.time() - generation_start
        
        total_time = time.time() - start_time
        
        if verbose:
            logger.info(f"   Generated answer in {generation_time:.2f}s")
            logger.info(f"   Total time: {total_time:.2f}s")
        
        # Format sources
        sources = []
        for doc in docs:
            source_info = doc.metadata.copy()
            source_info['content_preview'] = doc.page_content[:200]
            sources.append(source_info)
        
        return {
            "query": query,
            "answer": response.text,
            "sources": sources,
            "context": context,
            "num_docs": len(docs),
            "retrieval_time": retrieval_time,
            "generation_time": generation_time,
            "total_time": total_time
        }
