from flask import Flask, render_template, request, jsonify, session, send_file
from flask_cors import CORS
import os
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from model import get_response as get_isro_response
from weather_advisory import save_weather_context, geocode_city
from weather_llm import get_weather_response
import re
from fpdf import FPDF
import tempfile
import datetime
from models import db, ChatSession, ChatMessage

# Configure logging
if not os.path.exists('logs'):
    os.mkdir('logs')
file_handler = RotatingFileHandler('logs/astrobot.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

app = Flask(__name__)

# Configuration
app.secret_key = os.getenv('SECRET_KEY', 'dev_default_key')
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'chat_history.db')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', f'sqlite:///{db_path}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Logger setup
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('AstroBot startup')

CORS(app)
db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()

# Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    app.logger.error(f"Server Error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# Initialize session data
@app.before_request
def setup_session():
    if 'chat_history' not in session:
        session['chat_history'] = []
    if 'current_region' not in session:
        session['current_region'] = None
    if 'mode' not in session:
        session['mode'] = 'auto'
    if 'current_session_id' not in session:
        session['current_session_id'] = None

# Helper functions
def remove_duplicate_content(content):
    """Remove duplicate sections from content"""
    if not content:
        return content
    
    # Split into paragraphs and remove duplicates
    paragraphs = content.split('\n\n')
    unique_paragraphs = []
    seen_paragraphs = set()
    
    for paragraph in paragraphs:
        # Create a simplified version for comparison (remove formatting)
        simple_para = re.sub(r'\*\*(.*?)\*\*', r'\1', paragraph)
        simple_para = re.sub(r'[^a-zA-Z0-9\s]', '', simple_para).strip().lower()
        
        # Only add if we haven't seen this content before and it's not too short
        if simple_para and len(simple_para) > 20 and simple_para not in seen_paragraphs:
            unique_paragraphs.append(paragraph)
            seen_paragraphs.add(simple_para)
    
    return '\n\n'.join(unique_paragraphs)

def format_response_for_html(text):
    """Format the response text for proper HTML display"""
    if not text:
        return text
    
    # Convert markdown-style formatting to HTML
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'^# (.*?)$', r'<h4 style="margin: 15px 0 8px 0; color: #00F0FF; text-transform: uppercase; letter-spacing: 0.05em; font-family: \'Orbitron\', sans-serif;">\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*?)$', r'<h5 style="margin: 12px 0 6px 0; color: #00F0FF; font-family: \'Orbitron\', sans-serif;">\1</h5>', text, flags=re.MULTILINE)
    
    # Lists: * item to <li>item</li>
    lines = text.split('\n')
    in_list = False
    formatted_lines = []
    
    for line in lines:
        if line.strip().startswith('* '):
            if not in_list:
                formatted_lines.append('<ul style="margin: 8px 0; padding-left: 20px;">')
                in_list = True
            formatted_lines.append(f'<li style="margin: 4px 0; color: #E0E6ED;">{line[2:].strip()}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            # Add paragraph breaks for regular text
            if line.strip() and not line.startswith('#') and not line.startswith('<'):
                formatted_lines.append(f'<p style="margin: 8px 0; line-height: 1.6;">{line}</p>')
            else:
                formatted_lines.append(line)
    
    if in_list:
        formatted_lines.append('</ul>')
    
    text = '\n'.join(formatted_lines)
    text = text.replace('\n\n', '<br><br>')
    text = text.replace('\n', ' ')
    
    return text

def classify_intent(query):
    """Classify query intent"""
    q = query.lower()
    weather_keywords = [
        "weather", "temperature", "rain", "climate", "storm", 
        "safe", "travel", "forecast", "humidity", "wind", 
        "sunny", "cloudy", "hot", "cold", "umbrella", "jacket",
        "temperature", "rainfall", "windy", "storm", "cyclone"
    ]
    
    if any(w in q for w in weather_keywords):
        return "weather"
    return "isro"

def is_pdf_query(query):
    """Check if user is asking for PDF"""
    pdf_keywords = [
        "pdf", "download", "save as", "export", "document",
        "file", "print", "get pdf", "give me pdf", "send pdf",
        "generate pdf", "create pdf", "downloadable"
    ]
    q = query.lower()
    return any(keyword in q for keyword in pdf_keywords)

def remove_emojis(text):
    """Remove emojis while preserving spaces and formatting"""
    if not text:
        return text
    
    # Remove emojis but preserve spaces and formatting
    import re
    # Remove emojis (Unicode characters outside basic multilingual plane)
    text = re.sub(r'[^\x00-\x7F\u00A0-\uD7FF\uE000-\uFFFF]', '', text)
    return text

def handle_weather_query(query):
    """Handle weather-related queries"""
    if not session.get('current_region'):
        return "Please set a region first using the region selector. I need to know which location's weather you're asking about."
    
    return get_weather_response(query)

def handle_isro_query(query):
    """Handle ISRO/MOSDAC queries"""
    chat_history = session.get('chat_history', [])
    response, _ = get_isro_response(query, chat_history)
    return response

# Home route - serve the UI
@app.route('/')
def index():
    return render_template('index.html')

# API to get chat sessions
@app.route('/api/chat_sessions', methods=['GET'])
def get_chat_sessions():
    try:
        sessions = ChatSession.query.order_by(ChatSession.updated_at.desc()).all()
        sessions_data = [{
            'id': s.id,
            'title': s.title,
            'created_at': s.created_at.isoformat(),
            'updated_at': s.updated_at.isoformat()
        } for s in sessions]
        return jsonify(sessions_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API to get messages for a specific session
@app.route('/api/chat_sessions/<int:session_id>/messages', methods=['GET'])
def get_session_messages(session_id):
    try:
        chat_session = ChatSession.query.get_or_404(session_id)
        messages = [{
            'role': m.role,
            'content': m.content,
            'timestamp': m.timestamp.isoformat(),
            'mode': m.mode
        } for m in chat_session.messages]
        return jsonify(messages)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API to create a new chat session
@app.route('/api/chat_sessions/new', methods=['POST'])
def create_new_chat_session():
    try:
        data = request.json
        title = data.get('title', 'New Chat')
        
        new_session = ChatSession(title=title)
        db.session.add(new_session)
        db.session.commit()
        
        session['current_session_id'] = new_session.id
        session['chat_history'] = []
        
        return jsonify({
            'id': new_session.id,
            'title': new_session.title,
            'created_at': new_session.created_at.isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API to delete a chat session
@app.route('/api/chat_sessions/<int:session_id>', methods=['DELETE'])
def delete_chat_session(session_id):
    try:
        chat_session = ChatSession.query.get_or_404(session_id)
        db.session.delete(chat_session)
        db.session.commit()
        
        if session.get('current_session_id') == session_id:
            session['current_session_id'] = None
            session['chat_history'] = []
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API endpoint for chat
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '').strip()
        mode = data.get('mode', 'auto')
        
        if not message:
            return jsonify({'error': 'Empty message'}), 400
        
        # Store mode in session
        session['mode'] = mode
        
        # Auto-detect intent if mode is auto
        if mode == 'auto':
            mode = classify_intent(message)
        
        # Check if user is asking for PDF
        is_pdf_request = is_pdf_query(message)
        
        if mode == 'weather':
            response = handle_weather_query(message)
        else:
            response = handle_isro_query(message)
        
        # Remove any duplicate content from the response
        response = remove_duplicate_content(response)
        
        # Format the response for better HTML display
        formatted_response = format_response_for_html(response)
        
        # Add to session chat history
        session['chat_history'].append({
            'user': message,
            'assistant': response,
            'mode': mode
        })
        
        # Save to database if we have an active session
        if session.get('current_session_id'):
            try:
                chat_session = ChatSession.query.get(session['current_session_id'])
                if chat_session:
                    # Add user message
                    user_msg = ChatMessage(
                        session_id=chat_session.id,
                        role='user',
                        content=message,
                        mode=mode
                    )
                    db.session.add(user_msg)
                    
                    # Add assistant message
                    assistant_msg = ChatMessage(
                        session_id=chat_session.id,
                        role='assistant',
                        content=response,
                        mode=mode
                    )
                    db.session.add(assistant_msg)
                    
                    # Update session title if it's the first message
                    if len(chat_session.messages) == 0:
                        chat_session.title = message[:50] + "..." if len(message) > 50 else message
                    
                    chat_session.updated_at = datetime.datetime.utcnow()
                    db.session.commit()
            except Exception as e:
                print(f"Error saving to database: {e}")
        
        # Make sure to commit session changes
        session.modified = True
        
        # If PDF is requested, store the clean content for PDF generation
        if is_pdf_request:
            pdf_filename = f"response_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            # Store the cleaned response for PDF
            session['last_pdf_content'] = response
            session['last_pdf_filename'] = pdf_filename
            
            # Return response with HTML download link
            formatted_response += f'\n\n<div class="pdf-container"><a href="/download-pdf/{pdf_filename}" class="pdf-link" target="_blank">📄 Download as PDF</a></div>'
        
        return jsonify({
            'response': formatted_response,
            'mode': mode,
            'has_pdf': is_pdf_request
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API endpoint to set region
@app.route('/set_region', methods=['POST'])
def set_region():
    try:
        data = request.json
        region = data.get('region', '').strip()
        
        if not region:
            return jsonify({'error': 'Region is required'}), 400
        
        # Check if region is valid by geocoding
        coords = geocode_city(region)
        if not coords:
            return jsonify({'error': 'Could not find location. Please try a different name.'}), 400
        
        # Generate weather context for this region
        save_weather_context(region)
        
        # Store region in session
        session['current_region'] = region
        session.modified = True
        
        return jsonify({
            'success': True,
            'message': f'Region set to {region}',
            'region': region
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API endpoint to clear chat
@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    session['chat_history'] = []
    session.modified = True
    return jsonify({'success': True})

# Add this endpoint to your Flask app (somewhere with the other API endpoints)
@app.route('/api/chat_sessions/<int:session_id>/rename', methods=['POST'])
def rename_chat_session(session_id):
    try:
        data = request.json
        new_title = data.get('title', '').strip()
        
        if not new_title:
            return jsonify({'error': 'Title is required'}), 400
        
        chat_session = ChatSession.query.get_or_404(session_id)
        chat_session.title = new_title
        chat_session.updated_at = datetime.datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'id': chat_session.id,
            'title': chat_session.title,
            'updated_at': chat_session.updated_at.isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# PDF download endpoint
@app.route('/download-pdf/<filename>')
def download_pdf(filename):
    try:
        content = session.get('last_pdf_content', '')
        if not content:
            return jsonify({'error': 'No PDF content available'}), 404
        
        # Remove duplicate sections by processing the content
        content = remove_duplicate_content(content)
        
        # Create PDF with proper formatting
        pdf = FPDF()
        pdf.add_page()
        
        # Add a Unicode-compatible font
        pdf.set_font("Arial", size=12)
        
        # Add title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="AstroBot Response", ln=True, align='C')
        pdf.ln(15)
        
        # Add timestamp
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(200, 10, txt=f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
        pdf.ln(10)
        
        # Process content with proper formatting
        pdf.set_font("Arial", size=12)
        
        # Clean content of problematic Unicode characters
        def clean_text(text):
            # Replace problematic characters
            text = text.replace('•', '-')
            text = text.replace('–', '-')
            text = text.replace('—', '-')
            text = text.replace('"', "'")
            return text
        
        # Split content into paragraphs while preserving structure
        paragraphs = content.split('\n\n')
        processed_paragraphs = []
        
        for paragraph in paragraphs:
            paragraph = clean_text(paragraph.strip())
            if not paragraph:
                continue
                
            # Skip duplicate paragraphs
            if paragraph in processed_paragraphs:
                continue
                
            processed_paragraphs.append(paragraph)
            
            # Handle headers
            if paragraph.startswith('# '):
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, txt=paragraph[2:].strip(), ln=True)
                pdf.set_font("Arial", size=12)
                pdf.ln(5)
                
            elif paragraph.startswith('## '):
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 8, txt=paragraph[3:].strip(), ln=True)
                pdf.set_font("Arial", size=12)
                pdf.ln(4)
                
            # Handle list items
            elif paragraph.startswith('* ') or any(line.strip().startswith('* ') for line in paragraph.split('\n')):
                lines = paragraph.split('\n')
                for line in lines:
                    if line.strip().startswith('* '):
                        pdf.cell(10)
                        pdf.cell(5, 6, txt="-", ln=0)
                        pdf.cell(5)
                        list_text = re.sub(r'\*\*(.*?)\*\*', r'\1', line[2:].strip())
                        list_text = clean_text(list_text)
                        pdf.multi_cell(0, 6, txt=list_text)
                        pdf.ln(2)
                pdf.ln(4)
                pdf.set_left_margin(10)
                
            # Handle regular paragraphs
            else:
                clean_paragraph = re.sub(r'\*\*(.*?)\*\*', r'\1', paragraph)
                clean_paragraph = clean_text(clean_paragraph)
                pdf.multi_cell(0, 6, txt=clean_paragraph)
                pdf.ln(6)
        
        # Add footer
        pdf.set_y(-15)
        pdf.set_font("Arial", 'I', 8)
        pdf.cell(0, 10, txt="Powered by MOSDAC (ISRO) - AstroBot", align='C')
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        pdf.output(temp_file.name)
        
        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"PDF generation error: {e}")
        return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_ENV", "development") == "development"
    app.run(debug=debug_mode, port=port)