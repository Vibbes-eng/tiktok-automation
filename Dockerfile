cat > Dockerfile << 'EOF'
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11-slim
COPY main_minimal.py /app/main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

git add . && git commit -m "FastAPI pre-built image" && git push