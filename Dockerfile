FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
COPY streamlit_app.py .

EXPOSE 8000 8501

CMD ["uvicorn", "validation_pipeline.app:app", "--host", "0.0.0.0", "--port", "8000"]
