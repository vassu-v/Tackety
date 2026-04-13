import os
from typing import Optional
try:
    from pypdf import PdfReader
except ImportError:
    print("Warning: pypdf not found. Ensure it is installed: pip install pypdf")
    PdfReader = None

def filetypeprocessor(file_path: str) -> Optional[str]:
    """
    Detects the file extension and returns the extracted raw text content.
    Supported types: .pdf, .txt, .md
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found - {file_path}")
        return None

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        if PdfReader is None:
            print("Error: PdfReader is not available (pypdf missing).")
            return None
        try:
            reader = PdfReader(file_path)
            full_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)
            return "\n".join(full_text)
        except Exception as e:
            print(f"Error processing PDF {file_path}: {e}")
            return None

    elif ext in [".txt", ".md"]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error processing text file {file_path}: {e}")
            return None

    else:
        print(f"Unsupported file type: {ext}")
        return None
