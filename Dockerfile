FROM python:3.9-slim

RUN apt update && apt install -y curl build-essential libgl1-mesa-glx ghostscript libglib2.0-dev
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python -

COPY ./pyproject.toml ./poetry.lock /

RUN /root/.local/bin/poetry install

WORKDIR /mit-skate-cal

COPY ./mit_skate_cal /mit-skate-cal/mit_skate_cal

CMD ["/root/.local/bin/poetry", "run", "python", "/mit-skate-cal/mit_skate_cal/main.py"]
