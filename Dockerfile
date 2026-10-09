FROM python:3.12-slim
WORKDIR /standard
COPY requirements-qa.txt ./
RUN pip install --no-cache-dir -r requirements-qa.txt
COPY . .
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["sh", "-c", "python tools/validate.py && python -m unittest discover -s tests -v && python tools/demo_es.py"]
