#!/bin/bash
# Helper script to manage RAG system

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== RAG System Helper ===${NC}"

case "$1" in
    build)
        echo -e "${YELLOW}Building index with Docker...${NC}"
        docker compose --profile build up rag-builder
        ;;
    build-skip-questions)
        echo -e "${YELLOW}Building index without question generation (faster)...${NC}"
        docker compose run --rm \
            -v ./data:/app/data \
            -v ./books:/app/books:ro \
            --env-file .env \
            rag-builder \
            python build_index.py --pdf books/DM2024.pdf --output data/sections_index.json --skip-questions
        ;;
    start)
        echo -e "${YELLOW}Starting RAG system...${NC}"
        docker compose up -d
        echo -e "${GREEN}Application running at http://localhost:8000${NC}"
        ;;
    stop)
        echo -e "${YELLOW}Stopping RAG system...${NC}"
        docker compose down
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    logs)
        docker compose logs -f
        ;;
    status)
        docker compose ps
        ;;
    clean)
        echo -e "${YELLOW}Cleaning generated data...${NC}"
        rm -rf data/
        mkdir -p data/pages
        echo -e "${GREEN}Cleaned!${NC}"
        ;;
    *)
        echo -e "${YELLOW}Usage:${NC}"
        echo -e "  $0 build                  - Build index with Docker (includes questions)"
        echo -e "  $0 build-skip-questions   - Build index without questions (faster)"
        echo -e "  $0 start                  - Start the application"
        echo -e "  $0 stop                   - Stop the application"
        echo -e "  $0 restart                - Restart the application"
        echo -e "  $0 logs                   - View logs"
        echo -e "  $0 status                 - Check status"
        echo -e "  $0 clean                  - Remove generated data"
        echo ""
        echo -e "${YELLOW}First time setup:${NC}"
        echo -e "  1. Copy .env.example to .env and add your API key"
        echo -e "  2. Place PDF in books/DM2024.pdf"
        echo -e "  3. Run: $0 build"
        echo -e "  4. Run: $0 start"
        ;;
esac
