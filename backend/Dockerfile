FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Patch libxrk to tolerate non-sequential lap numbers in AIM XRK files.
# The stock parser raises "Lap gap from N to M" when the embedded LAP messages
# go backwards or skip more than one (some loggers re-emit corrected laps).
# We rebuild the Cython module with the validation turned into a `continue`
# so problematic LAP messages are skipped and parsing succeeds.
# Note: cargo is not installed, so the Rust backend is intentionally skipped;
# our app uses the default Cython backend (LIBXRK_BACKEND unset).
RUN set -eux; \
    LIBXRK_VERSION=$(python -c "from importlib.metadata import version; print(version('libxrk'))"); \
    pip install --no-cache-dir "cython>=3.0" setuptools wheel; \
    mkdir -p /tmp/libxrk-src; \
    cd /tmp/libxrk-src; \
    curl -sSLO "https://files.pythonhosted.org/packages/source/l/libxrk/libxrk-${LIBXRK_VERSION}.tar.gz"; \
    tar xzf "libxrk-${LIBXRK_VERSION}.tar.gz"; \
    cd "libxrk-${LIBXRK_VERSION}"; \
    grep -q "raise ValueError('Lap gap from %d to %d'" src/libxrk/aim_xrk.pyx; \
    sed -i "s|raise ValueError('Lap gap from %d to %d' % (lap_nums\[-1\], lap))|continue|" src/libxrk/aim_xrk.pyx; \
    ! grep -q "raise ValueError('Lap gap from %d to %d'" src/libxrk/aim_xrk.pyx; \
    echo "libxrk patched: lap-gap validation bypassed"; \
    pip install --no-cache-dir --force-reinstall --no-deps .; \
    cd /; \
    rm -rf /tmp/libxrk-src

COPY app/ app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
