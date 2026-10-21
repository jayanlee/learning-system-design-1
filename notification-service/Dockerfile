FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini alembic.ini
COPY alembic alembic
COPY app app
COPY entrypoint.sh entrypoint.sh
EXPOSE 8000
CMD ["sh", "entrypoint.sh"]
