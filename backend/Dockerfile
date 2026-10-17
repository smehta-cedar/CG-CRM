# Stage 1: install the dependencies into a standalone virtualenv.
FROM python:3.14-alpine AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

ARG REQUIREMENTS=local
COPY requirements/ requirements/
RUN pip install -r requirements/${REQUIREMENTS}.txt \
    && pip uninstall -y pip \
    && cd /opt/venv/lib/python3.14/site-packages \
    # LANGUAGE_CODE is en-us; every other translation is dead weight.
    && find . -type d -path "*/locale/*" -maxdepth 6 ! -name "en*" ! -name LC_MESSAGES -prune -exec rm -rf {} + \
    && find . -type d \( -name __pycache__ -o -name tests \) -prune -exec rm -rf {} +


# Stage 2: runtime only, no pip or build leftovers.
FROM python:3.14-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN python -m pip uninstall -y pip \
    && rm -rf /root/.cache

COPY --from=builder /opt/venv /opt/venv

# Amazon's CA bundle, so prod can verify the AWS RDS certificate.
ADD https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /etc/ssl/certs/rds-global-bundle.pem
RUN chmod 644 /etc/ssl/certs/rds-global-bundle.pem

WORKDIR /app
COPY . .

EXPOSE 8000

CMD ["sh", "sh/local.sh"]
