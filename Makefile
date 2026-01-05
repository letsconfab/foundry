.PHONY: help all db api ui clean install-api install-ui stop logs-api logs-db logs-ui

# Default target
help:
	@echo "Available commands:"
	@echo "  make all        - Start all services (db, api, ui)"
	@echo "  make db         - Start PostgreSQL database"
	@echo "  make api        - Start FastAPI backend"
	@echo "  make ui         - Start React frontend"
	@echo "  make stop       - Stop all running services"
	@echo "  make clean      - Clean up containers and volumes"
	@echo "  make install-ui - Install frontend dependencies"
	@echo "  make install-api- Install backend dependencies"
	@echo "  make logs-api   - Show API logs"
	@echo "  make logs-db    - Show database logs"
	@echo "  make logs-ui    - Show UI logs"

# Start all services
all: db api ui

# Database service
db:
	@echo "Starting PostgreSQL database..."
	docker-compose up -d db

# API service
api:
	@echo "Starting FastAPI backend..."
	cd api && . .venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8001

# UI service
ui:
	@echo "Starting React frontend..."
	cd ui && npm run dev

# Install dependencies
install-api:
	@echo "Installing API dependencies..."
	cd api && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

install-ui:
	@echo "Installing UI dependencies..."
	cd ui && npm install

# Stop all services
stop:
	@echo "Stopping all services..."
	docker-compose down
	@pkill -f "uvicorn main:app" || true
	@pkill -f "vite" || true

# Clean up
clean:
	@echo "Cleaning up containers and volumes..."
	docker-compose down -v
	@pkill -f "uvicorn main:app" || true
	@pkill -f "vite" || true

# Logs
logs-api:
	@echo "API logs (if running in background)"
	@docker-compose logs -f api || echo "API not running in docker"

logs-db:
	@echo "Database logs"
	docker-compose logs -f db

logs-ui:
	@echo "UI logs (if running in background)"
	@docker-compose logs -f ui || echo "UI not running in docker"

# Development helpers
dev-setup: install-api install-ui
	@echo "Development environment setup complete!"
	@echo "Run 'make all' to start all services"
