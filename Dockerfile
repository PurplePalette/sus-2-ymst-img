FROM --platform=linux/amd64 kotayan/sus2ymst-img:latest

# packages install
WORKDIR /app
COPY ./pyproject.toml /app/pyproject.toml
RUN poetry install --only main --no-root

COPY ./main.py /app/main.py
COPY . .

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
