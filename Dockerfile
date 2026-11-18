FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Pliki statyczne zbieramy w obrazie (serwuje je WhiteNoise). SECRET_KEY tylko na czas builda.
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

# Użytkownik bez uprawnień roota; /app/media tylko do uruchomień lokalnych (w Azure media są w Blobie)
RUN useradd --create-home app && mkdir -p /app/media && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["gunicorn", "-c", "gunicorn.conf.py", "config.wsgi:application"]
