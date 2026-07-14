from chunker import PDFChunker
from embeddings import EmbeddingGenerator
from vector_store import VectorStore
from qa import QAEngine


class RAGService:
    def __init__(self):
        """
        Initialize all components of the RAG pipeline.
        """

        self.chunker = PDFChunker()
        self.embedder = EmbeddingGenerator()
        self.vector_store = VectorStore()
        self.qa_engine = QAEngine()

        self.document_loaded = False

    def load_document(self, pdf_path):
        """
        Loads a PDF, chunks it, generates embeddings,
        and stores everything inside the FAISS index.
        """

        print("Loading document...")

        chunks = self.chunker.chunk_document(pdf_path)

        print(f"Created {len(chunks)} chunks.")

        embedded_chunks = self.embedder.embed_chunks(chunks)

        print("Generated embeddings.")

        self.vector_store.build(embedded_chunks)

        print("FAISS index built successfully.")

        self.document_loaded = True

    def ask_question(self, question, lang_choice="en"):
        """
        Retrieves relevant chunks and generates an answer.
        """

        if not self.document_loaded:
            raise Exception("No document has been loaded.")

        query_embedding = self.embedder.embed_text(question)

        retrieved_chunks = self.vector_store.search(
            query_embedding,
            top_k=5
        )

        answer = self.qa_engine.ask(
            question,
            retrieved_chunks,
            lang_choice
        )

        return {
            "question": question,
            "answer": answer,
            "sources": [
                chunk["page"] for chunk in retrieved_chunks
            ],
            "retrieved_chunks": retrieved_chunks
        }

    def clear(self):
        """
        Clears the current document index.
        """

        self.vector_store = VectorStore()
        self.document_loaded = False

        print("Vector store cleared.")
