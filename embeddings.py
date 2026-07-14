from sentence_transformers import SentenceTransformer


class EmbeddingGenerator:
    def __init__(self):
        print("Loading embedding model...")

        self.model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

        print("Model loaded!")

    def embed_text(self, text):
        """
        Generate embedding for a single text.
        """

        embedding = self.model.encode(
            text,
            convert_to_numpy=True
        )

        return embedding

    def embed_chunks(self, chunks):
        """
        Generate embeddings for every chunk.
        """

        embedded_chunks = []

        for chunk in chunks:

            vector = self.embed_text(chunk["text"])

            chunk["embedding"] = vector

            embedded_chunks.append(chunk)

        return embedded_chunks