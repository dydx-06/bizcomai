import faiss
import numpy as np


class VectorStore:

    def __init__(self):

        self.index = None
        self.chunks = []

    def build(self, embedded_chunks):
        """
        Builds a FAISS index from embedded chunks.
        """

        self.chunks = embedded_chunks

        vectors = np.array(
            [chunk["embedding"] for chunk in embedded_chunks],
            dtype=np.float32
        )

        faiss.normalize_L2(vectors)

        dimension = vectors.shape[1]

        self.index = faiss.IndexFlatIP(dimension)

        self.index.add(vectors)

        print(f"Indexed {self.index.ntotal} chunks.")

    def search(self, query_embedding, top_k=10):
        """
        Returns the most similar chunks.
        """

        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)

        distances, indices = self.index.search(query, top_k)

        results = []

        for i in indices[0]:
            results.append(self.chunks[i])

        return results