import json
import os
import random
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.search.simple_search import create_search_engine, load_index
from app.processors.pdf_to_images import convert_pdf_to_images


app = FastAPI(title="Дискретная математика - RAG")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

search_engine = None
sections_index = []


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


class ValidateRequest(BaseModel):
    question_id: str
    answer: str


class SimulatorRequest(BaseModel):
    chapter: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    global search_engine, sections_index
    
    print("Initializing RAG system...")
    
    pages_dir = BASE_DIR / "data" / "pages"
    index_path = BASE_DIR / "data" / "sections_index.json"
    
    if not pages_dir.exists() or len(list(pages_dir.glob("*.png"))) < 100:
        print("Converting PDF to images...")
        convert_pdf_to_images(str(BASE_DIR / "books" / "DM2024.pdf"), str(pages_dir), dpi=150)
    
    if not index_path.exists():
        print("Building sections index...")
        from app.search.pdf_indexer import PDFIndexer
        indexer = PDFIndexer(str(BASE_DIR / "books" / "DM2024.pdf"))
        indexer.extract_sections()
        indexer.save(str(index_path))
    
    sections_index = load_index(str(index_path))
    print(f"Loaded {len(sections_index)} sections")
    
    search_engine = create_search_engine(sections_index)
    print("Search engine ready!")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/simulator", response_class=HTMLResponse)
async def simulator_page(request: Request):
    return templates.TemplateResponse("simulator.html", {"request": request})


@app.get("/data/pages/{filename}")
async def get_page_image(filename: str):
    img_path = BASE_DIR / "data" / "pages" / filename
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(img_path, media_type="image/png")


def get_page_range(center_page: int, total_pages: int = 1738, offset: int = 0) -> list:
    base_start = center_page + offset * 5
    pages = []
    for i in range(5):
        page = base_start + i
        if 1 <= page <= total_pages:
            pages.append(page)
    return pages


@app.post("/api/search")
async def search(request: SearchRequest):
    if not search_engine:
        raise HTTPException(status_code=503, detail="Search engine not initialized")
    
    results = search_engine.search(request.query, top_k=request.top_k)
    
    response_results = []
    for r in results:
        pages = get_page_range(r.page, offset=0)
        
        response_results.append({
            "section": r.section_num,
            "title": r.title,
            "main_page": r.page,
            "pages": pages,
            "thumbnails": [f"/data/pages/page_{p:04d}.png" for p in pages],
            "keywords": r.keywords
        })
    
    return JSONResponse({"results": response_results})


@app.get("/api/pages/{page_num}")
async def get_pages(page_num: int, offset: int = 0):
    pages = get_page_range(page_num, offset=offset)
    return JSONResponse({
        "pages": pages,
        "thumbnails": [f"/data/pages/page_{p:04d}.png" for p in pages]
    })


@app.get("/api/chapters")
async def get_chapters():
    chapters = {}
    for s in sections_index:
        ch = s['section_num'].split('.')[0]
        if ch.isdigit():
            if ch not in chapters:
                chapters[ch] = s['title']
    
    return JSONResponse({
        "chapters": [{"id": k, "title": v} for k, v in sorted(chapters.items(), key=lambda x: int(x[0]))]
    })


@app.post("/api/simulator/next")
async def next_question(req: SimulatorRequest):
    if not sections_index:
        raise HTTPException(status_code=503, detail="Not initialized")
    
    available = sections_index
    if req.chapter:
        available = [s for s in sections_index if s['section_num'].startswith(req.chapter + '.')]
    
    if not available:
        return JSONResponse({"error": "No questions available"}, status_code=404)
    
    section = random.choice(available)
    
    question_templates = [
        f"Что вы знаете о {section['title']}?",
        f"Расскажите о {section['title']}.",
        f"Какие ключевые понятия в разделе {section['title']}?",
        f"Дайте характеристику {section['title']}.",
    ]
    question_text = random.choice(question_templates)
    
    page = section['page']
    context_pages = []
    for offset in [-1, 0]:
        p = page + offset
        if 1 <= p <= 1738:
            context_pages.append(p)
    
    return JSONResponse({
        "question_id": section['section_num'],
        "text": question_text,
        "chapter": section['section_num'].split('.')[0],
        "section": section['section_num'],
        "section_title": section['title'],
        "context_pages": context_pages,
        "context_thumbnails": [f"/data/pages/page_{p:04d}.png" for p in context_pages]
    })


@app.post("/api/simulator/validate")
async def validate_answer(req: ValidateRequest):
    question_id = req.question_id
    section = next((s for s in sections_index if s['section_num'] == question_id), None)
    
    if not section:
        return JSONResponse({
            "valid": True,
            "correct": False,
            "feedback": "Раздел не найден",
            "correct_answer": ""
        })
    
    page = section['page']
    answer_pages = get_page_range(page)
    
    is_correct = len(req.answer) > 10
    
    return JSONResponse({
        "valid": True,
        "correct": is_correct,
        "feedback": "Отличный ответ!" if is_correct else "Попробуйте еще раз изучить материал.",
        "correct_answer": section['title'],
        "section_title": section['title'],
        "answer_pages": answer_pages,
        "answer_thumbnails": [f"/data/pages/page_{p:04d}.png" for p in answer_pages]
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
