FROM python:3.13

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt --no-cache-dir

# RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

COPY . .

WORKDIR /app/foodgram_final

# RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "--bind", "0.0.0.0:7000", "foodgram_final.wsgi"]
