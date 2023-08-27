FROM --platform=linux/amd64 python:3.9-slim-buster


ENV POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    PYSETUP_PATH="/opt/pysetup"

ENV PATH="$POETRY_HOME/bin:$PATH"

RUN apt-get update && \
    apt-get install --no-install-recommends -y curl && \
    apt-get clean

RUN curl -sSL https://install.python-poetry.org/ | python -

# RUN apt-get install -y php php-dev

# RUN apt-get install -y git
# RUN git clone --recursive --depth=1 https://github.com/kjdev/php-ext-lz4.git
# WORKDIR /php-ext-lz4
# RUN phpize
# RUN ./configure
# RUN make
# RUN make install
RUN apt-get install -y php
RUN sed -i 's/;extension=bz2/extension=\/app\/php-ext-lz4\/modules\/lz4.so/' /etc/php/7.3/cli/php.ini

# packages install
WORKDIR /app
COPY ./pyproject.toml /app/pyproject.toml
RUN poetry install --only main --no-root

# Python script
COPY ./main.py /app/main.py
COPY . .

# PHP script
RUN php svg.php test

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
