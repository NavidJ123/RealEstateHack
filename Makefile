PYTHON ?= python3
VENV ?= .venv
ACTIVATE = . $(VENV)/bin/activate

.PHONY: venv api app all seed_sn test lint clean

venv:
	$(PYTHON) -m venv $(VENV)
	$(ACTIVATE) && pip install --upgrade pip
	$(ACTIVATE) && pip install -r requirements.txt

api:
	$(ACTIVATE) && uvicorn backend.api:app --reload --port 8000

app:
	$(ACTIVATE) && streamlit run app/main.py --server.port=8501

all:
	$(ACTIVATE) && bash -c "trap 'kill 0' EXIT; uvicorn backend.api:app --reload --port 8000 & streamlit run app/main.py --server.port=8501"

seed_sn:
	$(ACTIVATE) && python backend/db/seed_servicenow.py

lint:
	$(ACTIVATE) && PYTHONPATH=. ruff check

test:
	$(ACTIVATE) && PYTHONPATH=. pytest -q

clean:
	rm -rf $(VENV)
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
