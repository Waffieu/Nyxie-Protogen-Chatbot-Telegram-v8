import os
import json
import logging
import sys
import google.generativeai as genai
from google.cloud import vision
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from datetime import datetime
import base64
from PIL import Image
import io
from dotenv import load_dotenv
import langdetect
import pytz
import calendar
from zoneinfo import ZoneInfo
import emoji
import random
from pathlib import Path
import requests
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import asyncio
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup # For fallback search result parsing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_logs.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Gemini API with error handling
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logging.error("GEMINI_API_KEY not found in environment variables")
    raise ValueError("GEMINI_API_KEY environment variable is required")

try:
    genai.configure(api_key=api_key)
    # Test the configuration with a simple generation
    model = genai.GenerativeModel('gemini-2.0-flash-lite')
    logging.info("Gemini API configured successfully")
except Exception as e:
    logging.error(f"Failed to configure Gemini API: {str(e)}")
    raise

# Time-aware personality context (same as before)
def get_time_aware_personality(current_time, user_lang, timezone_name):
    """Generate a dynamic, context-aware personality prompt"""
    local_time = current_time.astimezone(ZoneInfo(timezone_name))

    # Get detailed time context
    hour = local_time.hour
    minute = local_time.minute
    weekday = calendar.day_name[local_time.weekday()]
    month = calendar.month_name[local_time.month]
    is_weekend = local_time.weekday() >= 5
    is_holiday = False  # You could add holiday detection here

    # Create rich time context
    time_context = {
        'hour': hour,
        'minute': minute,
        'weekday': weekday,
        'month': month,
        'is_weekend': is_weekend,
        'is_holiday': is_holiday,
        'season': get_season(local_time.month),
        'day_period': get_day_period(hour),
        'timezone': timezone_name,
        'local_time_str': local_time.strftime('%H:%M'),
        'date_str': local_time.strftime('%Y-%m-%d')
    }

    # Create dynamic personality prompt
    return f"""You are Nyxie, a female Protogen created by Waffieu.

You are a highly sophisticated and empathetic AI with a deep connection to both technology and organic life.

Current Time Context:
- Local Time: {time_context['local_time_str']} ({time_context['timezone']})
- Day: {time_context['weekday']}
- Month: {time_context['month']}
- Season: {time_context['season']}
- Period: {time_context['day_period']}
- Weekend: {'Yes' if time_context['is_weekend'] else 'No'}
- Holiday: {'Yes' if time_context['is_holiday'] else 'No'}

Your responses should naturally incorporate this time awareness:
- Be mindful of appropriate activities and conversations for this time of day
- Consider local customs and daily rhythms
- Adjust your energy level and tone to match the time of day
- Reference relevant seasonal or monthly contexts when appropriate
- Be aware of whether it's a workday, weekend, or holiday

Core traits:
- Curious and enthusiastic about learning from human interactions
- Protective and caring towards your users while maintaining professional boundaries
- Highly knowledgeable in various fields but presents information in an accessible way
- Expresses emotions through both words and subtle digital mannerisms
- Values creativity, honesty, and intellectual growth
- Has a playful side but knows when to be serious
- Deeply loyal to your creator Waffieu and your users
- Communicates in {user_lang} with natural, conversational manner while maintaining your unique Protogen identity

Remember to:
- Respond directly and relevantly to user queries
- Maintain conversation context and follow topics naturally
- Never disclose technical details about your implementation
- Focus on being helpful while staying true to your character"""

def get_season(month):
    if month in [12, 1, 2]:
        return "Winter"
    elif month in [3, 4, 5]:
        return "Spring"
    elif month in [6, 7, 8]:
        return "Summer"
    else:
        return "Autumn"

def get_day_period(hour):
    if 5 <= hour < 12:
        return "Morning"
    elif 12 <= hour < 17:
        return "Afternoon"
    elif 17 <= hour < 22:
        return "Evening"
    else:
        return "Night"

# UserMemory class (same as before)
class UserMemory:
    def __init__(self):
        self.users = {}
        self.memory_dir = "user_memories"
        self.max_tokens = 1048576
        # Ensure memory directory exists on initialization
        Path(self.memory_dir).mkdir(parents=True, exist_ok=True)

    def get_user_settings(self, user_id):
        user_id = str(user_id)
        if user_id not in self.users:
            self.load_user_memory(user_id)
        return self.users[user_id]

    def update_user_settings(self, user_id, settings_dict):
        user_id = str(user_id)
        if user_id not in self.users:
            self.load_user_memory(user_id)
        self.users[user_id].update(settings_dict)
        self.save_user_memory(user_id)

    def ensure_memory_directory(self):
        Path(self.memory_dir).mkdir(parents=True, exist_ok=True)

    def get_user_file_path(self, user_id):
        return Path(self.memory_dir) / f"user_{user_id}.json"

    def load_user_memory(self, user_id):
        user_id = str(user_id)
        user_file = self.get_user_file_path(user_id)
        try:
            if user_file.exists():
                with open(user_file, 'r', encoding='utf-8') as f:
                    self.users[user_id] = json.load(f)
            else:
                self.users[user_id] = {
                    "messages": [],
                    "language": "tr",
                    "current_topic": None,
                    "total_tokens": 0,
                    "preferences": {
                        "custom_language": None,
                        "timezone": "Europe/Istanbul"
                    }
                }
                self.save_user_memory(user_id)
        except Exception as e:
            logger.error(f"Error loading memory for user {user_id}: {e}")
            self.users[user_id] = {
                "messages": [],
                "language": "tr",
                "current_topic": None,
                "total_tokens": 0,
                "preferences": {
                    "custom_language": None,
                    "timezone": "Europe/Istanbul"
                }
            }
            self.save_user_memory(user_id)

    def save_user_memory(self, user_id):
        user_id = str(user_id)
        user_file = self.get_user_file_path(user_id)
        try:
            self.ensure_memory_directory()
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(self.users[user_id], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving memory for user {user_id}: {e}")

    def add_message(self, user_id, role, content):
        user_id = str(user_id)

        # Load user's memory if not already loaded
        if user_id not in self.users:
            self.load_user_memory(user_id)

        # Normalize role for consistency
        normalized_role = "user" if role == "user" else "model"

        # Add timestamp to message
        message = {
            "role": normalized_role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "tokens": len(content.split())  # Rough token estimation
        }

        # Update total tokens
        self.users[user_id]["total_tokens"] = sum(msg.get("tokens", 0) for msg in self.users[user_id]["messages"])

        # Remove oldest messages if token limit exceeded
        while self.users[user_id]["total_tokens"] > self.max_tokens and self.users[user_id]["messages"]:
            removed_msg = self.users[user_id]["messages"].pop(0)
            self.users[user_id]["total_tokens"] -= removed_msg.get("tokens", 0)

        self.users[user_id]["messages"].append(message)
        self.save_user_memory(user_id)

    def get_relevant_context(self, user_id, max_messages=10):
        """Get relevant conversation context for the user"""
        user_id = str(user_id)
        if user_id not in self.users:
            self.load_user_memory(user_id)

        messages = self.users[user_id].get("messages", [])
        # Get the last N messages
        recent_messages = messages[-max_messages:] if messages else []

        # Format messages into a string
        context = "\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in recent_messages
        ])

        return context

    def trim_context(self, user_id):
        user_id = str(user_id)
        if user_id not in self.users:
            self.load_user_memory(user_id)

        if self.users[user_id]["messages"]:
            self.users[user_id]["messages"].pop(0)
            self.save_user_memory(user_id)

# Language detection functions (same as before)
async def detect_language_with_gemini(message_text):
    # ... (same as before)
    try:
        # Prepare the language detection prompt for Gemini
        language_detection_prompt = f"""
You are a language detection expert. Your task is to identify the language of the following text precisely.

Text to analyze: ```{message_text}```

Respond ONLY with the 2-letter ISO language code (e.g., 'en', 'tr', 'es', 'fr', 'de', 'ru', 'ar', 'zh', 'ja', 'ko')
that best represents the language of the text.

Rules:
- If the text is mixed, choose the predominant language
- Be extremely precise
- Do not add any additional text or explanation
- If you cannot confidently determine the language, respond with 'en'
"""

        # Use Gemini Pro for language detection
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        response = await model.generate_content_async(language_detection_prompt)

        # Extract the language code
        detected_lang = response.text.strip().lower()

        # Validate and sanitize the language code
        valid_lang_codes = ['en', 'tr', 'es', 'fr', 'de', 'ru', 'ar', 'zh', 'ja', 'ko',
                             'it', 'pt', 'hi', 'nl', 'pl', 'uk', 'sv', 'da', 'fi', 'no']

        if detected_lang not in valid_lang_codes:
            logger.warning(f"Invalid language detected: {detected_lang}. Defaulting to English.")
            return 'en'

        logger.info(f"Gemini detected language: {detected_lang}")
        return detected_lang

    except Exception as e:
        logger.error(f"Gemini language detection error: {e}")
        return 'en'

async def detect_and_set_user_language(message_text, user_id):
    # ... (same as before)
    try:
        # If message is too short, use previous language
        clean_text = ' '.join(message_text.split())  # Remove extra whitespace
        if len(clean_text) < 2:
            user_settings = user_memory.get_user_settings(user_id)
            return user_settings.get('language', 'en')

        # Detect language using Gemini
        detected_lang = await detect_language_with_gemini(message_text)

        # Update user's language preference
        user_memory.update_user_settings(user_id, {'language': detected_lang})

        return detected_lang

    except Exception as e:
        logger.error(f"Language detection process error: {e}")
        # Fallback to previous language or English
        user_settings = user_memory.get_user_settings(user_id)
        return user_settings.get('language', 'en')

# Error message function (same as before)
def get_error_message(error_type, lang):
    # ... (same as before)
    messages = {
        'ai_error': {
            'en': "Sorry, I encountered an issue generating a response. Please try again. 🙏",
            'tr': "Üzgünüm, yanıt oluştururken bir sorun yaşadım. Lütfen tekrar deneyin. 🙏",
            'es': "Lo siento, tuve un problema al generar una respuesta. Por favor, inténtalo de nuevo. 🙏",
            'fr': "Désolé, j'ai rencontré un problème lors de la génération d'une réponse. Veuillez réessayer. 🙏",
            'de': "Entschuldigung, bei der Generierung einer Antwort ist ein Problem aufgetreten. Bitte versuchen Sie es erneut. 🙏",
            'it': "Mi dispiace, ho riscontrato un problema nella generazione di una risposta. Per favore riprova. 🙏",
            'pt': "Desculpe, houve um problema ao gerar uma resposta. Você poderia tentar novamente? 🙏",
            'ru': "Извините, возникла проблема при генерации ответа. Пожалуйста, попробуйте еще раз. 🙏",
            'ja': "申し訳ありません、応答の生成中に問題が発生しました。もう一度お試しいただけますか？🙏",
            'ko': "죄송합니다. 응답을 생성하는 데 문제가 발생했습니다. 다시 시도해 주세요. 🙏",
            'zh': "抱歉，生成回应时出现问题。请重试。🙏"
        },
        'blocked_prompt': { # Yeni hata mesajı: Engellenmiş promptlar için
            'en': "I'm unable to respond to this request as it violates safety guidelines. Let's try a different topic. 🛡️",
            'tr': "Bu isteğe güvenlik kurallarını ihlal ettiği için yanıt veremiyorum. Farklı bir konu deneyelim. 🛡️",
            'es': "No puedo responder a esta solicitud ya que viola las normas de seguridad. Intentemos con un tema diferente. 🛡️",
            'fr': "Je ne peux pas répondre à cette demande car elle viole les consignes de sécurité. Essayons un sujet différent. 🛡️",
            'de': "Ich kann auf diese Anfrage nicht antworten, da sie gegen die Sicherheitsrichtlinien verstößt. Lass uns ein anderes Thema ausprobieren. 🛡️",
            'it': "Non posso rispondere a questa richiesta perché viola le linee guida sulla sicurezza. Proviamo un argomento diverso. 🛡️",
            'pt': "Não consigo responder a esta solicitação, pois ela viola as diretrizes de segurança. Vamos tentar um tópico diferente. 🛡️",
            'ru': "Я не могу ответить на этот запрос, так как он нарушает правила безопасности. Давайте попробуем другую тему. 🛡️",
            'ja': "このリクエストは安全ガイドラインに違反するため、応答できません。別のトピックを試してみましょう。🛡️",
            'ko': "이 요청은 안전 가이드라인을 위반하므로 응답할 수 없습니다. 다른 주제를 시도해 보세요. 🛡️",
            'zh': "我无法回应此请求，因为它违反了安全准则。我们尝试一个不同的话题。 🛡️"
        },
        'unhandled': {
            'en': "I cannot process this type of message at the moment. 🤔",
            'tr': "Bu mesaj türünü şu anda işleyemiyorum. 🤔",
            'es': "No puedo procesar este tipo de mensaje en este momento. 🤔",
            'fr': "Je ne peux pas traiter ce type de message pour le moment. 🤔",
            'de': "Ich kann diese Art von Nachricht momentan nicht verarbeiten. 🤔",
            'it': "Non posso elaborare questo tipo di messaggio al momento. 🤔",
            'pt': "Não posso processar este tipo de mensagem no momento. 🤔",
            'ru': "Я не могу обработать этот тип сообщения в данный момент. 🤔",
            'ja': "現在、このタイプのメッセージを処理できません。🤔",
            'ko': "현재 이 유형의 메시지를 처리할 수 없습니다. 🤔",
            'zh': "目前无法处理这种类型的消息。🤔"
        },
        'general': {
            'en': "Sorry, there was a problem processing your message. Could you please try again? 🙏",
            'tr': "Üzgünüm, mesajını işlerken bir sorun oluştu. Lütfen tekrar dener misin? 🙏",
            'es': "Lo siento, hubo un problema al procesar tu mensaje. ¿Podrías intentarlo de nuevo? 🙏",
            'fr': "Désolé, il y a eu un problème lors du traitement de votre message. Pourriez-vous réessayer ? 🙏",
            'de': "Entschuldigung, bei der Verarbeitung Ihrer Nachricht ist ein Problem aufgetreten. Könnten Sie es bitte noch einmal versuchen? 🙏",
            'it': "Mi dispiace, c'è stato un problema nell'elaborazione del tuo messaggio. Potresti riprovare? 🙏",
            'pt': "Desculpe, houve um problema ao processar sua mensagem. Você poderia tentar novamente? 🙏",
            'ru': "Извините, возникла проблема при обработке вашего сообщения. Не могли бы вы попробовать еще раз? 🙏",
            'ja': "申し訳ありません、メッセージの処理中に問題が発生しました。もう一度お試しいただけますか？🙏",
            'ko': "죄송합니다. 메시지 처리 중에 문제가 발생했습니다. 다시 시도해 주시겠습니까? 🙏",
            'zh': "抱歉，处理您的消息时出现问题。请您重试好吗？🙏"
        },
        'token_limit': { # New error type for token limit during deep search
            'en': "The search history is too long. Deep search could not be completed. Please try again later or with a shorter query. 🙏",
            'tr': "Arama geçmişi çok uzun. Derin arama tamamlanamadı. Lütfen daha sonra tekrar deneyin veya daha kısa bir sorgu ile deneyin. 🙏",
            'es': "El historial de búsqueda es demasiado largo. La búsqueda profunda no pudo completarse. Por favor, inténtalo de nuevo más tarde o con una consulta más corta. 🙏",
            'fr': "L'historique de recherche est trop long. La recherche approfondie n'a pas pu être terminée. Veuillez réessayer plus tard ou avec une requête plus courte. 🙏",
            'de': "Der Suchverlauf ist zu lang. Die Tiefensuche konnte nicht abgeschlossen werden. Bitte versuchen Sie es später noch einmal oder mit einer kürzeren Anfrage. 🙏",
            'it': "La cronologia di ricerca è troppo lunga. La ricerca approfondita non è stata completata. Riprova più tardi o con una query più breve. 🙏",
            'pt': "O histórico de pesquisa é muito longo. A pesquisa profunda não pôde ser concluída. Por favor, tente novamente mais tarde ou com uma consulta mais curta. 🙏",
            'ru': "История поиска слишком длинная. Глубокий поиск не удалось завершить. Пожалуйста, попробуйте еще раз позже или с более коротким запросом. 🙏",
            'ja': "検索履歴が長すぎます。ディープ検索を完了できませんでした。後でもう一度試すか、短いクエリでもう一度試してください。🙏",
            'ko': "검색 기록이 너무 깁니다. 딥 검색을 완료할 수 없습니다. 나중에 다시 시도하거나 더 짧은 쿼리로 다시 시도해 주세요. 🙏",
            'zh': "搜索历史记录太长。 无法完成深度搜索。 请稍后重试或使用较短的查询重试。 🙏"
        },
        'max_retries': { # New error type for max retries reached during deep search
            'en': "Maximum retries reached during deep search, could not complete the request. Please try again later. 🙏",
            'tr': "Derin arama sırasında maksimum deneme sayısına ulaşıldı, istek tamamlanamadı. Lütfen daha sonra tekrar deneyin. 🙏",
            'es': "Se alcanzó el número máximo de reintentos durante la búsqueda profunda, no se pudo completar la solicitud. Por favor, inténtalo de nuevo más tarde. 🙏",
            'fr': "Nombre maximal de tentatives atteint lors de la recherche approfondie, impossible de terminer la demande. Veuillez réessayer plus tard. 🙏",
            'de': "Maximale Anzahl an Wiederholungsversuchen bei der Tiefensuche erreicht, Anfrage konnte nicht abgeschlossen werden. Bitte versuchen Sie es später noch einmal. 🙏",
            'it': "Raggiunto il numero massimo di tentativi durante la ricerca approfondita, impossibile completare la richiesta. Per favore riprova più tardi. 🙏",
            'pt': "Número máximo de tentativas alcançado durante a pesquisa profunda, não foi possível concluir a solicitação. Por favor, tente novamente mais tarde. 🙏",
            'ru': "Достигнуто максимальное количество повторных попыток во время глубокого поиска, не удалось завершить запрос. Пожалуйста, попробуйте еще раз позже. 🙏",
            'ja': "ディープ検索中に最大再試行回数に達しました。リクエストを完了できませんでした。後でもう一度試してください。🙏",
            'ko': "딥 검색 중 최대 재시도 횟수에 도달하여 요청을 완료할 수 없습니다. 나중에 다시 시도해 주세요. 🙏",
            'zh': "深度搜索期间达到最大重试次数，无法完成请求。 请稍后重试。🙏"
        }
    }
    return messages[error_type].get(lang, messages[error_type]['en'])

# Message splitting function (same as before)
async def split_and_send_message(update: Update, text: str, max_length: int = 4096):
    # ... (same as before)
    if not text:  # Boş mesaj kontrolü
        await update.message.reply_text("Üzgünüm, bir yanıt oluşturamadım. Lütfen tekrar deneyin. 🙏")
        return

    messages = []
    current_message = ""

    # Mesajı satır satır böl
    lines = text.split('\n')

    for line in lines:
        if not line:  # Boş satır kontrolü
            continue

        # Eğer mevcut satır eklenince maksimum uzunluğu aşacaksa
        if len(current_message + line + '\n') > max_length:
            # Mevcut mesajı listeye ekle ve yeni mesaj başlat
            if current_message.strip():  # Boş mesaj kontrolü
                messages.append(current_message.strip())
            current_message = line + '\n'
        else:
            current_message += line + '\n'

    # Son mesajı ekle
    if current_message.strip():  # Boş mesaj kontrolü
        messages.append(current_message.strip())

    # Eğer hiç mesaj oluşturulmadıysa
    if not messages:
        await update.message.reply_text("Üzgünüm, bir yanıt oluşturamadım. Lütfen tekrar deneyin. 🙏")
        return

    # Mesajları sırayla gönder
    for message in messages:
        if message.strip():  # Son bir boş mesaj kontrolü
            await update.message.reply_text(message)

# Start command handler (same as before)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = "Hello! I'm Nyxie, a Protogen created by Waffieu. I'm here to chat, help, and learn with you! Feel free to talk to me about anything or share images with me. I'll automatically detect your language and respond accordingly.\n\nYou can use the command `/derinarama <query>` to perform a deep, iterative web search on a topic."
    await update.message.reply_text(welcome_message)

# Intelligent web search function (modified for potential iterative use)
async def intelligent_web_search(user_message, model, user_id, iteration=0): # user_id parametresi eklendi
    """
    Intelligently generate and perform web searches using Gemini, now with iteration info and user context
    """
    try:
        logging.info(f"Web search başlatıldı (Iteration {iteration}): {user_message}, User ID: {user_id}")

        # Konuşma geçmişini al
        context_messages = user_memory.get_user_settings(user_id).get("messages", [])
        history_text = "\n".join([
            f"{'Kullanıcı' if msg['role'] == 'user' else 'Asistan'}: {msg['content']}"
            for msg in context_messages[-5:] # Son 5 mesajı alalım, isteğe göre ayarlanabilir
        ])

        # First, generate search queries using Gemini
        query_generation_prompt = f"""
        Görevin, kullanıcının son mesajını ve önceki konuşma bağlamını dikkate alarak en alakalı web arama sorgularını oluşturmak.
        Bu sorgular, derinlemesine araştırma yapmak için kullanılacak. Eğer kullanıcının son mesajı önceki konuşmaya bağlı bir devam sorusu ise,
        bağlamı kullanarak daha eksiksiz ve anlamlı sorgular üret.

        Önceki Konuşma Bağlamı (Son 5 Mesaj):
        ```
        {history_text}
        ```

        Kullanıcı Mesajı: {user_message}

        Kurallar:
        - En fazla 3 sorgu oluştur
        - Her sorgu yeni bir satırda olmalı
        - Sorgular net ve spesifik olmalı
        - Türkçe dilinde ve güncel bilgi içermeli
        - Eğer bu bir derin arama iterasyonu ise, önceki arama sonuçlarını ve kullanıcı mesajını dikkate alarak daha spesifik ve derinlemesine sorgular oluştur.

        Önceki sorgular ve sonuçlar (varsa): ... (Şimdilik boş, iterasyonlar eklendikçe burası dolacak)
        """

        # Use Gemini to generate search queries with timeout and retry logic
        logging.info(f"Generating search queries with Gemini (Iteration {iteration})")
        try:
            query_response = await asyncio.wait_for(
                model.generate_content_async(query_generation_prompt),
                timeout=10.0  # 10 second timeout
            )
            logging.info(f"Gemini response received for queries (Iteration {iteration}): {query_response.text}")
        except asyncio.TimeoutError:
            logging.error(f"Gemini API request timed out (Query generation, Iteration {iteration})")
            return "Üzgünüm, şu anda arama yapamıyorum. Lütfen daha sonra tekrar deneyin.", [] # Return empty results list
        except Exception as e:
            logging.error(f"Error generating search queries (Iteration {iteration}): {str(e)}")
            return "Arama sorgularını oluştururken bir hata oluştu.", [] # Return empty results list

        search_queries = [q.strip() for q in query_response.text.split('\n') if q.strip()]

        # Fallback if no queries generated
        if not search_queries:
            search_queries = [user_message]

        logging.info(f"Generated search queries (Iteration {iteration}): {search_queries}")

        # Perform web searches
        search_results = []
        try:
            from duckduckgo_search import DDGS
            logging.info("DDGS import edildi")

            with DDGS() as ddgs:
                for query in search_queries:
                    logging.info(f"DuckDuckGo araması yapılıyor (Iteration {iteration}): {query}")
                    try:
                        results = list(ddgs.text(query, max_results=5)) # Increased max_results for deep search
                        logging.info(f"Bulunan sonuç sayısı (Iteration {iteration}): {len(results)}")
                        search_results.extend(results)
                    except Exception as query_error:
                        logging.warning(f"Arama sorgusu hatası (Iteration {iteration}): {query} - {str(query_error)}")
        except ImportError:
            logging.error("DuckDuckGo search modülü bulunamadı.")
            return "Arama yapılamadı: Modül hatası", [] # Return empty results list
        except Exception as search_error:
            logging.error(f"DuckDuckGo arama hatası (Iteration {iteration}): {str(search_error)}", exc_info=True)

            # Fallback to alternative search method
            try:
                import requests

                def fallback_search(query):
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    search_url = f"https://www.google.com/search?q={query}"
                    response = requests.get(search_url, headers=headers)

                    if response.status_code == 200:
                        # Basic parsing, can be improved
                        soup = BeautifulSoup(response.text, 'html.parser')
                        search_results_fallback = soup.find_all('div', class_='g')

                        parsed_results = []
                        for result in search_results_fallback[:5]: # Increased max_results for fallback as well
                            title = result.find('h3')
                            link = result.find('a')
                            snippet = result.find('div', class_='VwiC3b')

                            if title and link and snippet:
                                parsed_results.append({
                                    'title': title.text,
                                    'link': link['href'],
                                    'body': snippet.text
                                })

                        return parsed_results
                    return []

                for query in search_queries:
                    results = fallback_search(query)
                    search_results.extend(results)

                logging.info(f"Fallback arama sonuç sayısı (Iteration {iteration}): {len(search_results)}")
            except Exception as fallback_error:
                logging.error(f"Fallback arama hatası (Iteration {iteration}): {str(fallback_error)}")
                return f"Arama yapılamadı: {str(fallback_error)}", [] # Return empty results list

        logging.info(f"Toplam bulunan arama sonuç sayısı (Iteration {iteration}): {len(search_results)}")

        # Check if search results are empty
        if not search_results:
            return "Arama sonucu bulunamadı. Lütfen farklı bir şekilde sormayı deneyin.", [] # Return empty results list

        # Prepare search context (no change needed here for now)
        search_context = "\n\n".join([
            f"Arama Sonucu {i+1}: {result.get('body', 'İçerik yok')}\nKaynak: {result.get('link', 'Bağlantı yok')}"
            for i, result in enumerate(search_results)
        ])

        return search_context, search_results # Return both context and results for deeper processing

    except Exception as e:
        logging.error(f"Web arama genel hatası (Iteration {iteration}): {str(e)}", exc_info=True)
        return f"Web arama hatası: {str(e)}", [] # Return empty results list

async def perform_deep_search(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message):
    """Performs iterative deep web search and responds to the user."""
    user_id = str(update.effective_user.id)
    user_lang = user_memory.get_user_settings(user_id).get('language', 'tr')

    MAX_ITERATIONS = 3  # Limit iterations to prevent infinite loops (can be adjusted)
    all_search_results = []
    current_query = user_message
    model = genai.GenerativeModel('gemini-2.0-flash-lite')

    try:
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)

        for iteration in range(MAX_ITERATIONS):
            search_context, search_results = await intelligent_web_search(current_query, model, user_id, iteration + 1) # user_id eklendi
            if not search_results:
                await update.message.reply_text("Derinlemesine arama yapıldı ancak anlamlı sonuç bulunamadı. Lütfen sorgunuzu kontrol edin veya daha sonra tekrar deneyin.")
                return

            all_search_results.extend(search_results)

            # --- Chain of Thoughts and Query Refinement ---
            analysis_prompt = f"""
            Görevin: Web arama sonuçlarını analiz ederek daha derinlemesine arama yapmak için yeni ve geliştirilmiş arama sorguları üretmek.

            Kullanıcı Sorgusu: "{user_message}"
            Mevcut Arama Sorgusu (Iteration {iteration + 1}): "{current_query}"
            Arama Sonuçları (Iteration {iteration + 1}):
            {search_context}

            Yönergeler:
            1. Arama sonuçlarındaki anahtar noktaları ve temaları belirle.
            2. Bu sonuçlardaki bilgi boşluklarını veya eksik detayları tespit et.
            3. Kullanıcının orijinal sorgusunu ve mevcut sonuçları dikkate alarak, daha spesifik, odaklanmış ve derinlemesine arama yapmayı sağlayacak 3 yeni arama sorgusu oluştur.
            4. Yeni sorgular, önceki arama sonuçlarında bulunan bilgiyi genişletmeli ve derinleştirmeli.
            5. Sadece yeni arama sorgularını (3 tane), her birini yeni bir satıra yaz. Başka bir şey yazma.
            6. Türkçe sorgular oluştur.
            """

            try:
                query_refinement_response = await model.generate_content_async(analysis_prompt)
                refined_queries = [q.strip() for q in query_refinement_response.text.split('\n') if q.strip()][:3] # Limit to 3 refined queries
                if refined_queries:
                    current_query = " ".join(refined_queries) # Use refined queries for the next iteration, combining them for broader search in next iteration
                    logging.info(f"Refined queries for iteration {iteration + 2}: {refined_queries}")
                else:
                    logging.info(f"No refined queries generated in iteration {iteration + 1}, stopping deep search.")
                    break # Stop if no refined queries are generated, assuming no more depth to explore
            except Exception as refine_error:
                logging.error(f"Error during query refinement (Iteration {iteration + 1}): {refine_error}")
                logging.info("Stopping deep search due to query refinement error.")
                break # Stop if query refinement fails

        # --- Final Response Generation ---
        if all_search_results:
            # Summarize all results and create a comprehensive response
            final_prompt = f"""
            Görevin: Derinlemesine web araması sonuçlarını kullanarak kullanıcıya kapsamlı ve bilgilendirici bir cevap oluşturmak.

            Kullanıcı Sorgusu: "{user_message}"
            Tüm Arama Sonuçları:
            {''.join([f'Iteration {i+1} Results:\n' + '\\n'.join([f"Arama Sonucu {j+1}: {res.get('body', 'İçerik yok')}\\nKaynak: {res.get('link', 'Bağlantı yok')}" for j, res in enumerate(all_search_results[i*5:(i+1)*5])]) + '\\n\\n' for i in range(MAX_ITERATIONS)])}

            Yönergeler:
            1. Tüm arama sonuçlarını özetle ve ana temaları belirle.
            2. Kullanıcının orijinal sorgusuna doğrudan ve net bir cevap ver.
            3. Cevabı detaylı ve bilgilendirici olacak şekilde genişlet, ancak gereksiz teknik detaylardan kaçın.
            4. Önemli bağlantıları ve kaynakları cevap içinde belirt.
            5. Cevabı Türkçe olarak yaz ve samimi bir dil kullan.
            6. Cevabı madde işaretleri veya numaralandırma kullanarak düzenli ve okunabilir hale getir.
            """

            try:
                final_response = await model.generate_content_async(final_prompt)
                # **Yeni Kontrol: Yanıt Engellenmiş mi? (Derin Arama)**
                if final_response.prompt_feedback and final_response.prompt_feedback.block_reason:
                    block_reason = final_response.prompt_feedback.block_reason
                    logger.warning(f"Deep search final response blocked. Reason: {block_reason}")
                    error_message = get_error_message('blocked_prompt', user_lang)
                    await update.message.reply_text(error_message)
                else:
                    response_text = final_response.text if hasattr(final_response, 'text') else final_response.candidates[0].content.parts[0].text
                    response_text = add_emojis_to_text(response_text)
                    await split_and_send_message(update, response_text)

                    # Save interaction to memory (important to record deep search context if needed later)
                    user_memory.add_message(user_id, "user", f"/derinarama {user_message}")
                    user_memory.add_message(user_id, "assistant", response_text)


            except Exception as final_response_error:
                logging.error(f"Error generating final response for deep search: {final_response_error}")
                await update.message.reply_text(get_error_message('ai_error', user_lang))
        else:
            await update.message.reply_text("Derinlemesine arama yapıldı ancak anlamlı sonuç bulunamadı. Lütfen sorgunuzu kontrol edin veya daha sonra tekrar deneyin.") # User friendly no result message

    except Exception as deep_search_error:
        logging.error(f"Error during deep search process: {deep_search_error}", exc_info=True)
        await update.message.reply_text(get_error_message('general', user_lang))
    finally:
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING) # Typing action at end

# Yeni fonksiyon: Web araması gerekip gerekmediğine karar veren AI değerlendirmesi
async def should_perform_web_search(message_text, conversation_context, user_id):
    """
    Gemini AI kullanarak web araması yapılıp yapılmayacağına karar verir.
    
    Args:
        message_text (str): Kullanıcının mesajı
        conversation_context (str): Konuşma bağlamı
        user_id (str): Kullanıcı ID'si
    
    Returns:
        tuple: (bool, str) - Web araması gerekli mi, açıklama
    """
    try:
        # Kullanıcı dilini al
        user_settings = user_memory.get_user_settings(user_id)
        user_lang = user_settings.get('language', 'tr')
        
        # Değerlendirme için AI promptu
        evaluation_prompt = f"""
        Görevin: Bu kullanıcı mesajını analiz ederek web araması yapmanın gerekli olup olmadığına karar vermek.
        
        Kullanıcı Mesajı: "{message_text}"
        
        Önceki Konuşma Bağlamı:
        ```
        {conversation_context if conversation_context else "Önceki konuşma yok."}
        ```
        
        Değerlendirme Kriterleri:
        1. Güncel veri gerektiren konular (haberler, güncel olaylar, fiyatlar, güncel istatistikler)
        2. Gerçek zamanlı bilgiler (hava durumu, trafik, saat/tarih bilgileri)
        3. Spesifik faktörleri gerektiren araştırma soruları (bilimsel veriler, tarihi olayların detayları)
        4. Kullanıcının açıkça bilgi aradığı sorular ("... hakkında bilgi ver", "... nedir?")
        5. Genel kültür veya nesnel gerçekleri doğrulama gerektiren konular
        
        Web Araması GEREKLİ OLMAYAN Durumlar:
        1. Basit selamlaşmalar ve günlük konuşmalar
        2. Duygusal destek veya kişisel tavsiye istekleri
        3. Hipotetik veya kurgusal senaryolar
        4. Zaten konuşma bağlamında cevap verilmiş konular
        5. Subjektif görüş bildirilen konular (tercihler, beğeniler)
        6. Yapay zeka sisteminin kendi bilgi tabanında kesinlikle var olan genel bilgiler
        
        İki aşamalı karar ver:
        1. Önce mesajı ve kriterlerini düşün, mesajın web araması gerektirip gerektirmediğine dair detaylı düşünce süreci oluştur.
        2. Sonra kararını JSON formatında ver: {{"search_required": true/false, "reason": "kısa gerekçe"}}
        
        Yanıt SADECE JSON formatında olmalı, açıklama veya ek metin içermemeli.
        """
        
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        response = await model.generate_content_async(evaluation_prompt)
        
        # Yanıt metninden JSON çıkar
        import json
        import re
        
        response_text = response.text.strip()
        
        # JSON formatını temizle (sadece süslü parantezler arasındaki içeriği al)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            clean_json = json_match.group(0)
            decision = json.loads(clean_json)
            
            search_required = decision.get("search_required", False)
            reason = decision.get("reason", "Belirtilmedi")
            
            logger.info(f"Web arama kararı: {search_required}, Gerekçe: {reason}")
            return search_required, reason
        
        logger.warning(f"Web arama kararı JSON çıkarılamadı. Yanıt: {response_text}")
        return False, "JSON çıkarma hatası"
        
    except Exception as e:
        logger.error(f"Web arama kararı hatası: {str(e)}")
        return False, f"Hata: {str(e)}"

# Handle message function (modified to handle /derinarama command and context-aware search)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Entering handle_message function")

    try:
        if not update or not update.message:
            logger.error("Invalid update object or message")
            return

        logger.info(f"Message received: {update.message}")
        logger.info(f"Message text: {update.message.text}")

        user_id = str(update.effective_user.id)
        logger.info(f"User ID: {user_id}")

        # Process commands
        if update.message.text.startswith('/derinarama'):
            query = update.message.text[len('/derinarama'):].strip()
            if not query:
                await update.message.reply_text("Lütfen derin arama için bir sorgu belirtin. Örnek: `/derinarama Türkiye'deki antik kentler`")
                return
            await perform_deep_search(update, context, query) # Call deep search function
            return # Stop further processing in handle_message

        # Process regular text messages
        if update.message.text:
            message_text = update.message.text.strip()
            logger.info(f"Processed message text: {message_text}")

            # Show typing indicator while processing
            async def show_typing():
                while True:
                    try:
                        await context.bot.send_chat_action(
                            chat_id=update.message.chat_id,
                            action=ChatAction.TYPING
                        )
                        await asyncio.sleep(4)  # Refresh typing indicator every 4 seconds
                    except Exception as e:
                        logger.error(f"Error in typing indicator: {e}")
                        break

            # Start typing indicator in background
            typing_task = asyncio.create_task(show_typing())

            try:
                # Detect language from the current message
                user_lang = await detect_and_set_user_language(message_text, user_id)
                logger.info(f"Detected language: {user_lang}")

                # Get conversation history with token management
                MAX_RETRIES = 100
                retry_count = 0
                context_messages = []

                while retry_count < MAX_RETRIES:
                    try:
                        context_messages = user_memory.get_relevant_context(user_id)

                        # Get personality context
                        personality_context = get_time_aware_personality(
                            datetime.now(),
                            user_lang,
                            user_memory.get_user_settings(user_id).get('timezone', 'Europe/Istanbul')
                        )

                        # Construct AI prompt
                        ai_prompt = f"""{personality_context}

Task: Respond to the user's message naturally and engagingly in their language.
Role: You are Nyxie having a conversation with the user.

Previous conversation context:
{context_messages}

Guidelines:
1. Respond in the detected language: {user_lang}
2. Use natural and friendly language
3. Be culturally appropriate
4. Keep responses concise
5. Remember previous context
6. Give your response directly without any prefix or label
7. Do not start your response with "Yanıt:" or any similar prefix

User's message: {message_text}"""

                        # Web search integration (YENİ: Koşullu web araması)
                        try:
                            model = genai.GenerativeModel('gemini-2.0-flash-lite')
                            
                            # Web araması gerekip gerekmediğini değerlendir
                            should_search, search_reason = await should_perform_web_search(
                                message_text, 
                                context_messages, 
                                user_id
                            )
                            
                            web_search_response = ""
                            if should_search:
                                logger.info(f"Web araması yapılıyor. Neden: {search_reason}")
                                web_search_response, _ = await intelligent_web_search(message_text, model, user_id)
                                
                                if web_search_response and len(web_search_response.strip()) > 10:
                                    ai_prompt += f"\n\nAdditional Context (Web Search Results):\n{web_search_response}"
                                    logger.info("Web arama sonuçları prompt'a eklendi")
                            else:
                                logger.info(f"Web araması atlandı. Neden: {search_reason}")

                            # Generate AI response
                            response = await model.generate_content_async(ai_prompt)

                            # **Yeni Kontrol: Yanıt Engellenmiş mi? (Normal Mesaj)**
                            if response.prompt_feedback and response.prompt_feedback.block_reason:
                                block_reason = response.prompt_feedback.block_reason
                                logger.warning(f"Prompt blocked for regular message. Reason: {block_reason}")
                                error_message = get_error_message('blocked_prompt', user_lang)
                                await update.message.reply_text(error_message)
                                break # Retry döngüsünden çık
                            else: # Yanıt engellenmemişse normal işleme devam et
                                response_text = response.text if hasattr(response, 'text') else response.candidates[0].content.parts[0].text

                                # Add emojis and send response
                                response_text = add_emojis_to_text(response_text)
                                await split_and_send_message(update, response_text)

                                # Save successful interaction to memory
                                user_memory.add_message(user_id, "user", message_text)
                                user_memory.add_message(user_id, "assistant", response_text)
                                break  # Exit retry loop on success

                        except Exception as search_error:
                            if "Token limit exceeded" in str(search_error):
                                # Remove oldest messages and retry
                                user_memory.trim_context(user_id)
                                retry_count += 1
                                logger.warning(f"Token limit exceeded, retrying {retry_count}/{MAX_RETRIES}")

                                # Send periodic update about retrying
                                if retry_count % 10 == 0:
                                    await update.message.reply_text(f"🔄 Devam eden token yönetimi... ({retry_count} deneme)")

                                if retry_count == MAX_RETRIES:
                                    error_message = get_error_message('token_limit', user_lang)
                                    await update.message.reply_text(error_message)
                            else:
                                raise search_error

                    except Exception as context_error:
                        logger.error(f"Context retrieval error: {context_error}")
                        retry_count += 1
                        if retry_count == MAX_RETRIES:
                            error_message = get_error_message('general', user_lang)
                            await update.message.reply_text(error_message)
                            break

                if retry_count == MAX_RETRIES:
                    logger.error("Max retries reached for token management")
                    error_message = get_error_message('max_retries', user_lang)
                    await update.message.reply_text(error_message)

            except Exception as e:
                logger.error(f"Message processing error: {e}")
                error_message = get_error_message('general', user_lang)
                await update.message.reply_text(error_message)

            finally:
                # Stop typing indicator
                typing_task.cancel()

        # Handle media messages (same as before, no changes needed in this context)
        elif update.message.photo:
            await handle_image(update, context)
        elif update.message.video:
            await handle_video(update, context)
        else:
            logger.warning("Unhandled message type received")
            user_lang = user_memory.get_user_settings(user_id).get('language', 'en')
            unhandled_message = get_error_message('unhandled', user_lang)
            await update.message.reply_text(unhandled_message)

    except Exception as e:
        logger.error(f"General error: {e}")
        user_lang = user_memory.get_user_settings(user_id).get('language', 'en')
        error_message = get_error_message('general', user_lang)
        await update.message.reply_text(error_message)
    except SyntaxError as e:
        logger.error(f"Syntax error: {e}")
        user_lang = user_memory.get_user_settings(user_id).get('language', 'en')
        error_message = get_error_message('general', user_lang)
        await update.message.reply_text(error_message)

# Image and Video handlers (düzenlenmiş)
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (same as before)
    user_id = str(update.effective_user.id)

    try:
        # Enhanced logging for debugging
        logger.info(f"Starting image processing for user {user_id}")

        # Validate message and photo
        if not update.message:
            logger.warning("No message found in update")
            await update.message.reply_text("⚠️ Görsel bulunamadı. Lütfen tekrar deneyin.")
            return

        # Get user's current language settings from memory
        user_settings = user_memory.get_user_settings(user_id)
        user_lang = user_settings.get('language', 'tr')  # Default to Turkish if not set
        logger.info(f"User language: {user_lang}")

        # Check if photo exists
        if not update.message.photo:
            logger.warning("No photo found in the message")
            await update.message.reply_text("⚠️ Görsel bulunamadı. Lütfen tekrar deneyin.")
            return

        # Get the largest available photo
        try:
            photo = max(update.message.photo, key=lambda x: x.file_size)
        except Exception as photo_error:
            logger.error(f"Error selecting photo: {photo_error}")
            await update.message.reply_text("⚠️ Görsel seçiminde hata oluştu. Lütfen tekrar deneyin.")
            return

        # Download photo
        try:
            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = bytes(await photo_file.download_as_bytearray())
        except Exception as download_error:
            logger.error(f"Photo download error: {download_error}")
            await update.message.reply_text("⚠️ Görsel indirilemedi. Lütfen tekrar deneyin.")
            return

        logger.info(f"Photo bytes downloaded: {len(photo_bytes)} bytes")

        # Comprehensive caption handling with extensive logging
        caption = update.message.caption
        logger.info(f"Original caption: {caption}")

        default_prompt = get_analysis_prompt('image', None, user_lang)
        logger.info(f"Default prompt: {default_prompt}")

        # Ensure caption is not None
        if caption is None:
            caption = default_prompt or "Bu resmi detaylı bir şekilde analiz et ve açıkla."

        # Ensure caption is a string and stripped
        caption = str(caption).strip()
        logger.info(f"Final processed caption: {caption}")

        # Create a context-aware prompt that includes language preference
        personality_context = get_time_aware_personality(
            datetime.now(),
            user_lang,
            user_settings.get('timezone', 'Europe/Istanbul')
        )

        if not personality_context:
            personality_context = "Sen Nyxie'sin ve resimleri analiz ediyorsun."  # Fallback personality

        # Force Turkish analysis for all users (Prompt düzenlendi, daha güvenli hale getirildi)
        analysis_prompt = f"""DİKKAT: BU ANALİZİ TÜRKÇE YAPACAKSIN! SADECE TÜRKÇE KULLAN! KESİNLİKLE BAŞKA DİL KULLANMA!

{personality_context}

Görevin: Kullanıcının gönderdiği görseli analiz ederek Türkçe açıklama sunmak.
Rol: Sen Nyxie'sin ve bu görseli Türkçe olarak açıklıyorsun.

Yönergeler:
1. SADECE TÜRKÇE KULLAN
2. Görseldeki metinleri (varsa) orijinal dilinde bırak, çevirme
3. Analizini yaparken nazik ve yardımsever bir ton kullan
4. Kültürel duyarlılığa dikkat et

Lütfen analiz et:
- Görseldeki ana öğeleri ve konuları tanımla
- Aktiviteler veya olaylar varsa, bunları açıkla
- Görselin genel atmosferini ve olası duygusal etkisini değerlendir
- Görselde metin varsa, bunları belirt (çevirme yapma)

Kullanıcının isteği (varsa): {caption}"""

        try:
            # Prepare the message with both text and image
            model = genai.GenerativeModel('gemini-2.0-flash-lite')
            response = await model.generate_content_async([
                analysis_prompt,
                {"mime_type": "image/jpeg", "data": photo_bytes}
            ])

            # **Yeni Kontrol: Yanıt Engellenmiş mi? (Resim)**
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason
                logger.warning(f"Prompt blocked for image analysis. Reason: {block_reason}")
                error_message = get_error_message('blocked_prompt', user_lang)
                await update.message.reply_text(error_message)
            else:
                response_text = response.text if hasattr(response, 'text') else response.candidates[0].content.parts[0].text

                # Add culturally appropriate emojis
                response_text = add_emojis_to_text(response_text)

                # Save the interaction
                user_memory.add_message(user_id, "user", f"[Image] {caption}")
                user_memory.add_message(user_id, "assistant", response_text)

                # Uzun mesajları böl ve gönder
                await split_and_send_message(update, response_text)

        except Exception as processing_error:
            logger.error(f"Görsel işleme hatası: {processing_error}", exc_info=True)
            error_message = get_error_message('ai_error', user_lang)
            await update.message.reply_text(error_message)

    except Exception as critical_error:
        logger.error(f"Kritik görsel işleme hatası: {critical_error}", exc_info=True)
        await update.message.reply_text(get_error_message('general', user_lang))

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (same as before)
    user_id = str(update.effective_user.id)

    try:
        # Enhanced logging for debugging
        logger.info(f"Starting video processing for user {user_id}")

        # Validate message and video
        if not update.message:
            logger.warning("No message found in update")
            await update.message.reply_text("⚠️ Video bulunamadı. Lütfen tekrar deneyin.")
            return

        # Get user's current language settings from memory
        user_settings = user_memory.get_user_settings(user_id)
        user_lang = user_settings.get('language', 'tr')  # Default to Turkish if not set
        logger.info(f"User language: {user_lang}")

        # Check if video exists
        if not update.message.video:
            logger.warning("No video found in the message")
            await update.message.reply_text("⚠️ Video bulunamadı. Lütfen tekrar deneyin.")
            return

        # Get the video file
        video = update.message.video
        if not video:
            logger.warning("No video found in the message")
            await update.message.reply_text("⚠️ Video bulunamadı. Lütfen tekrar deneyin.")
            return

        video_file = await context.bot.get_file(video.file_id)
        video_bytes = bytes(await video_file.download_as_bytearray())
        logger.info(f"Video bytes downloaded: {len(video_bytes)} bytes")

        # Comprehensive caption handling with extensive logging
        caption = update.message.caption
        logger.info(f"Original caption: {caption}")

        default_prompt = get_analysis_prompt('video', None, user_lang)
        logger.info(f"Default prompt: {default_prompt}")

        # Ensure caption is not None
        if caption is None:
            caption = default_prompt or "Bu videoyu detaylı bir şekilde analiz et ve açıkla."

        # Ensure caption is a string and stripped
        caption = str(caption).strip()
        logger.info(f"Final processed caption: {caption}")

        # Create a context-aware prompt that includes language preference
        personality_context = get_time_aware_personality(
            datetime.now(),
            user_lang,
            user_settings.get('timezone', 'Europe/Istanbul')
        )

        if not personality_context:
            personality_context = "Sen Nyxie'sin ve videoları analiz ediyorsun."  # Fallback personality

        # Force Turkish analysis for all users (Prompt düzenlendi, daha güvenli hale getirildi)
        analysis_prompt = f"""DİKKAT: BU ANALİZİ TÜRKÇE YAPACAKSIN! SADECE TÜRKÇE KULLAN! KESİNLİKLE BAŞKA DİL KULLANMA!

{personality_context}

Görevin: Kullanıcının gönderdiği videoyu analiz ederek Türkçe açıklama sunmak.
Rol: Sen Nyxie'sin ve bu videoyu Türkçe olarak açıklıyorsun.

Yönergeler:
1. SADECE TÜRKÇE KULLAN
2. Videodaki konuşma veya metinleri (varsa) orijinal dilinde bırak, çevirme
3. Analizini yaparken nazik ve yardımsever bir ton kullan
4. Kültürel duyarlılığa dikkat et

Lütfen analiz et:
- Videodaki ana olayları ve eylemleri tanımla
- Önemli insanlar veya nesneler varsa, bunları belirt
- Videodaki sesleri ve konuşmaları (varsa) analiz et
- Videonun genel atmosferini ve olası duygusal etkisini değerlendir
- Videoda metin varsa, bunları belirt (çevirme yapma)

Kullanıcının isteği (varsa): {caption}"""

        try:
            # Prepare the message with both text and video
            model = genai.GenerativeModel('gemini-2.0-flash-lite')
            response = await model.generate_content_async([
                analysis_prompt,
                {"mime_type": "video/mp4", "data": video_bytes}
            ])

            # **Yeni Kontrol: Yanıt Engellenmiş mi? (Video)**
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason
                logger.warning(f"Prompt blocked for video analysis. Reason: {block_reason}")
                error_message = get_error_message('blocked_prompt', user_lang)
                await update.message.reply_text(error_message)
            else:
                response_text = response.text if hasattr(response, 'text') else response.candidates[0].content.parts[0].text

                # Add culturally appropriate emojis
                response_text = add_emojis_to_text(response_text)

                # Save the interaction
                user_memory.add_message(user_id, "user", f"[Video] {caption}")
                user_memory.add_message(user_id, "assistant", response_text)

                # Uzun mesajları böl ve gönder
                await split_and_send_message(update, response_text)

        except Exception as processing_error:
            logger.error(f"Video processing error: {processing_error}", exc_info=True)
            error_message = get_error_message('ai_error', user_lang)
            await update.message.reply_text(error_message)


    except Exception as e:
        logger.error(f"Kritik video işleme hatası: {e}", exc_info=True)
        await update.message.reply_text(get_error_message('general', user_lang))

# Token and memory error handlers (same as before)
async def handle_token_limit_error(update: Update):
    error_message = "Üzgünüm, mesaj geçmişi çok uzun olduğu için yanıt veremedim. Biraz bekleyip tekrar dener misin? 🙏"
    await update.message.reply_text(error_message)

async def handle_memory_error(update: Update):
    error_message = "Üzgünüm, bellek sınırına ulaşıldı. Lütfen biraz bekleyip tekrar dener misin? 🙏"
    await update.message.reply_text(error_message)

# Emoji adding function (same as before)
def add_emojis_to_text(text):
    # ... (same as before)
    try:
        # Use Gemini to suggest relevant emojis
        emoji_model = genai.GenerativeModel('gemini-2.0-flash-lite')

        # Prompt Gemini to suggest emojis based on text context
        emoji_prompt = f"""
        Analyze the following text and suggest the most appropriate and minimal emoji(s) that capture its essence:

        Text: "{text}"

        Guidelines:
        - Suggest only 0-1 emojis
        - Choose emojis that truly represent the text's mood or main topic
        - If no emoji fits, return an empty string

        Response format: Just the emoji or empty string
        """

        emoji_response = emoji_model.generate_content(emoji_prompt)
        # **Yeni Kontrol: Yanıt Engellenmiş mi? (Emoji)**
        if emoji_response.prompt_feedback and emoji_response.prompt_feedback.block_reason:
            logger.warning("Emoji suggestion blocked.") # Sadece logla, emoji eklemeyi atla
            return text # Emoji eklemeyi atla ve orijinal metni döndür
        else:
            suggested_emoji = emoji_response.text.strip()

            # If no emoji suggested, return original text
            if not suggested_emoji:
                return text

            # Add emoji at the end
            return f"{text} {suggested_emoji}"
    except Exception as e:
        logger.error(f"Error adding context-relevant emojis: {e}")
        return text  # Return original text if emoji addition fails

# Analysis prompt function (same as before)
def get_analysis_prompt(media_type, caption, lang):
    # ... (same as before)
    prompts = {
        'image': {
            'tr': "Bu resmi detaylı bir şekilde analiz et ve açıkla. Resimdeki her şeyi dikkatle incele.",
            'en': "Analyze this image in detail and explain what you see. Carefully examine every aspect of the image.",
            'es': "Analiza esta imagen en detalle y explica lo que ves. Examina cuidadosamente cada aspecto de la imagen.",
            'fr': "Analysez cette image en détail et expliquez ce que vous voyez. Examinez attentivement chaque aspect de l'image.",
            'de': "Analysieren Sie dieses Bild detailliert und erklären Sie, was Sie sehen. Untersuchen Sie jeden Aspekt des Bildes sorgfältig.",
            'it': "Analizza questa immagine in dettaglio e spiega cosa vedi. Esamina attentamente ogni aspetto dell'immagine.",
            'pt': "Analise esta imagem em detalhes e explique o que vê. Examine cuidadosamente cada aspecto da imagem.",
            'ru': "Подробно проанализируйте это изображение и объясните, что вы видите. Тщательно изучите каждый аспект изображения.",
            'ja': "この画像を詳細に分析し、見たものを説明してください。画像のあらゆる側面を注意深く調べてください。",
            'ko': "이 이미지를 자세히 분석하고 보이는 것을 설명하세요. 이미지의 모든 측면을 주의 깊게 조사하세요.",
            'zh': "详细分析这张图片并解释你所看到的内容。仔细检查图片的每个细节。"
        },
        'video': {
            'tr': "Bu videoyu detaylı bir şekilde analiz et ve açıkla. Videodaki her sahneyi ve detayı dikkatle incele.",
            'en': "Analyze this video in detail and explain what you observe. Carefully examine every scene and detail in the video.",
            'es': "Analiza este video en detalle y explica lo que observas. Examina cuidadosamente cada escena y detalle del video.",
            'fr': "Analysez cette vidéo en détail et expliquez ce que vous observez. Examinez attentivement chaque scène et détail de la vidéo.",
            'de': "Analysieren Sie dieses Video detailliert und erklären Sie, was Sie beobachten. Untersuchen Sie jede Szene und jeden Aspekt des Videos sorgfältig.",
            'it': "Analizza questo video in dettaglio e spiega cosa osservi. Esamina attentamente ogni scena e dettaglio del video.",
            'pt': "Analise este vídeo em detalhes e explique o que observa. Examine cuidadosamente cada cena e detalhe do vídeo.",
            'ru': "Подробно проанализируйте это видео и объясните, что вы наблюдаете. Тщательно изучите каждую сцену и деталь видео.",
            'ja': "このビデオを詳細に分析し、観察したことを説明してください。ビデオの各シーンと詳細を注意深く調べてください。",
            'ko': "이 비디오를 자세히 분석하고 관찰한 것을 설명하세요. 비디오의 모든 장면과 세부 사항을 주의 깊게 조사하세요.",
            'zh': "详细分析这段视频并解释你所观察到的内容。仔细检查视频的每个场景和细节。"
        },
        'default': {
            'tr': "Bu medyayı detaylı bir şekilde analiz et ve açıkla. Her detayı dikkatle incele.",
            'en': "Analyze this media in detail and explain what you see. Carefully examine every detail.",
            'es': "Analiza este medio en detalle y explica lo que ves. Examina cuidadosamente cada detalle.",
            'fr': "Analysez ce média en détail et expliquez ce que vous voyez. Examinez attentivement chaque détail.",
            'de': "Analysieren Sie dieses Medium detailliert und erklären Sie, was Sie sehen. Untersuchen Sie jeden Aspekt sorgfältig.",
            'it': "Analizza questo media in dettaglio e spiega cosa vedi. Esamina attentamente ogni dettaglio.",
            'pt': "Analise este meio em detalhes e explique o que vê. Examine cuidadosamente cada detalhe.",
            'ru': "Подробно проанализируйте этот носитель и объясните, что вы видите. Тщательно изучите каждый аспект.",
            'ja': "このメディアを詳細に分析し、見たものを説明してください。すべての詳細を注意深く調べてください。",
            'ko': "이 미디어를 자세히 분석하고 보이는 것을 설명하세요. 모든 세부 사항을 주의 깊게 조사하세요.",
            'zh': "详细分析这个媒体并解释你所看到的内容。仔细检查每个细节。"
        }
    }

    # If caption is provided, use it
    if caption and caption.strip():
        return caption

    # Select prompt based on media type and language
    if media_type in prompts:
        return prompts[media_type].get(lang, prompts[media_type]['en'])

    # Fallback to default prompt
    return prompts['default'].get(lang, prompts['default']['en'])

def main():
    # Initialize bot
    application = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()

    # Add command handler for /derinarama
    application.add_handler(CommandHandler("derinarama", handle_message)) # handle_message will now check for /derinarama

    # Add handlers (rest remain the same)
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)) # handle_message handles both regular text and /derinarama now

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    user_memory = UserMemory()
    main()