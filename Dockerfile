
FROM python:3.12-slim

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        git build-essential python3-dev \
        libjpeg-dev zlib1g-dev libpng-dev libfreetype6-dev \
        liblcms2-dev libopenjp2-7-dev libtiff-dev \
        tk-dev tcl-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /DreamxBotz

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip --root-user-action=ignore && \
    pip install --no-cache-dir -r requirements.txt --root-user-action=ignore

COPY . .

CMD ["python3", "bot.py"]
