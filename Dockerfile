FROM python:3.10-slim

# Install compilation tools
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up a new user with UID 1000 to comply with Hugging Face requirements
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Create PipeLine folder in working directory and copy its requirements
RUN mkdir -p PipeLine
COPY --chown=user:user PipeLine/requirements.txt ./PipeLine/

# Install requirements
RUN pip install --no-cache-dir --user -r PipeLine/requirements.txt

# Copy the rest of the project files
COPY --chown=user:user . .

# Expose default Hugging Face Spaces port
EXPOSE 7860

# Start Flask app using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--chdir", "PipeLine", "app:app"]
