# Архитектура RAG-системы для учебника по дискретной математике

## Общая диаграмма архитектуры

```mermaid
graph TB
    subgraph "Клиентский слой"
        Browser[Браузер]
        SearchUI[index.html<br/>Поиск]
        SimUI[simulator.html<br/>Тренажёр]
    end

    subgraph "Backend - FastAPI (main.py)"
        API[FastAPI Application]
        SearchEndpoint[POST /api/search]
        SimNextEndpoint[POST /api/simulator/next]
        SimValidateEndpoint[POST /api/simulator/validate]
        PagesEndpoint[GET /api/pages/:num]
        ImagesEndpoint[GET /data/pages/:filename]
    end

    subgraph "Поисковый модуль (app/search/)"
        BM25[BM25 Search Engine<br/>simple_search.py]
        IndexLoader[Index Loader<br/>load_index]
    end

    subgraph "Модуль валидации (app/models/)"
        Validator[Answer Validator<br/>answer_validator.py]
        SentenceTransformer[Sentence Transformers<br/>paraphrase-multilingual-MiniLM]
    end

    subgraph "Модуль обработки (app/processors/)"
        PDFExtractor[PDF Keyword Extractor<br/>pdf_keyword_extractor.py]
        QuestionGen[Question Template Generator<br/>question_template_generator.py]
        KeyTermsParser[Key Terms Table Parser<br/>key_terms_table_parser.py]
        TextCleaner[Text Cleaner<br/>text_cleaner.py]
    end

    subgraph "Скрипты генерации"
        BuildScript[build_keywords.py<br/>Index Builder]
    end

    subgraph "Хранилище данных (data/)"
        SectionIndex[sections_index.json<br/>Индекс секций]
        PageImages[pages/*.png<br/>Изображения страниц]
    end

    subgraph "Внешние ресурсы"
        PDF[books/DM2024.pdf<br/>Учебник]
    end

    %% Client to Backend
    Browser --> SearchUI
    Browser --> SimUI
    SearchUI --> SearchEndpoint
    SimUI --> SimNextEndpoint
    SimUI --> SimValidateEndpoint
    SearchUI --> PagesEndpoint
    SimUI --> ImagesEndpoint

    %% Backend to Modules
    API --> SearchEndpoint
    API --> SimNextEndpoint
    API --> SimValidateEndpoint
    API --> PagesEndpoint
    API --> ImagesEndpoint

    SearchEndpoint --> BM25
    SimNextEndpoint --> SectionIndex
    SimValidateEndpoint --> Validator
    PagesEndpoint --> PageImages
    ImagesEndpoint --> PageImages

    %% Search Module
    BM25 --> IndexLoader
    IndexLoader --> SectionIndex

    %% Validator Module
    Validator --> SentenceTransformer

    %% Build Pipeline
    BuildScript --> PDFExtractor
    BuildScript --> QuestionGen
    BuildScript --> KeyTermsParser
    BuildScript --> TextCleaner
    PDFExtractor --> PDF
    BuildScript --> SectionIndex
    BuildScript --> PageImages
```

## Диаграмма последовательности - Поиск

```mermaid
sequenceDiagram
    participant User as Пользователь
    participant UI as index.html
    participant API as FastAPI
    participant Search as BM25 Engine
    participant Index as sections_index.json
    participant Pages as pages/*.png

    User->>UI: Вводит запрос "графы"
    UI->>API: POST /api/search<br/>{query: "графы", top_k: 3}
    API->>Search: search("графы", top_k=3)
    Search->>Index: Загрузка индекса
    Index-->>Search: Секции с ключевыми словами
    Search-->>API: Top-3 релевантных секций
    API->>Pages: Получение страниц (page ± 2)
    Pages-->>API: URLs изображений
    API-->>UI: JSON с результатами
    UI-->>User: Отображение результатов<br/>+ страницы учебника
```

## Диаграмма последовательности - Тренажёр

```mermaid
sequenceDiagram
    participant User as Студент
    participant UI as simulator.html
    participant API as FastAPI
    participant Index as sections_index.json
    participant Validator as Answer Validator
    participant ST as Sentence Transformers

    User->>UI: Нажимает "Следующий вопрос"
    UI->>API: POST /api/simulator/next
    API->>Index: Выбор случайной секции
    Index-->>API: Вопрос + контекст
    API-->>UI: Текст вопроса
    UI-->>User: Показ вопроса<br/>(без контекста)

    User->>UI: Вводит ответ
    UI->>API: POST /api/simulator/validate<br/>{question_id, answer}
    API->>Index: Получение правильного ответа
    Index-->>API: Reference answer + keywords
    API->>Validator: validate_answer()
    Validator->>ST: Сравнение эмбеддингов
    ST-->>Validator: Cosine similarity score
    Validator-->>API: Вердикт + feedback
    API-->>UI: Результат + страницы
    UI-->>User: Оценка ответа +<br/>страницы учебника
```

## Pipeline генерации индекса

```mermaid
graph LR
    subgraph "Входные данные"
        PDF[DM2024.pdf]
    end

    subgraph "Этапы обработки (build_keywords.py)"
        Extract[SectionExtractor<br/>Извлечение секций по паттернам]
        RedText[RedTextKeywordExtractor<br/>Красный текст из PDF]
        SubjectIndex[SubjectIndexParser<br/>Предметный указатель]
        Questions[QuestionTemplateGenerator<br/>Генерация вопросов]
        Merge[Keyword Merger<br/>Приоритетное слияние]
    end

    subgraph "Выходные данные"
        Index[sections_index.json]
        Images[pages/*.png]
    end

    PDF --> Extract
    PDF --> RedText
    PDF --> SubjectIndex
    Extract --> Merge
    RedText --> Merge
    SubjectIndex --> Merge
    Merge --> Questions
    Questions --> Index
    PDF --> Images

```

## Структура компонентов

```mermaid
graph TB
    subgraph "frontend/"
        Templates[templates/<br/>├── index.html<br/>└── simulator.html]
    end

    subgraph "backend/"
        Main[main.py<br/>FastAPI приложение]
    end

    subgraph "app/search/"
        Search[simple_search.py<br/>BM25 поиск]
    end

    subgraph "app/models/"
        Validator[answer_validator.py<br/>Семантическая валидация]
    end

    subgraph "app/processors/"
        PDFKeywords[pdf_keyword_extractor.py<br/>Извлечение ключевых слов]
        QuestionGen[question_template_generator.py<br/>Генерация вопросов]
        KeyTerms[key_terms_table_parser.py<br/>Парсер таблиц ключевых terms]
        TextCleaner[text_cleaner.py<br/>Очистка текста]
    end

    subgraph "data/"
        Index[sections_index.json]
        Pages[pages/*.png]
    end

    subgraph "scripts/"
        Build[build_keywords.py]
    end

    Templates --> Main
    Main --> Search
    Main --> Validator
    Build --> PDFKeywords
    Build --> QuestionGen
    Build --> KeyTerms
    Build --> TextCleaner
    Build --> Index
    Search --> Index
    Validator --> Index

```

## Технологический стек

```mermaid
graph LR
    subgraph "Backend"
        FastAPI[FastAPI]
        Uvicorn[Uvicorn]
        Pydantic[Pydantic]
    end

    subgraph "Поиск"
        BM25[rank-bm25]
        NLTK[NLTK]
    end

    subgraph "Обработка PDF"
        PyMuPDF[PyMuPDF]
    end

    subgraph "ML/NLP"
        SentenceTransformers[sentence-transformers]
        Torch[PyTorch]
    end

    subgraph "Frontend"
        HTML[HTML/CSS/JS]
    end

    subgraph "Инфраструктура"
        Docker[Docker]
    end
```

## Диаграмма данных

```mermaid
graph TB
    subgraph "Источники ключевых слов"
        RedText[Красный текст<br/>RGB: R≥0.8, G,B≤0.3]
        SubjIndex[Предметный указатель<br/>последние 50 страниц]
        Freq[Частотный анализ<br/>TF-based]
    end

    subgraph "Приоритет слияния"
        Priority1[Предметный указатель<br/>высший приоритет]
        Priority2[Красный текст<br/>средний приоритет]
        Priority3[Частотный анализ<br/>резервный]
    end

    RedText --> Section
    SubjIndex --> Section
    Freq --> Section

    Priority1 -.-> SubjIndex
    Priority2 -.-> RedText
    Priority3 -.-> Freq
```
