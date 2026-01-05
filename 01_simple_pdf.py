"""
Simple PDF Parsing with Docling - Quick Start
==============================================

This script demonstrates the most basic usage of Docling:
converting a PDF to Markdown.

Why Docling?
- Handles complex PDFs with tables, images, and multi-column layouts
- No need for custom OCR implementation
- Preserves document structure and formatting
- Works out-of-the-box without configuration

Usage:
    python 01_simple_pdf.py
"""

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
import os
from pathlib import Path


def main():
    # Supported document formats
    supported_extensions = ['.pdf', '.docx', '.pptx', '.html', '.md', '.txt']
    documents_folder = Path("documents")
    
    # Find all supported documents
    documents = []
    for ext in supported_extensions:
        documents.extend(documents_folder.glob(f"*{ext}"))
    
    if not documents:
        print("No supported documents found in 'documents' folder")
        return
    
    print("=" * 60)
    print("Converting Documents to Markdown with Docling")
    print("=" * 60)
    print(f"Found {len(documents)} document(s):\n")
    for doc in documents:
        print(f"  - {doc.name}")
    print()

    # Initialize converter without table recognition and use CPU
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_table_structure = False
    pipeline_options.do_ocr = False  # Disable OCR to avoid GPU issues
    
    converter = DocumentConverter(
        format_options={
            PdfFormatOption: pipeline_options
        }
    )

    # Process each document
    for doc_path in documents:
        print("\n" + "=" * 60)
        print(f"Processing: {doc_path.name}")
        print("=" * 60)
        
        try:
            # Convert document
            result = converter.convert(str(doc_path))
            
            # Export to Markdown
            markdown = result.document.export_to_markdown()
            
            # Save to file
            output_filename = doc_path.stem + "_output.md"
            output_path = Path("output") / output_filename
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
            
            print(f"✓ Converted successfully")
            print(f"✓ Saved to: {output_path}")
            print(f"✓ Length: {len(markdown)} characters")
            
        except Exception as e:
            print(f"✗ Error processing {doc_path.name}: {str(e)}")
    
    print("\n" + "=" * 60)
    print("All documents processed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
