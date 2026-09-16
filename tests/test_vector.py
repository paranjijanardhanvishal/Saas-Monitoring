import pytest
from app.metadata.vector import LocalVectorDatabase, compute_tf, cosine_similarity

def test_compute_tf():
    tf = compute_tf("hello world hello")
    assert tf["hello"] == 2/3
    assert tf["world"] == 1/3

import math

def test_cosine_similarity():
    vec1 = {"hello": 1, "world": 1}
    vec2 = {"hello": 1, "world": 1}
    assert math.isclose(cosine_similarity(vec1, vec2), 1.0, rel_tol=1e-9)
    
    vec3 = {"foo": 1}
    assert math.isclose(cosine_similarity(vec1, vec3), 0.0, rel_tol=1e-9)

def test_local_vector_database():
    vdb = LocalVectorDatabase()
    vdb.insert("doc1", "confidential salary report")
    vdb.insert("doc2", "public holiday schedule")
    vdb.insert("doc3", "salary and bonus report")
    
    results = vdb.search("salary report", top_k=2)
    assert len(results) == 2
    
    # doc1 and doc3 should be the most similar
    doc_ids = [r[0] for r in results]
    assert "doc1" in doc_ids
    assert "doc3" in doc_ids
    assert "doc2" not in doc_ids
