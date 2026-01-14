---
title: AstroBot
emoji: 🚀
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
---
# AstroBot - AI-Powered Space & Weather Assistant

A comprehensive AI chatbot web application that provides real-time information about satellites, weather data, and space research using MOSDAC (ISRO) data sources.

## Features

- **AI-Powered Chat**: Natural language queries about space and weather
- **RAG Architecture**: Retrieval Augmented Generation with FAISS vector database
- **Web Crawling**: Automated extraction of ISRO/MOSDAC data
- **Weather Integration**: Location-based weather forecasts
- **Voice Input**: Speech-to-text capabilities
- **Session Management**: Persistent chat history
- **PDF Export**: Download conversations as PDF

## Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables (copy `.env.example` to `.env`)
4. Run the application: `python main_App.py`

## Usage

Access the web interface at `http://localhost:5000` and start asking questions about:
- ISRO missions and satellites
- Weather forecasts for any location
- Space research and data
