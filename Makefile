.PHONY: install build run test clean

install:
	python -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

build:
	python tools/build_portal.py

run:
	python wsgi.py

test:
	python -m pytest

clean:
	rm -rf .venv __pycache__ .pytest_cache .coverage htmlcov var
