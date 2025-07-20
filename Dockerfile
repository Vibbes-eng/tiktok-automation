FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11-slim
COPY main.py /app/main.py
COPY start.py /app/start.py
WORKDIR /app
CMD ["python", "start.py"]