"""
WebRAG Content Vectorizer Service
Handles intelligent chunking, embedding, and vector storage of web content
"""

import asyncio
import hashlib
import httpx
import json
import re
import time
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import chromadb
from chromadb.config import Settings


class ContentResult:
    """Container for extracted web content"""
    def __init__(self, url: str, title: str, text: str, timestamp: float = None):
        self.url = url
        self.title = title
        self.text = text
        self.timestamp = timestamp or time.time()
        self.content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]


class RAGResult:
    """Container for RAG search results"""
    def __init__(self, query: str, retrieved_chunks: List[str], sources: List[Dict], 
                 generated_response: str, similarity_scores: List[float] = None):
        self.query = query
        self.retrieved_chunks = retrieved_chunks
        self.sources = sources
        self.generated_response = generated_response
        self.similarity_scores = similarity_scores or []


class ContentVectorizer:
    """Intelligent content vectorization and RAG search engine"""
    
    def __init__(self, ollama_base_url: str = None, 
                 embedding_model: str = "nomic-embed-text:latest",
                 chroma_path: str = "./chroma_db"):
        import os
        if ollama_base_url is None:
            ollama_base_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_base_url = ollama_base_url
        self.embedding_model = embedding_model
        self.chroma_path = chroma_path
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Create or get collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="web_content",
            metadata={"description": "WebRAG content embeddings"}
        )
    
    async def get_ollama_embedding(self, text: str, task_prefix: str = "search_document") -> List[float]:
        """Get embeddings from Ollama using nomic-embed-text"""
        # Add task prefix as required by nomic-embed-text
        prefixed_text = f"{task_prefix}: {text}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.ollama_base_url}/api/embeddings",
                    json={
                        "model": self.embedding_model,
                        "prompt": prefixed_text
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result["embedding"]
            except Exception as e:
                print(f"❌ Embedding failed for text: {text[:100]}... Error: {e}")
                raise
    
    def smart_chunk(self, text: str, max_chunk_size: int = 512, overlap: int = 50) -> List[str]:
        """Intelligent text chunking with semantic boundaries"""
        if not text or len(text.strip()) == 0:
            return []
        
        # Clean and normalize text
        text = re.sub(r'\s+', ' ', text.strip())
        
        # If text is small enough, return as single chunk
        if len(text) <= max_chunk_size:
            return [text]
        
        chunks = []
        
        # Method 1: Sentence-based chunking (preferred)
        try:
            # Simple sentence splitting using multiple delimiters
            sentences = re.split(r'(?<=[.!?])\s+', text)
            current_chunk = ""
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                # Check if adding this sentence would exceed limit
                test_chunk = current_chunk + (" " if current_chunk else "") + sentence
                
                if len(test_chunk) <= max_chunk_size:
                    current_chunk = test_chunk
                else:
                    # Save current chunk if it has content
                    if current_chunk:
                        chunks.append(current_chunk)
                    
                    # Handle sentences longer than max_chunk_size
                    if len(sentence) > max_chunk_size:
                        # Split long sentence by words
                        words = sentence.split()
                        temp_chunk = ""
                        for word in words:
                            test_temp = temp_chunk + (" " if temp_chunk else "") + word
                            if len(test_temp) <= max_chunk_size:
                                temp_chunk = test_temp
                            else:
                                if temp_chunk:
                                    chunks.append(temp_chunk)
                                temp_chunk = word
                        if temp_chunk:
                            current_chunk = temp_chunk
                    else:
                        current_chunk = sentence
            
            # Add the last chunk
            if current_chunk:
                chunks.append(current_chunk)
        
        except Exception:
            # Fallback: Fixed-size overlapping windows
            chunks = self._fixed_size_chunk(text, max_chunk_size, overlap)
        
        # Ensure no empty chunks
        chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
        
        return chunks
    
    def _fixed_size_chunk(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Fallback: Fixed-size chunking with overlap"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to end at word boundary
            if end < len(text) and not text[end].isspace():
                last_space = chunk.rfind(' ')
                if last_space > chunk_size * 0.7:  # Only if we don't lose too much
                    chunk = chunk[:last_space]
                    end = start + last_space
            
            chunks.append(chunk.strip())
            
            # Move start position with overlap
            start = max(start + chunk_size - overlap, end)
            
            if start >= len(text):
                break
        
        return [chunk for chunk in chunks if chunk.strip()]
    
    async def process_content(self, content: ContentResult) -> Dict[str, Any]:
        """Process and store content with embeddings"""
        print(f"   🧠 Processing content for embedding: {content.title}")
        
        try:
            # Check if content already exists
            existing = self.collection.get(
                where={"content_hash": content.content_hash}
            )
            
            if existing and len(existing['documents']) > 0:
                print(f"   ♻️  Content already vectorized: {content.title}")
                return {
                    "status": "exists",
                    "chunks": len(existing['documents']),
                    "content_hash": content.content_hash
                }
            
            # Chunk the content intelligently
            chunks = self.smart_chunk(content.text, max_chunk_size=512)
            
            if not chunks:
                print(f"   ⚠️  No chunks generated for: {content.title}")
                return {"status": "no_chunks", "content_hash": content.content_hash}
            
            print(f"   ✂️  Generated {len(chunks)} chunks")
            
            # Generate embeddings for all chunks
            embeddings = []
            for i, chunk in enumerate(chunks):
                try:
                    embedding = await self.get_ollama_embedding(chunk)
                    embeddings.append(embedding)
                    print(f"   📊 Embedded chunk {i+1}/{len(chunks)}")
                except Exception as e:
                    print(f"   ❌ Failed to embed chunk {i+1}: {e}")
                    continue
            
            if not embeddings:
                print(f"   ❌ No embeddings generated for: {content.title}")
                return {"status": "embedding_failed", "content_hash": content.content_hash}
            
            # Store in ChromaDB
            chunk_ids = [f"{content.content_hash}_{i}" for i in range(len(chunks))]
            metadatas = [{
                "url": content.url,
                "title": content.title,
                "chunk_id": i,
                "content_hash": content.content_hash,
                "timestamp": content.timestamp,
                "total_chunks": len(chunks)
            } for i in range(len(chunks))]
            
            self.collection.add(
                ids=chunk_ids,
                documents=chunks[:len(embeddings)],  # Only add chunks that have embeddings
                embeddings=embeddings,
                metadatas=metadatas[:len(embeddings)]
            )
            
            print(f"   ✅ Stored {len(embeddings)} chunks in vector DB")
            
            return {
                "status": "success",
                "chunks": len(embeddings),
                "content_hash": content.content_hash,
                "url": content.url,
                "title": content.title
            }
            
        except Exception as e:
            print(f"   ❌ Content processing failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "content_hash": content.content_hash
            }
    
    async def rag_search(self, query: str, max_results: int = 5, 
                        similarity_threshold: float = 0.1) -> RAGResult:
        """Perform RAG search with context retrieval"""
        print(f"🔍 RAG Search: {query}")
        
        try:
            # Generate query embedding with search_query prefix
            query_embedding = await self.get_ollama_embedding(query, "search_query")
            
            # Search similar content in ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=max_results,
                include=["documents", "metadatas", "distances", "embeddings"]
            )
            
            if not results['documents'] or not results['documents'][0]:
                return RAGResult(
                    query=query,
                    retrieved_chunks=[],
                    sources=[],
                    generated_response="No relevant information found in the knowledge base."
                )
            
            # Calculate cosine similarities with normalization
            filtered_chunks = []
            filtered_sources = []
            similarity_scores = []
            
            # Get stored embeddings for similarity calculation
            stored_embeddings = results.get('embeddings', [None])[0] if 'embeddings' in results else None
            
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0], 
                results['distances'][0]
            )):
                # Calculate proper cosine similarity
                if stored_embeddings is not None and len(stored_embeddings) > i:
                    stored_emb = np.array(stored_embeddings[i])
                    query_emb = np.array(query_embedding)
                    
                    # Normalize embeddings
                    stored_norm = stored_emb / (np.linalg.norm(stored_emb) + 1e-8)
                    query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-8)
                    
                    # Calculate cosine similarity
                    cosine_similarity = np.dot(query_norm, stored_norm)
                    similarity = float(cosine_similarity)
                else:
                    # Fallback: convert ChromaDB distance to similarity (lower distance = higher similarity)
                    similarity = max(0, 1 - distance)
                
                print(f"   📊 Chunk {i+1}: similarity = {similarity:.3f}")
                
                if similarity >= similarity_threshold:
                    filtered_chunks.append(doc)
                    filtered_sources.append(metadata)
                    similarity_scores.append(similarity)
            
            if not filtered_chunks:
                return RAGResult(
                    query=query,
                    retrieved_chunks=[],
                    sources=[],
                    generated_response="No sufficiently relevant information found in the knowledge base."
                )
            
            # Build context from retrieved chunks
            context = "\n\n".join([
                f"Source: {meta['title']} (URL: {meta['url']})\nContent: {chunk}"
                for chunk, meta in zip(filtered_chunks, filtered_sources)
            ])
            
            print(f"📋 Retrieved {len(filtered_chunks)} relevant chunks")
            
            # For now, return structured result without LLM generation
            # The SmartOllamaChat will handle the final response generation
            return RAGResult(
                query=query,
                retrieved_chunks=filtered_chunks,
                sources=filtered_sources,
                generated_response="",  # Will be filled by the chat interface
                similarity_scores=similarity_scores
            )
            
        except Exception as e:
            print(f"❌ RAG search failed: {e}")
            return RAGResult(
                query=query,
                retrieved_chunks=[],
                sources=[],
                generated_response=f"Search failed: {e}",
                similarity_scores=[]
            )
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get vectorstore statistics"""
        try:
            count = self.collection.count()
            
            # Get unique sources
            all_metadata = self.collection.get(include=["metadatas"])
            unique_urls = set()
            unique_titles = set()
            
            for metadata in all_metadata.get('metadatas', []):
                unique_urls.add(metadata.get('url', ''))
                unique_titles.add(metadata.get('title', ''))
            
            return {
                "total_chunks": count,
                "unique_sources": len(unique_urls),
                "unique_titles": len(unique_titles),
                "embedding_model": self.embedding_model,
                "collection_name": self.collection.name
            }
        except Exception as e:
            return {
                "error": str(e),
                "total_chunks": 0,
                "unique_sources": 0
            }


# Export classes for use in other modules
__all__ = ['ContentVectorizer', 'ContentResult', 'RAGResult']