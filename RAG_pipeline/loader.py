import os
import pymupdf4llm
from typing import Union, List, Dict, Any, Optional

class PDFParserLoader:
    def __init__(self, output_format: str = "markdown"):
        """
        :param output_format: Choice between 'markdown' or 'json'
        """
        self.output_format = output_format.lower()

    def parse_pdf(self, pdf_path: str, pages: Optional[List[int]] = None) -> Union[str, List[Dict[str, Any]]]:
        """
        Extracts specific pages from PDF.
        
        :param pdf_path: Absolute or relative path to the PDF file.
        :param pages: Optional list of 0-based page numbers (e.g., [0, 1, 2] for pages 1-3).
                      If None, parses the entire document.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

        if self.output_format == "json":
            # Returns a list of dictionaries (page by page metadata & text)
            return pymupdf4llm.to_markdown(pdf_path, pages=pages, page_chunks=True)
        else:
            # Returns clean Github-Flavored Markdown string
            return pymupdf4llm.to_markdown(pdf_path, pages=pages)

    def parse_text_file(self, file_path: str) -> str:
        """Reads plain text or markdown files directly."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at: {file_path}")
            
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def load(self, file_path: str, pages: Optional[List[int]] = None) -> Union[str, List[Dict[str, Any]]]:
        """
        Universal entry point to load documents.
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            return self.parse_pdf(file_path, pages=pages)
        elif ext in [".txt", ".md", ".markdown"]:
            return self.parse_text_file(file_path)
        else:
            raise ValueError(f"Unsupported file format: '{ext}'. Supported formats: .pdf, .txt, .md")