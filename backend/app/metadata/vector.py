import math
from collections import Counter
import re

def compute_tf(text: str):
    """
    Computes Term Frequencies (TF) for a given text.
    Acts as our lightweight 'vectorizer'.
    """
    words = re.findall(r'\w+', text.lower())
    if not words:
        return {}
    
    count = Counter(words)
    total_words = len(words)
    tf = {word: count[word] / total_words for word in count}
    return tf

def cosine_similarity(vec1: dict, vec2: dict) -> float:
    """
    Computes cosine similarity between two TF vectors.
    Simulates a Vector Database similarity search (e.g., Pinecone).
    """
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])

    sum1 = sum([val**2 for val in vec1.values()])
    sum2 = sum([val**2 for val in vec2.values()])
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    if not denominator:
        return 0.0
    else:
        return float(numerator / denominator)

class LocalVectorDatabase:
    """
    A lightweight, in-memory local alternative to Pinecone for the BTech prototype.
    Supports inserting vectors (TF maps) and finding the top-K similar documents.
    """
    def __init__(self):
        self.index = {}

    def insert(self, doc_id: str, text: str):
        self.index[doc_id] = compute_tf(text)
        
    def search(self, query_text: str, top_k: int = 3):
        query_vec = compute_tf(query_text)
        results = []
        for doc_id, doc_vec in self.index.items():
            sim = cosine_similarity(query_vec, doc_vec)
            if sim > 0:
                results.append((doc_id, sim))
                
        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

# Global instance for the application lifecycle
local_vdb = LocalVectorDatabase()
