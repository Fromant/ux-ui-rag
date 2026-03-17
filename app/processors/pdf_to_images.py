import os
import fitz
from pathlib import Path
from PIL import Image


def convert_pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 150):
    os.makedirs(output_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    print(f"Converting {len(doc)} pages to images...")
    
    for page_num in range(len(doc)):
        if page_num % 100 == 0:
            print(f"Processing page {page_num + 1}/{len(doc)}")
        
        page = doc.load_page(page_num)
        
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        img_path = os.path.join(output_dir, f"page_{page_num + 1:04d}.png")
        pix.save(img_path)
    
    doc.close()
    print(f"Saved {len(doc)} images to {output_dir}")


if __name__ == "__main__":
    convert_pdf_to_images("books/DM2024.pdf", "data/pages", dpi=150)
