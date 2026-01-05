"""
Simple PDF Parsing with Docling – Quick Start

This script demonstrates the most basic usage of Docling:
converting a PDF to Markdown.
"""

from docling.document_converter import DocumentConverter


def convert_pdf_to_markdown(pdf_path: str, output_path: str = None) -> str:
    """
    Convert a PDF file to Markdown format using Docling.
    
    Args:
        pdf_path: Path to the input PDF file
        output_path: Optional path to save the output Markdown file
        
    Returns:
        Markdown content as a string
    """
    # Initialize the document converter
    converter = DocumentConverter()
    
    # Convert the PDF
    result = converter.convert(pdf_path)
    
    # Export to Markdown
    markdown_content = result.document.export_to_markdown()
    
    # Save to file if output path is provided
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"Markdown saved to: {output_path}")
    
    return markdown_content


def main():
    """Main function to demonstrate PDF to Markdown conversion."""
    # Example usage
    pdf_file = "example.pdf"  # Replace with your PDF file path
    output_file = "output.md"
    
    try:
        print(f"Converting {pdf_file} to Markdown...")
        markdown = convert_pdf_to_markdown(pdf_file, output_file)
        print(f"\nConversion successful!")
        print(f"\nPreview (first 500 characters):\n{markdown[:500]}...")
        
    except FileNotFoundError:
        print(f"Error: File '{pdf_file}' not found.")
        print("Please update the pdf_file variable with a valid PDF path.")
    except Exception as e:
        print(f"Error during conversion: {e}")


if __name__ == "__main__":
    main()
