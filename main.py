import random
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.search.simple_search import create_search_engine, load_index
from app.models.answer_validator import initialize_validator


app = FastAPI(title="Дискретная математика - RAG")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

search_engine = None
sections_index = []
answer_validator = None
total_pages = 0


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


class ValidateRequest(BaseModel):
    question_id: str
    answer: str
    question_text: Optional[str] = None  # The question that was asked


class SimulatorRequest(BaseModel):
    chapter: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    global search_engine, sections_index, answer_validator, total_pages

    print("Initializing RAG system...")

    index_path = BASE_DIR / "data" / "sections_index.json"

    if not index_path.exists():
        raise RuntimeError(
            f"Index file not found at {index_path}. "
            "Run: docker compose --profile build up rag-builder"
        )

    sections_index = load_index(str(index_path))
    print(f"Loaded {len(sections_index)} sections")

    # Get total pages from page images
    pages_dir = BASE_DIR / "data" / "pages"
    if pages_dir.exists():
        png_files = list(pages_dir.glob("*.png"))
        total_pages = len(png_files)
        print(f"Found {total_pages} page images")
    else:
        print("Warning: No page images found")

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


def get_page_range(center_page: int, offset: int = 0) -> list:
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

        # Get full section data from index
        section_data = next((s for s in sections_index if s['section_num'] == r.section_num), {})

        response_results.append({
            "section": r.section_num,
            "title": r.title,
            "main_page": r.page,
            "pages": pages,
            "thumbnails": [f"/data/pages/page_{p:04d}.png" for p in pages],
            "keywords": r.keywords,
            "keyword_sources": section_data.get('keywords_by_source', {}),
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
    quiz_questions = section.get('quiz_questions', [])

    # Use pre-generated question from index
    if quiz_questions:
        question_data = random.choice(quiz_questions)
        question_text = question_data.get('question', f"Что вы знаете о \"{section['title']}\"?")
        question_type = question_data.get('type', 'definition')
        question_difficulty = question_data.get('difficulty', 'medium')
    else:
        # Fallback if no questions in index
        title = section['title']
        question_text = f"Что вы знаете о \"{title}\"?"
        question_type = 'definition'
        question_difficulty = 'medium'

    page = section['page']
    context_pages = []
    for offset in [-1, 0]:
        p = page + offset
        if 1 <= p <= total_pages:
            context_pages.append(p)

    return JSONResponse({
        "question_id": section['section_num'],
        "text": question_text,
        "question_type": question_type,
        "difficulty": question_difficulty,
        "chapter": section['section_num'].split('.')[0],
        "section": section['section_num'],
        "section_title": section['title'],
        "keywords": section.get('keywords', []),
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
            "reference_answer": ""
        })

    page = section['page']
    answer_pages = get_page_range(page)

    section_title = section['title']
    section_keywords = section.get('keywords', [])

    # Find the question and get reference answer
    question_text = req.question_text or ""
    reference_answer = ""

    if section.get('quiz_questions'):
        for q in section['quiz_questions']:
            if q.get('question') == question_text:
                reference_answer = q.get('answer', '')
                break

    # Fallback if no reference answer
    if not reference_answer:
        reference_answer = f"{section_title}. Ключевые понятия: {', '.join(section_keywords[:5])}"

    # Validate answer
    is_correct = False
    similarity_score = 0.0
    confidence = "unknown"
    matched_keywords = []

    if answer_validator:
        try:
            is_correct, similarity_score, details = answer_validator.validate_answer(
                student_answer=req.answer,
                question=question_text or section_title,
                reference_answer=reference_answer,
                section_title=section_title,
                keywords=section_keywords
            )
            confidence = details.get('confidence', 'unknown')
            matched_keywords = details.get('matched_keywords', [])
        except Exception as e:
            print(f"Validation error: {e}")
            confidence = "error"
    else:
        # Fallback to keyword matching if validator not loaded
        answer_lower = req.answer.lower()
        matched_keywords = [kw for kw in section_keywords if kw.lower() in answer_lower]
        title_words = [w for w in section_title.lower().split() if len(w) > 3]
        matched_keywords.extend([w for w in title_words if w in answer_lower and w not in matched_keywords])

        total_terms = len(section_keywords) + len(title_words)
        match_count = len(matched_keywords)
        is_correct = total_terms > 0 and match_count / total_terms >= 0.3
        similarity_score = match_count / max(total_terms, 1)
        confidence = "fallback"

    # Generate feedback
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
        "reference_answer": reference_answer,
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
