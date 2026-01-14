import aiohttp
import asyncio
import os
import json
from bs4 import BeautifulSoup
from pathlib import Path
import mimetypes
import speech_recognition as sr
import tempfile
import subprocess
import fitz  # PyMuPDF for PDFs
from docx import Document
import pandas as pd
from urllib.parse import urljoin, urlparse
from collections import deque

BASE_URL = "https://www.mosdac.gov.in"
OUTPUT_DIR = Path("output")
MEDIA_DIR = OUTPUT_DIR / "media"
VISITED = set()
SITE_DATA = {"url": BASE_URL, "children": []}

OUTPUT_DIR.mkdir(exist_ok=True)
MEDIA_DIR.mkdir(exist_ok=True)

# ---------------- Utilities ---------------- #

async def fetch(session, url):
    try:
        async with session.get(url, timeout=30) as resp:
            if resp.status == 200:
                ct = resp.headers.get("content-type", "")
                return await resp.read(), ct
    except Exception as e:
        print(f"[ERROR] {url}: {e}")
    return None, None

def save_file(content, url, ct):
    ext = mimetypes.guess_extension(ct.split(";")[0]) or ".bin"
    fname = MEDIA_DIR / (url.split("/")[-1].split("?")[0] or "file" + ext)
    with open(fname, "wb") as f:
        f.write(content)
    return fname

def pdf_to_text(path):
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()

def docx_to_text(path):
    doc = docx.Document(path)
    return "\n".join([p.text for p in doc.paragraphs])

def csv_xlsx_to_text(path):
    try:
        df = pd.read_excel(path) if path.suffix in [".xlsx", ".xls"] else pd.read_csv(path)
        return df.to_string()
    except Exception as e:
        return f"[ERROR READING TABLE] {e}"

def audio_to_text(path):
    recognizer = sr.Recognizer()
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        if path.suffix != ".wav":
            subprocess.run(["ffmpeg", "-i", str(path), str(tmp.name)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            audio_path = tmp.name
        else:
            audio_path = str(path)
        with sr.AudioFile(audio_path) as source:
            audio = recognizer.record(source)
            return recognizer.recognize_google(audio, language="en-IN")

# ---------------- Parsing ---------------- #

def extract_html_structure(html, url):
    soup = BeautifulSoup(html, "html.parser")
    structure = {"url": url, "text": "", "children": []}

    for header in soup.find_all(["h1","h2","h3","h4","h5","h6"]):
        section = {"header": header.get_text(strip=True), "content": "", "children": []}
        sib = header.find_next_sibling()
        while sib and sib.name not in ["h1","h2","h3","h4","h5","h6"]:
            section["content"] += sib.get_text(" ", strip=True) + " "
            sib = sib.find_next_sibling()
        structure["children"].append(section)

    if not structure["children"]:
        structure["text"] = soup.get_text(" ", strip=True)
    return structure

async def crawl_website(session, start_url, max_pages=1000):
    queue = asyncio.Queue()
    visited = set()
    results = []
    
    await queue.put(start_url)
    visited.add(start_url)
    
    async def worker():
        while True:
            try:
                url = await queue.get()
                if len(visited) >= max_pages:
                    queue.task_done()
                    continue
                
                content, ct = await fetch(session, url)
                if not content:
                    queue.task_done()
                    continue
                
                node = {"url": url, "text": "", "children": []}
                results.append(node)
                
                if "html" in ct:
                    html_structure = extract_html_structure(content, url)
                    node.update(html_structure)
                    
                    # Extract and queue new links
                    soup = BeautifulSoup(content, "html.parser")
                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        full_url = urljoin(url, href)
                        
                        # Only follow same-domain links
                        if (urlparse(full_url).netloc == urlparse(BASE_URL).netloc and 
                            full_url not in visited and 
                            len(visited) < max_pages):
                            visited.add(full_url)
                            await queue.put(full_url)
                
                elif "pdf" in ct:
                    path = save_file(content, url, ct)
                    node["text"] = pdf_to_text(path)
                
                # Handle other file types similarly...
                
                queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Worker error: {e}")
                queue.task_done()
    
    # Start multiple workers
    workers = [asyncio.create_task(worker()) for _ in range(10)]
    await queue.join()
    
    # Cancel workers
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
    
    return results

# ---------------- Main ---------------- #

async def main():
    async with aiohttp.ClientSession() as session:
        all_pages = await crawl_website(session, BASE_URL, max_pages=1000)
        
        # Build hierarchical structure if needed
        SITE_DATA["children"] = all_pages

    with open(OUTPUT_DIR / "output.json", "w", encoding="utf-8") as f:
        json.dump(SITE_DATA, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())