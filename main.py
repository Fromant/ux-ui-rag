import random
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.search.simple_search import create_search_engine, load_index
from app.processors.pdf_to_images import convert_pdf_to_images
from app.models.answer_validator import initialize_validator


app = FastAPI(title="Дискретная математика - RAG")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

search_engine = None
sections_index = []
answer_validator = None


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
    global search_engine, sections_index, answer_validator

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

    # Initialize answer validator with semantic similarity
    print("Loading answer validator model...")
    answer_validator = initialize_validator()
    print("Answer validator ready!")


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

    # Generate question based on section title
    # Different templates work better for different types of titles
    title = section['title']
    
    # Question templates that work well with Russian technical titles
    question_templates = [
        f"Что вы знаете о \"{title}\"?",
        f"Расскажите о \"{title}\".",
        f"Дайте определение: {title}.",
        f"Объясните понятие \"{title}\".",
    ]
    
    # For titles that look like definitions or properties, use simpler templates
    if any(word in title.lower() for word in ['определение', 'свойство', 'признак', 'критерий', 'теорема']):
        question_templates = [
            f"Сформулируйте: {title}.",
            f"Что утверждает {title.lower()}?",
            f"Объясните: {title}.",
        ]
    
    # For titles about algorithms or methods
    if any(word in title.lower() for word in ['алгоритм', 'метод', 'способ', 'процедура']):
        question_templates = [
            f"Опишите алгоритм: {title}.",
            f"В чём суть метода \"{title}\"?",
            f"Как работает {title.lower()}?",
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

    # Build reference text from section content
    section_title = section['title']
    section_keywords = section.get('keywords', [])
    
    # Use semantic similarity via embeddings
    is_correct = False
    similarity_score = 0.0
    confidence = "unknown"
    matched_keywords = []
    
    if answer_validator:
        try:
            # Build reference text from title + keywords
            reference_text = f"{section_title} {' '.join(section_keywords[:5])}"
            
            is_correct, similarity_score, details = answer_validator.validate_answer(
                student_answer=req.answer,
                reference_text=reference_text,
                section_title=section_title,
                keywords=section_keywords
            )
            confidence = details.get('confidence', 'unknown')
            
            # Also check keyword matches for feedback
            answer_lower = req.answer.lower()
            for keyword in section_keywords:
                if keyword.lower() in answer_lower:
                    matched_keywords.append(keyword)
                    
        except Exception as e:
            print(f"Validation error: {e}")
            # Fallback to keyword matching if embedding fails
            answer_lower = req.answer.lower()
            for keyword in section_keywords:
                if keyword.lower() in answer_lower:
                    matched_keywords.append(keyword)
            
            title_words = section_title.lower().split()
            for title_word in title_words:
                if len(title_word) > 3 and title_word not in matched_keywords and title_word in answer_lower:
                    matched_keywords.append(title_word)
            
            total_terms = len(section_keywords) + len([w for w in title_words if len(w) > 3])
            match_count = len(matched_keywords)
            is_correct = (total_terms > 0 and match_count / total_terms >= 0.3) or (len(req.answer) >= 20 and match_count >= 1)
            similarity_score = match_count / max(total_terms, 1)
            confidence = "fallback"
    else:
        # Fallback if validator not initialized
        answer_lower = req.answer.lower()
        for keyword in section_keywords:
            if keyword.lower() in answer_lower:
                matched_keywords.append(keyword)
        
        title_words = section_title.lower().split()
        for title_word in title_words:
            if len(title_word) > 3 and title_word not in matched_keywords and title_word in answer_lower:
                matched_keywords.append(title_word)
        
        total_terms = len(section_keywords) + len([w for w in title_words if len(w) > 3])
        match_count = len(matched_keywords)
        is_correct = (total_terms > 0 and match_count / total_terms >= 0.3) or (len(req.answer) >= 20 and match_count >= 1)
        similarity_score = match_count / max(total_terms, 1)

    # Generate feedback based on confidence
    if confidence == "high":
        feedback = "Отличный ответ! Вы хорошо усвоили материал."
    elif confidence == "medium":
        feedback = "Хороший ответ! Но можно ответить полнее."
    elif confidence == "low":
        feedback = "Ответ частично верный, но стоит повторить материал."
    else:
        feedback = "Попробуйте еще раз изучить материал."

    return JSONResponse({
        "valid": True,
        "correct": is_correct,
        "feedback": feedback,
        "correct_answer": section_title,
        "section_title": section_title,
        "similarity_score": similarity_score,
        "confidence": confidence,
        "matched_keywords": matched_keywords,
        "answer_pages": answer_pages,
        "answer_thumbnails": [f"/data/pages/page_{p:04d}.png" for p in answer_pages]
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
