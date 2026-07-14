import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter


class PDFChunker:
    
    def __init__(self, chunk_size=500, chunk_overlap=100):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap = chunk_overlap
        )

    def extract_text(self, pdf_path):
        """
        Reads a PDF and extracts text page by page.
        Returns a list of dictionaries.
        """

        doc = fitz.open(pdf_path)

        pages = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()

            if text.strip():
                pages.append({
                    "page": page_num + 1,
                    "text": text
                })

        return pages

    def chunk_document(self, pdf_path):
        """
        Splits the extracted text into chunks while preserving page numbers.
        """

        pages = self.extract_text(pdf_path)

        chunks = []

        chunk_id = 0

        for page in pages:

            split_text = self.splitter.split_text(page["text"])

            for chunk in split_text:

                chunks.append({
                    "chunk_id": chunk_id,
                    "page": page["page"],
                    "text": chunk
                })

                chunk_id += 1

        return chunks