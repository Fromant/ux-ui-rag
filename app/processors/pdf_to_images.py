import os
import fitz


def convert_pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 150):
    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"Converting {total_pages} pages to images...")

    for page_num in range(total_pages):
        if page_num % 100 == 0:
            print(f"Processing page {page_num + 1}/{total_pages}")

        page = doc.load_page(page_num)

        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        img_path = os.path.join(output_dir, f"page_{page_num + 1:04d}.png")
        pix.save(img_path)

    doc.close()
    print(f"Saved {total_pages} images to {output_dir}")
