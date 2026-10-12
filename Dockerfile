FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
WORKDIR /standard
COPY requirements-qa.txt ./
RUN pip install --no-cache-dir -r requirements-qa.txt
COPY . .
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["sh", "-c", "python tools/validate.py && python -m unittest discover -s tests -v && python tools/demo_es.py"]
