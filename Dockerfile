FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for compilation of some packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories that the app writes to
RUN mkdir -p logs output/media data

# Create a user to run the app (Hugging Face recommends not running as root)
RUN useradd -m -u 1000 user
RUN chown -R user:user /app
USER user

# Set environment variables
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PORT=7860

# Expose the port Hugging Face Spaces expects
EXPOSE 7860

# Command to run the application
CMD ["python", "wsgi.py"]
