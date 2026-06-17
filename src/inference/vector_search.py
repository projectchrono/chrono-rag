from __future__ import annotations

import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from pymongo import MongoClient

from inference.llm import LLM

load_dotenv()

_MONGO_URI = "mongodb://localhost:27017/?directConnection=true"
_DB_NAME = "chrono_rag"
_COLLECTION_NAME = "chunks"
_TOP_K = 5

with open(os.path.join(os.path.dirname(__file__), "migration_prompt.md"), "r") as f:
    _VERSION_DIFF_PROMPT = f.read()

_SYSTEM_PROMPT = f"""
    You are an expert in Chrono and PyChrono, the physics-based simulation libraries. "
    "Answer the user's question using only the provided `retrieved_data` from the vector store. "
    Explain the user by analysing the `retrieved_data` and the `user_query` and frame the answers accordingly, if the suer asks for explanation/clarification.
    Provide the code by analysing and modifying according to the user's request if the user asks for code.
    Your response SHOULD NOT contain the word `retrieved_data`.


    You need to keep these in mind during code generation:
    1. The retrieved data contains code that are of version 9.0.0 of PyChrono. 
    You can use the following prompt to analyze the version difference and generate code that is compatible with PyChrono version 10.0.0: 

    {_VERSION_DIFF_PROMPT}
"""


def _get_collection():
    client = MongoClient(_MONGO_URI)
    return client[_DB_NAME][_COLLECTION_NAME]


def search(query: str, top_k: int = _TOP_K, model: str = LLM.ANTHROPIC_MODEL) -> str:
    embedder = OpenAIEmbeddings(model="text-embedding-3-small")
    query_vector = embedder.embed_query(query)

    collection = _get_collection()
    results = collection.aggregate([
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": top_k * 10,
                "limit": top_k,
            }
        },
        {
            "$project": {
                "_id": 0,
                "content": 1,
                "answer": 1,
                "chunk_name": 1,
                "file_path": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
        {"$match": {"score": {"$gte": 0.75}}}
    ])

    chunks = list(results)
    context_parts = []
    for chunk in chunks:
        part = f"### {chunk.get('chunk_name', '')} ({chunk.get('file_path', '')})\n"
        if chunk.get("answer"):
            part += f"{chunk['answer']}\n"
        part += f"{chunk['content']}"
        context_parts.append(part)

    context = "\n\n".join(context_parts)

    llm = LLM(model=model)
    system = f"{_SYSTEM_PROMPT}\n\nretrieved_data:\n{context}"
    return llm.complete(system=system, user=f"user_query: {query}")
