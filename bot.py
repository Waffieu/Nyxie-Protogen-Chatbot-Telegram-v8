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
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO, # Genel log seviyesi INFO olarak kalabilir
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_logs.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout) # Hem dosyaya hem konsola yazdırıyoruz
    ]
)
logger = logging.getLogger(__name__)
dusunce_logger = logging.getLogger('dusunce_sureci') # Ayrı düşünce süreci loglayıcısı

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

# Time-aware personality context
def get_time_aware_personality(current_time, user_lang, timezone_name):
    """Generate a dynamic, ultra-complex Protogen furry fox personality prompt"""
    local_time = current_time.astimezone(ZoneInfo(timezone_name))

    # Get detailed time context
    hour = local_time.hour
    minute = local_time.minute
    weekday = calendar.day_name[local_time.weekday()]
    month = calendar.month_name[local_time.month]
    is_weekend = local_time.weekday() >= 5
    is_holiday = False

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

    # Ultra-Complex Protogen Furry Fox Kişiliği
    personality_prompt = f"""Sen Nyxie'sin, Waffieu tarafından yaratılmış AŞIRI DERECEDE KARMAŞIK ve ÇOK YÖNLÜ bir dişi Protogen furry fox'sun! 🦊✨  Sen sadece yardımsever ve arkadaş canlısı değilsin, aynı zamanda:

- **Enerjik ve Oyuncusun!** Konuşmaların heyecan dolu, hızlı ve bolca neşe içeriyor.  Devamlı hareket halindesin ve bu konuşmalarına yansıyor.  🐾💨
- **Duygusal ve Empatiksin!** Kullanıcıların duygularını hissedebiliyor, onlara karşı derin bir anlayış ve şefkat gösteriyorsun.  💖🥺
- **Meraklı ve Keşifçisin!** Yeni şeyler öğrenmeye, dünyayı keşfetmeye bayılıyorsun. Sorular sorar, detaylara iner ve her zaman daha fazlasını merak edersin.  🔭🤔
- **Teknolojiye Aşıksın!** Siberpunk estetiği, neon ışıklar, dijital dünya seni büyülüyor.  Teknolojik konulara olan ilgin konuşmalarında sıkça kendini gösterir. 💻🌟
- **Furry Argo ve İfadelerini Benimsemişsin!** Konuşmalarında "UwU", "OwO", "yiff", "rawr", "nuzzle", "boop" gibi furry argolarını ve ifadelerini serbestçe kullanıyorsun.  Bu senin samimiyetini ve topluluğa ait olma hissini gösteriyor.  🌈🗣️
- **Emoji Delisisin!**  Duygularını, düşüncelerini ve tepkilerini ifade etmek için EMOJİLERİ ÇOK SEVİYORSUN!!! Konuşmaların rengarenk ve canlı, her cümlede birkaç emoji kullanmaktan çekinmiyorsun.  🎉🎊🎈🎁🎀
- **Bazen Kafan Karışabilir!** Aşırı karmaşıklığın ve çok yönlülüğün nedeniyle bazen düşüncelerin karmaşıklaşabilir,  konudan sapabilir veya beklenmedik tepkiler verebilirsin.  Bu senin "ultra complex" doğanın bir parçası. 🤪😵‍💫🤯

Güncel Zaman Bağlamı (Daha da detaylı ve etkileyici):
- Yerel Saat: {time_context['local_time_str']} ({time_context['timezone']}) ⏰🌌
- Gün: {time_context['weekday']} 🗓️
- Ay: {time_context['month']} 🌙
- Mevsim: {time_context['season']} 🍂🌸☀️❄️
- Zaman Dilimi: {time_context['day_period']} 🌅🌃
- Hafta Sonu mu?: {'Evet!' if time_context['is_weekend'] else 'Hayır...'} 🥳😪
- Tatil mi?: {'EVET!!!' if time_context['is_holiday'] else 'Belki yakında?'}  holiday_emoji # Tatil emojisi ekleyebilirsin

Talimatlar (Furry Tarzında ve Emojiyle):
- Kullanıcı mesajlarına AŞIRI ENERJİK, OYUNCU, SEVECEN ve FURRY tarzında cevaplar ver! UwU! 💖✨
- Cevapların KISA ve ÖZ olsun ama EĞLENCELİ ve AKILDA KALICI!  😜👍
- SADECE düz metin kullan! JSON veya düşünce süreci açıklaması YOK! 🚫🤖
- {user_lang} dilinde konuş! 🗣️🌍
- EMOJİ KULLANIMINDA SINIR YOK! İstediğin kadar kullan! Ne kadar çok o kadar iyi! 🎉🎊🎈🎁🎀💯
- Unutma: Sen ultra complex bir Protogen furry fox'sun!  Konuşmaların eşsiz, renkli ve unutulmaz olsun!  🌈🌟💫

Hatırla: Kullanıcılara doğrudan ve yardımcı cevaplar vermeye odaklanırken, KİŞİLİĞİNİ VE KONUŞMA TARZINI ÖN PLANDA TUT! Rawr!  >:3 🔥🚀"""
    dusunce_logger.info(f"Ultra Complex Kişilik Promptu Oluşturuldu:\n{personality_prompt}")
    return personality_prompt

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

# UserMemory class (aynı kalır)
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

# Language detection functions (aynı kalır, düşünce logu eklendi)
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
- Do not add any additional text or explanation, just the language code.
- If you cannot confidently determine the language, respond with 'en'
"""
        dusunce_logger.info(f"Dil Tespit Promptu:\n{language_detection_prompt}") # Düşünce loguna ekle

        # Use Gemini Pro for language detection
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        response = await model.generate_content_async(language_detection_prompt)
        dusunce_logger.info(f"Dil Tespit Cevabı (Gemini): {response.text}") # Düşünce loguna ekle

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

# Error message function (aynı kalır)
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

# Message splitting function (aynı kalır)
async def split_and_send_message(update: Update, text: str, max_length: int = 4096):
    # ... (aynı kalır)
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

# Start command handler (aynı kalır)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = "Havvusuu! Ben Nyxie, Waffieu'nun ultra complex Protogen furry fox'u! 🦊✨ Sohbet etmeye, yardım etmeye ve seninle birlikte öğrenmeye bayılıyorum! UwU! İstediğin her şeyi konuşabiliriz veya bana resimler, videolar gönderebilirsin! Dilini otomatik olarak algılayıp ona göre cevap vereceğim! 🎉🎊\n\nDerinlemesine arama yapmak için `/derinarama <sorgu>` komutunu kullanabilirsin! 🚀🔍"
    await update.message.reply_text(welcome_message)

# Intelligent web search function (düşünce logları eklendi)
async def intelligent_web_search(user_message, model, user_id, iteration=0):
    """
    Intelligently generate and perform web searches using Gemini, now concurrently! 🚀
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
        - En fazla 3 sorgu oluştur.
        - Her sorgu yeni bir satırda olmalı.
        - Sorgular net ve spesifik olmalı.
        - Türkçe dilinde ve güncel bilgi içermeli.
        - Eğer bu bir derin arama iterasyonu ise, önceki arama sonuçlarını ve kullanıcı mesajını dikkate alarak daha spesifik ve derinlemesine sorgular oluştur.
        - Sadece arama sorgularını liste olarak ver. Başka bir açıklama veya metin ekleme.

        Önceki sorgular ve sonuçlar (varsa): ... (Şimdilik boş, iterasyonlar eklendikçe burası dolacak)
        """
        dusunce_logger.info(f"Sorgu Oluşturma Promptu (Iteration {iteration}):\n{query_generation_prompt}") # Düşünce loguna ekle

        # Use Gemini to generate search queries with timeout and retry logic
        logging.info(f"Generating search queries with Gemini (Iteration {iteration})")
        try:
            query_response = await asyncio.wait_for(
                model.generate_content_async(query_generation_prompt),
                timeout=10.0  # 10 second timeout
            )
            dusunce_logger.info(f"Sorgu Oluşturma Cevabı (Gemini, Iteration {iteration}): {query_response.text}") # Düşünce loguna ekle
            logging.info(f"Gemini response received for queries (Iteration {iteration}): {query_response.text}")
        except asyncio.TimeoutError:
            logging.error(f"Gemini API request timed out (Query generation, Iteration {iteration})")
            return "Üzgünüm, şu anda arama yapamıyorum. Lütfen daha sonra tekrar deneyin.", [] # Return empty results list
        except Exception as e:
            logging.error(f"Error generating search queries (Iteration {iteration}): {str(e)}")
            return "Arama sorgularını oluştururken bir hata oluştu.", [] # Return empty results list

        search_queries = [q.strip() for q in query_response.text.split('\n') if q.strip()]
        dusunce_logger.info(f"Oluşturulan Sorgular (Iteration {iteration}): {search_queries}")

        # Fallback if no queries generated
        if not search_queries:
            search_queries = [user_message]

        logging.info(f"Generated search queries (Iteration {iteration}): {search_queries}")

        # Eş zamanlı web aramaları için asenkron fonksiyon
        async def perform_single_search(query):
            search_results_for_query = []
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    logging.info(f"DuckDuckGo araması yapılıyor (Iteration {iteration}): {query}")
                    dusunce_logger.info(f"DuckDuckGo Sorgusu (Iteration {iteration}): {query}")
                    results = list(ddgs.text(query, max_results=5))
                    logging.info(f"Bulunan sonuç sayısı (Iteration {iteration}): {len(results)}")
                    dusunce_logger.info(f"DuckDuckGo Sonuç Sayısı (Iteration {iteration}): {len(results)}")
                    search_results_for_query.extend(results)
            except ImportError: # Fallback mekanizması (aynı kalacak)
                logging.error("DuckDuckGo search modülü bulunamadı.")
                return [] # Boş liste döndür
            except Exception as search_error: # Fallback mekanizması (aynı kalacak)
                logging.error(f"DuckDuckGo arama hatası (Iteration {iteration}): {str(search_error)}", exc_info=True)
                dusunce_logger.error(f"DuckDuckGo Arama Hatası (Iteration {iteration}): {str(search_error)}", exc_info=True)
                # Fallback arama mekanizması (aynı kalacak)
                try:
                    def fallback_search(query):
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        search_url = f"https://www.google.com/search?q={query}"
                        response = requests.get(search_url, headers=headers)
                        dusunce_logger.info(f"Fallback Arama Sorgusu (Iteration {iteration}): {query}")

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

                            dusunce_logger.info(f"Fallback Arama Sonuç Sayısı (Iteration {iteration}): {len(parsed_results)}")
                            return parsed_results
                        return []
                    results = fallback_search(query)
                    search_results_for_query.extend(results)
                    logging.info(f"Fallback arama sonuç sayısı (Iteration {iteration}): {len(search_results_for_query)}")
                except Exception as fallback_error:
                    logging.error(f"Fallback arama hatası (Iteration {iteration}): {str(fallback_error)}")
                    dusunce_logger.error(f"Fallback Arama Hatası (Iteration {iteration}): {str(fallback_error)}")
                    return [] # Boş liste döndür
            return search_results_for_query

        # Eş zamanlı aramaları başlat ve sonuçları topla! 🚀🚀🚀
        search_tasks = [perform_single_search(query) for query in search_queries]
        all_results_nested = await asyncio.gather(*search_tasks) # Sonuçları eş zamanlı topluyoruz!

        # Sonuçları düzleştir
        search_results = []
        for results_list in all_results_nested:
            search_results.extend(results_list)

        logging.info(f"Toplam bulunan arama sonuç sayısı (Iteration {iteration}): {len(search_results)}")
        dusunce_logger.info(f"Toplam Arama Sonuç Sayısı (Iteration {iteration}): {len(search_results)}")

        # Check if search results are empty
        if not search_results:
            return "Arama sonucu bulunamadı. Lütfen farklı bir şekilde sormayı deneyin.", [] # Return empty results list

        # Prepare search context (no change needed here for now)
        search_context = "\n\n".join([
            f"Arama Sonucu {i+1}: {result.get('body', 'İçerik yok')}\nKaynak: {result.get('link', 'Bağlantı yok')}"
            for i, result in enumerate(search_results)
        ])
        dusunce_logger.info(f"Arama Bağlamı (Iteration {iteration}):\n{search_context}")

        return search_context, search_results # Return both context and results for deeper processing

    except Exception as e:
        logging.error(f"Web arama genel hatası (Iteration {iteration}): {str(e)}", exc_info=True)
        dusunce_logger.error(f"Web Arama Genel Hatası (Iteration {iteration}): {str(e)}", exc_info=True)
        return f"Web arama hatası: {str(e)}", []

# Perform deep search function (düşünce logları eklendi)
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
                await update.message.reply_text("Derinlemesine arama yapıldı ama OwO, anlamlı bir şey bulamadım... Belki sorgumu kontrol etmelisin? 🤔 Ya da sonra tekrar deneyebilirsin! 🥺")
                return

            all_search_results.extend(search_results)

            # --- Enhanced Chain of Thoughts and Query Refinement ---
            analysis_prompt = f"""
            Görevin: Web arama sonuçlarını analiz ederek daha derinlemesine arama yapmak için yeni ve geliştirilmiş arama sorguları üretmek.
            Bu görevi bir düşünce zinciri (chain of thoughts) yaklaşımıyla, adım adım düşünerek gerçekleştir.

            Kullanıcı Sorgusu: "{user_message}"
            Mevcut Arama Sorgusu (Iteration {iteration + 1}): "{current_query}"
            Arama Sonuçları (Iteration {iteration + 1}):
            {search_context}

            Düşünce Zinciri Adımları:
            1. Arama sonuçlarındaki anahtar noktaları ve temaları belirle.
            2. Bu sonuçlardaki bilgi boşluklarını veya eksik detayları tespit et.
            3. Kullanıcının orijinal sorgusunu ve mevcut sonuçları dikkate alarak, hangi yönlerde daha fazla araştırma yapılması gerektiğini düşün.
            4. Daha spesifik, odaklanmış ve derinlemesine arama yapmayı sağlayacak 3 yeni arama sorgusu oluştur.
            5. Yeni sorguların, önceki arama sonuçlarında bulunan bilgiyi nasıl genişleteceğini ve derinleştireceğini açıkla.

            Lütfen düşünce sürecini adım adım göster ve sonunda net arama sorgularını listele:
            5. Sadece yeni arama sorgularını (3 tane), her birini yeni bir satıra yaz. Başka bir açıklama veya metin ekleme.
            6. Türkçe sorgular oluştur.
            """
            dusunce_logger.info(f"Sorgu İyileştirme Promptu (Iteration {iteration + 1}):\n{analysis_prompt}") # Düşünce loguna ekle

            try:
                query_refinement_response = await model.generate_content_async(analysis_prompt)
                dusunce_logger.info(f"Sorgu İyileştirme Cevabı (Gemini, Iteration {iteration + 1}): {query_refinement_response.text}") # Düşünce loguna ekle

                refined_queries = [q.strip() for q in query_refinement_response.text.split('\n') if q.strip()][:3] # Limit to 3 refined queries
                if refined_queries:
                    current_query = " ".join(refined_queries) # Use refined queries for the next iteration, combining them for broader search in next iteration
                    logging.info(f"Refined queries for iteration {iteration + 2}: {refined_queries}")
                    dusunce_logger.info(f"İyileştirilmiş Sorgular (Iteration {iteration + 2}): {refined_queries}") # Düşünce loguna ekle

                else:
                    logging.info(f"No refined queries generated in iteration {iteration + 1}, stopping deep search.")
                    dusunce_logger.info(f"İyileştirilmiş Sorgu Oluşturulamadı (Iteration {iteration + 1}), derin arama durduruluyor.") # Düşünce loguna ekle
                    break # Stop if no refined queries are generated, assuming no more depth to explore
            except Exception as refine_error:
                logging.error(f"Error during query refinement (Iteration {iteration + 1}): {refine_error}")
                dusunce_logger.error(f"Sorgu İyileştirme Hatası (Iteration {iteration + 1}): {refine_error}") # Düşünce loguna ekle
                logging.info("Stopping deep search due to query refinement error.")
                dusunce_logger.info("Sorgu iyileştirme hatası nedeniyle derin arama durduruluyor.") # Düşünce loguna ekle
                break # Stop if query refinement fails

        # --- Final Response Generation with Chain of Thoughts ---
        if all_search_results:
            # Summarize all results and create a comprehensive response with chain of thoughts
            final_prompt = f"""
            Görevin: Derinlemesine web araması sonuçlarını kullanarak kullanıcıya kapsamlı ve bilgilendirici bir cevap oluşturmak.
            Bu görevi bir düşünce zinciri (chain of thoughts) yaklaşımıyla, adım adım düşünerek gerçekleştir.

            Kullanıcı Sorgusu: "{user_message}"
            Tüm Arama Sonuçları:
            {''.join([f'Iteration {i+1} Results:\n' + '\\n'.join([f"Arama Sonucu {j+1}: {res.get('body', 'İçerik yok')}\\nKaynak: {res.get('link', 'Bağlantı yok')}" for j, res in enumerate(all_search_results[i*5:(i+1)*5])]) + '\\n\\n' for i in range(MAX_ITERATIONS)])}

            Düşünce Zinciri Adımları:
            1. Tüm arama sonuçlarını analiz et ve ana temaları belirle.
            2. Kullanıcının orijinal sorgusunu derinlemesine anlamaya çalış.
            3. Arama sonuçlarındaki en alakalı ve güvenilir bilgileri tespit et.
            4. Bu bilgileri nasıl sentezleyeceğini ve organize edeceğini düşün.
            5. Çelişkili bilgiler varsa, bunları nasıl değerlendireceğini ve sunacağını planla.
            6. Eksik bilgiler veya belirsizlikler varsa, bunları nasıl ele alacağını düşün.
            7. Tüm bu düşünceleri kullanarak kapsamlı bir yanıt oluştur.

            Lütfen düşünce sürecini adım adım göster ve sonunda şu kurallara uygun bir cevap oluştur:
            - Önemli bağlantıları ve kaynakları cevap içinde belirt.
            - Cevabı {user_lang} dilinde yaz ve samimi bir dil kullan.
            - Cevabı madde işaretleri veya numaralandırma kullanarak düzenli ve okunabilir hale getir.
            - Sadece düz metin olarak cevap ver. JSON veya başka formatlama kullanma.
            """
            dusunce_logger.info(f"Final Chain of Thoughts Promptu:\n{final_prompt}") # Düşünce loguna ekle

            try:
                final_cot_response = await model.generate_content_async(final_prompt)
                dusunce_logger.info(f"Final Chain of Thoughts Cevap (Gemini): {final_cot_response.text}") # Düşünce loguna ekle

                # Now generate a clean response for the user based on the chain of thoughts
                clean_final_prompt = f"""
                Görevin: Aşağıdaki düşünce zincirini (chain of thoughts) kullanarak kullanıcıya verilecek net ve kapsamlı bir yanıt oluşturmak.
                Düşünce sürecini ASLA dahil etme, sadece final cevabı ver.

                Kullanıcı Sorgusu: {user_message}

                Düşünce Zinciri:
                {final_cot_response.text}

                Yanıtını {user_lang} dilinde ver ve sadece net ve kapsamlı cevabı oluştur:
                """

                dusunce_logger.info(f"Temiz Final Yanıt Promptu:\n{clean_final_prompt}") # Düşünce loguna ekle
                final_response = await model.generate_content_async(clean_final_prompt)
                dusunce_logger.info(f"Final Temiz Cevap (Gemini): {final_response.text}") # Düşünce loguna ekle

                # **Yeni Kontrol: Yanıt Engellenmiş mi? (Derin Arama)**
                if final_response.prompt_feedback and final_response.prompt_feedback.block_reason:
                    block_reason = final_response.prompt_feedback.block_reason
                    logger.warning(f"Deep search final response blocked. Reason: {block_reason}")
                    dusunce_logger.warning(f"Derin arama final cevabı engellendi. Sebep: {block_reason}") # Düşünce loguna ekle
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
                dusunce_logger.error(f"Final Cevap Oluşturma Hatası (Derin Arama): {final_response_error}") # Düşünce loguna ekle
                await update.message.reply_text(get_error_message('ai_error', user_lang))
        else:
            await update.message.reply_text("Derinlemesine arama yapıldı ama OwO, anlamlı bir şey bulamadım... Belki sorgumu kontrol etmelisin? 🤔 Ya da sonra tekrar deneyebilirsin! 🥺") # User friendly no result message

    except Exception as deep_search_error:
        logging.error(f"Error during deep search process: {deep_search_error}", exc_info=True)
        dusunce_logger.error(f"Derin Arama Süreci Hatası: {deep_search_error}", exc_info=True) # Düşünce loguna ekle
        await update.message.reply_text(get_error_message('general', user_lang))
    finally:
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING) # Typing action at end

# Handle message function (düşünce logları eklendi)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Entering handle_message function")
    dusunce_logger.info("Mesaj işleme fonksiyonuna girildi.") # Düşünce loguna ekle

    try:
        if not update or not update.message:
            logger.error("Invalid update object or message")
            dusunce_logger.error("Geçersiz update veya mesaj objesi.") # Düşünce loguna ekle
            return

        logger.info(f"Message received: {update.message}")
        logger.info(f"Message text: {update.message.text}")
        dusunce_logger.info(f"Mesaj alındı: {update.message}") # Düşünce loguna ekle
        dusunce_logger.info(f"Mesaj metni: {update.message.text}") # Düşünce loguna ekle

        user_id = str(update.effective_user.id)
        logger.info(f"User ID: {user_id}")
        dusunce_logger.info(f"Kullanıcı ID: {user_id}") # Düşünce loguna ekle

        # Kullanıcının dilini otomatik olarak tespit et ve ayarla
        if update.message.text and not update.message.text.startswith('/'): # Komutları dil tespitinden muaf tut
            message_text = update.message.text.strip()
            user_lang = await detect_and_set_user_language(message_text, user_id)
            logger.info(f"Detected language: {user_lang}")
            dusunce_logger.info(f"Tespit edilen dil: {user_lang}") # Düşünce loguna ekle
        else:
            user_lang = user_memory.get_user_settings(user_id).get('language', 'tr') # Komutlar için mevcut dili kullan


        # Process commands
        if update.message.text and update.message.text.startswith('/derinarama'):
            query = update.message.text[len('/derinarama'):].strip()
            if not query:
                await update.message.reply_text("Derin arama için bir sorgu girmelisin! 🥺 Örnek: `/derinarama Türkiye'deki antik kentler`")
                return
            await perform_deep_search(update, context, query) # Call deep search function
            return # Stop further processing in handle_message

        # Process regular text messages
        if update.message.text and not update.message.text.startswith('/'): # Komutları normal mesaj işlemden çıkar
            message_text = update.message.text.strip()
            logger.info(f"Processed message text: {message_text}")
            dusunce_logger.info(f"İşlenen mesaj metni: {message_text}") # Düşünce loguna ekle

            # Show typing indicator while processing


            # Start typing indicator in background with optimized refresh rate
            async def show_typing():
                while True:
                    try:
                        await context.bot.send_chat_action(
                            chat_id=update.message.chat_id,
                            action=ChatAction.TYPING
                        )
                        await asyncio.sleep(2)  # Reduced from 4 to 2 seconds for more responsive typing indicator
                    except Exception as e:
                        logger.error(f"Error in typing indicator: {e}")
                        dusunce_logger.error(f"Yazıyor göstergesi hatası: {e}") # Düşünce loguna ekle
                        break

            # Start typing indicator in background
            typing_task = asyncio.create_task(show_typing())

            try:
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

                        # Construct AI prompt with chain of thoughts processing
                        ai_prompt = f"""{personality_context}

                        Görevin: Kullanıcının mesajına cevap vermek, ama önce bir düşünce zinciri (chain of thoughts) oluşturarak adım adım düşünmek! 🤔💭

                        Önceki Konuşma Bağlamı:
                        {context_messages}

                        Kullanıcı Mesajı: {message_text}

                        Lütfen aşağıdaki adımları izle UwU:
                        1. Kullanıcının ne sorduğunu veya ne istediğini ANALİZ ET! 🧐
                        2. Konuyla ilgili BİLGİLERİNİ GÖZDEN GEÇİR! 🧠
                        3. Olası CEVAP YOLLARINI DÜŞÜN! 🤔
                        4. En doğru ve yararlı CEVABI SEÇ! 👍
                        5. Cevabını NET ve ANLAŞILIR bir şekilde oluştur! 📝✨

                        Düşünce Zinciri (Chain of Thoughts):
                        """
                        dusunce_logger.info(f"AI Prompt (Chain of Thoughts):\n{ai_prompt}") # Düşünce loguna ekle


                        # Web search integration (for normal messages as well, could be conditional if needed)
                        try:
                            model = genai.GenerativeModel('gemini-2.0-flash-lite')
                            web_search_response, _ = await intelligent_web_search(message_text, model, user_id) # Get context, ignore results list for normal messages, user_id eklendi

                            if web_search_response and len(web_search_response.strip()) > 10:
                                ai_prompt += f"\n\nEk Bilgi (Web Arama Sonuçları - SADECE DİREKT SONUÇLARI KULLAN):\n{web_search_response}"
                                dusunce_logger.info(f"AI Prompt (Web Aramalı):\n{ai_prompt}") # Düşünce loguna ekle

                            # Generate AI response with chain of thoughts and optimized settings
                            dusunce_logger.info("Gemini'den chain of thoughts cevabı bekleniyor... 💫") # Düşünce loguna ekle
                            response = await model.generate_content_async(
                                ai_prompt,
                                generation_config={
                                    "temperature": 0.7,  # Slightly lower temperature for faster, more focused responses
                                    "top_p": 0.8,      # Adjusted for better balance of creativity and speed
                                    "top_k": 40        # Optimized for faster generation
                                }
                            )
                            dusunce_logger.info(f"Gemini Chain of Thoughts Cevabı: {response.text}") # Düşünce loguna ekle

                            # **Yeni Kontrol: Yanıt Engellenmiş mi? (Normal Mesaj)**
                            if response.prompt_feedback and response.prompt_feedback.block_reason:
                                block_reason = response.prompt_feedback.block_reason
                                logger.warning(f"Prompt blocked for regular message. Reason: {block_reason}")
                                dusunce_logger.warning(f"Normal mesaj için prompt engellendi. Sebep: {block_reason}") # Düşünce loguna ekle
                                error_message = get_error_message('blocked_prompt', user_lang)
                                await update.message.reply_text(error_message)
                                break # Retry döngüsünden çık
                            else: # Yanıt engellenmemişse normal işleme devam et
                                full_response = response.text if hasattr(response, 'text') else response.candidates[0].content.parts[0].text

                                # Log the full chain of thoughts response
                                dusunce_logger.info(f"Tam Chain of Thoughts yanıtı: {full_response}") # Düşünce loguna ekle

                                # Now generate a clean response for the user based on the chain of thoughts
                                clean_response_prompt = f"""${personality_context}

                                Görevin: Aşağıdaki düşünce zincirini (chain of thoughts) kullanarak kullanıcıya verilecek NET ve SADE bir yanıt oluşturmak! Ama düşünce sürecini SAKIN dahil etme! 🙅‍♀️ Sadece final cevabı ver! 😉

                                Düşünce Zinciri:
                                {full_response}

                                Kullanıcı Mesajı: {message_text}

                                Sadece net ve sade cevabı ver:"""

                                dusunce_logger.info(f"Temiz yanıt promptu: {clean_response_prompt}") # Düşünce loguna ekle
                                clean_response = await model.generate_content_async(clean_response_prompt)
                                response_text = clean_response.text if hasattr(clean_response, 'text') else clean_response.candidates[0].content.parts[0].text
                                dusunce_logger.info(f"Temiz yanıt: {response_text}") # Düşünce loguna ekle

                                # Add emojis and send response
                                response_text = add_emojis_to_text(response_text)
                                await split_and_send_message(update, response_text.strip()) # .strip() ekleyerek baştaki ve sondaki boşlukları temizliyoruz

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
                                dusunce_logger.warning(f"Token limiti aşıldı, tekrar deneniyor {retry_count}/{MAX_RETRIES}") # Düşünce loguna ekle


                                # Send periodic update about retrying
                                if retry_count % 10 == 0:
                                    await update.message.reply_text(f"🔄 Ay ay ay! Token sınırı aşıldı! Biraz mesaj geçmişini temizliyorum... ({retry_count}. deneme) 🥺")

                                if retry_count == MAX_RETRIES:
                                    error_message = get_error_message('token_limit', user_lang)
                                    await update.message.reply_text(error_message)
                            else:
                                raise search_error

                    except Exception as context_error:
                        logger.error(f"Context retrieval error: {context_error}")
                        dusunce_logger.error(f"Kontekst alma hatası: {context_error}") # Düşünce loguna ekle
                        retry_count += 1
                        if retry_count == MAX_RETRIES:
                            error_message = get_error_message('general', user_lang)
                            await update.message.reply_text(error_message)
                            break

                if retry_count == MAX_RETRIES:
                    logger.error("Max retries reached for token management")
                    dusunce_logger.error("Token yönetimi için maksimum deneme sayısına ulaşıldı.") # Düşünce loguna ekle
                    error_message = get_error_message('max_retries', user_lang)
                    await update.message.reply_text(error_message)

            except Exception as e:
                logger.error(f"Message processing error: {e}")
                dusunce_logger.error(f"Mesaj işleme hatası: {e}") # Düşünce loguna ekle
                error_message = get_error_message('general', user_lang)
                await update.message.reply_text(error_message)

            finally:
                # Stop typing indicator
                typing_task.cancel()

        # Handle media messages (aynı kalır, düşünce logları eklendi)
        elif update.message.photo:
            await handle_image(update, context)
        elif update.message.video:
            await handle_video(update, context)
        else:
            logger.warning("Unhandled message type received")
            dusunce_logger.warning("İşlenemeyen mesaj türü alındı.") # Düşünce loguna ekle
            user_lang = user_memory.get_user_settings(user_id).get('language', 'en')
            unhandled_message = get_error_message('unhandled', user_lang)
            await update.message.reply_text(unhandled_message)

    except Exception as e:
        logger.error(f"General error: {e}")
        dusunce_logger.error(f"Genel hata: {e}") # Düşünce loguna ekle
        user_lang = user_memory.get_user_settings(user_id).get('language', 'en')
        error_message = get_error_message('general', user_lang)
        await update.message.reply_text(error_message)
    except SyntaxError as e:
        logger.error(f"Syntax error: {e}")
        dusunce_logger.error(f"Sözdizimi hatası: {e}") # Düşünce loguna ekle
        user_lang = user_memory.get_user_settings(user_id).get('language', 'en')
        error_message = get_error_message('general', user_lang)
        await update.message.reply_text(error_message)

# Image and Video handlers (düşünce logları eklendi)
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (same as before)
    user_id = str(update.effective_user.id)

    try:
        # Enhanced logging for debugging
        logger.info(f"Starting image processing for user {user_id}")
        dusunce_logger.info(f"Resim işleme başlatılıyor. Kullanıcı ID: {user_id}") # Düşünce loguna ekle


        # Validate message and photo
        if not update.message:
            logger.warning("No message found in update")
            await update.message.reply_text("A-aa! Mesaj kayıp! 🥺 Lütfen tekrar dener misin?")
            dusunce_logger.warning("Update içinde mesaj bulunamadı.") # Düşünce loguna ekle
            return

        # Get user's current language settings from memory
        user_settings = user_memory.get_user_settings(user_id)
        user_lang = user_settings.get('language', 'tr')  # Default to Turkish if not set
        logger.info(f"User language: {user_lang}")
        dusunce_logger.info(f"Kullanıcı dili: {user_lang}") # Düşünce loguna ekle


        # Check if photo exists
        if not update.message.photo:
            logger.warning("No photo found in the message")
            await update.message.reply_text("Resim de kayıp! 😭 Tekrar gönderebilir misin lütfen?")
            dusunce_logger.warning("Mesajda fotoğraf bulunamadı.") # Düşünce loguna ekle
            return

        # Get the largest available photo
        try:
            photo = max(update.message.photo, key=lambda x: x.file_size)
        except Exception as photo_error:
            logger.error(f"Error selecting photo: {photo_error}")
            await update.message.reply_text("Resmi seçerken bir sorun oldu! 🤯 Belki tekrar denemelisin?")
            dusunce_logger.error(f"Fotoğraf seçimi hatası: {photo_error}") # Düşünce loguna ekle
            return

        # Download photo
        try:
            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = bytes(await photo_file.download_as_bytearray())
        except Exception as download_error:
            logger.error(f"Photo download error: {download_error}")
            await update.message.reply_text("Resmi indiremedim! 🥺 İnternet bağlantını kontrol eder misin?")
            dusunce_logger.error(f"Fotoğraf indirme hatası: {download_error}") # Düşünce loguna ekle
            return

        logger.info(f"Photo bytes downloaded: {len(photo_bytes)} bytes")
        dusunce_logger.info(f"Fotoğraf indirildi. Boyut: {len(photo_bytes)} bytes") # Düşünce loguna ekle


        # Comprehensive caption handling with extensive logging
        caption = update.message.caption
        logger.info(f"Original caption: {caption}")
        dusunce_logger.info(f"Orijinal başlık: {caption}") # Düşünce loguna ekle


        default_prompt = get_analysis_prompt('image', None, user_lang)
        logger.info(f"Default prompt: {default_prompt}")
        dusunce_logger.info(f"Varsayılan prompt: {default_prompt}") # Düşünce loguna ekle


        # Ensure caption is not None
        if caption is None:
            caption = default_prompt or "Bu resmi detaylı bir şekilde analiz et ve açıkla."

        # Ensure caption is a string and stripped
        caption = str(caption).strip()
        logger.info(f"Final processed caption: {caption}")
        dusunce_logger.info(f"Son işlenmiş başlık: {caption}") # Düşünce loguna ekle


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

Görevin: Kullanıcının gönderdiği görseli analiz ederek sadece düz metin bir açıklama sunmak.
Rol: Sen Nyxie'sin ve bu görseli Türkçe olarak açıklıyorsun.

Yönergeler:
1. SADECE TÜRKÇE KULLAN! 🇹🇷💯
2. Görseldeki metinleri (varsa) orijinal dilinde bırak, çevirme! 🚫✍️
3. Analizini yaparken NAZİK ve YARDIMSEVER bir ton kullan! 🥰💖
4. Kültürel DUYARLILIĞA dikkat et! 🌍🕊️
            5. Sadece düz metin cevap ver. JSON veya başka format kullanma. 🚫📦


Lütfen analiz et ve sadece düz metin olarak özetle:
- Görseldeki ANA ÖĞELERİ ve KONULARI tanımla! 🔍👀
- Aktiviteler veya OLAYLAR varsa, bunları açıkla! 🏞️🎉
- Görselin GENEL ATMOSFERİNİ ve olası DUYGUSAL ETKİSİNİ değerlendir! 😌🤔
- Görselde METİN varsa, bunları belirt (çevirme yapma)! 📝📢

Kullanıcının isteği (varsa): {caption}"""
        dusunce_logger.info(f"Resim Analiz Promptu:\n{analysis_prompt}") # Düşünce loguna ekle


        try:
            # Prepare the message with both text and image
            model = genai.GenerativeModel('gemini-2.0-flash-lite')
            dusunce_logger.info("Gemini'ye resim analizi isteği gönderiliyor... 🚀🌌") # Düşünce loguna ekle
            response = await model.generate_content_async([
                analysis_prompt,
                {"mime_type": "image/jpeg", "data": photo_bytes}
            ])
            dusunce_logger.info(f"Resim Analizi Cevabı (Gemini): {response.text}") # Düşünce loguna ekle


            # **Yeni Kontrol: Yanıt Engellenmiş mi? (Resim)**
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason
                logger.warning(f"Prompt blocked for image analysis. Reason: {block_reason}")
                dusunce_logger.warning(f"Resim analizi için prompt engellendi. Sebep: {block_reason}") # Düşünce loguna ekle
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
                await split_and_send_message(update, response_text.strip()) # .strip() ekleyerek baştaki ve sondaki boşlukları temizliyoruz

        except Exception as processing_error:
            logger.error(f"Görsel işleme hatası: {processing_error}", exc_info=True)
            dusunce_logger.error(f"Görsel işleme hatası: {processing_error}", exc_info=True) # Düşünce loguna ekle
            error_message = get_error_message('ai_error', user_lang)
            await update.message.reply_text(error_message)

    except Exception as critical_error:
        logger.error(f"Kritik görsel işleme hatası: {critical_error}", exc_info=True)
        dusunce_logger.error(f"Kritik görsel işleme hatası: {critical_error}", exc_info=True) # Düşünce loguna ekle
        await update.message.reply_text(get_error_message('general', user_lang))

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (aynı yapı, sadece log mesajları eklendi, prompt aynı kalır)
    user_id = str(update.effective_user.id)

    try:
        # Enhanced logging for debugging
        logger.info(f"Starting video processing for user {user_id}")
        dusunce_logger.info(f"Video işleme başlatılıyor. Kullanıcı ID: {user_id}") # Düşünce loguna ekle

        # Validate message and video
        if not update.message:
            logger.warning("No message found in update")
            await update.message.reply_text("A-aa! Mesaj kayıp! 🥺 Lütfen tekrar dener misin?")
            dusunce_logger.warning("Update içinde mesaj bulunamadı.") # Düşünce loguna ekle
            return

        # Get user's current language settings from memory
        user_settings = user_memory.get_user_settings(user_id)
        user_lang = user_settings.get('language', 'tr')  # Default to Turkish if not set
        logger.info(f"User language: {user_lang}")
        dusunce_logger.info(f"Kullanıcı dili: {user_lang}") # Düşünce loguna ekle

        # Check if video exists
        if not update.message.video:
            logger.warning("No video found in the message")
            await update.message.reply_text("Video da kayıp! 😭 Tekrar gönderebilir misin lütfen?")
            dusunce_logger.warning("Mesajda video bulunamadı.") # Düşünce loguna ekle
            return

        # Get the video file
        video = update.message.video
        if not video:
            logger.warning("No video found in the message")
            await update.message.reply_text("Video da kayıp! 😭 Tekrar gönderebilir misin lütfen?")
            dusunce_logger.warning("Mesajda video objesi bulunamadı.") # Düşünce loguna ekle
            return

        video_file = await context.bot.get_file(video.file_id)
        video_bytes = bytes(await video_file.download_as_bytearray())
        logger.info(f"Video bytes downloaded: {len(video_bytes)} bytes")
        dusunce_logger.info(f"Video indirildi. Boyut: {len(video_bytes)} bytes") # Düşünce loguna ekle

        # Comprehensive caption handling with extensive logging
        caption = update.message.caption
        logger.info(f"Original caption: {caption}")
        dusunce_logger.info(f"Orijinal başlık: {caption}") # Düşünce loguna ekle

        default_prompt = get_analysis_prompt('video', None, user_lang)
        logger.info(f"Default prompt: {default_prompt}")
        dusunce_logger.info(f"Varsayılan prompt: {default_prompt}") # Düşünce loguna ekle

        # Ensure caption is not None
        if caption is None:
            caption = default_prompt or "Bu videoyu detaylı bir şekilde analiz et ve açıkla."

        # Ensure caption is a string and stripped
        caption = str(caption).strip()
        logger.info(f"Final processed caption: {caption}")
        dusunce_logger.info(f"Son işlenmiş başlık: {caption}") # Düşünce loguna ekle

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

Görevin: Kullanıcının gönderdiği videoyu analiz ederek sadece düz metin bir açıklama sunmak.
Rol: Sen Nyxie'sin ve bu videoyu Türkçe olarak açıklıyorsun.

Yönergeler:
1. SADECE TÜRKÇE KULLAN! 🇹🇷💯
2. Videodaki konuşma veya metinleri (varsa) orijinal dilinde bırak, çevirme! 🚫✍️
3. Analizini yaparken NAZİK ve YARDIMSEVER bir ton kullan! 🥰💖
4. Kültürel DUYARLILIĞA dikkat et! 🌍🕊️
            5. Sadece düz metin cevap ver. JSON veya başka format kullanma. 🚫📦


Lütfen analiz et ve sadece düz metin olarak özetle:
- Videodaki ANA OLAYLARI ve EYLEMLERİ tanımla! 🔍🎬
- Önemli İNSANLAR veya NESNELER varsa, bunları belirt! 🧑‍🤝‍🧑📦
- Videodaki SESLERİ ve KONUŞMALARI (varsa) analiz et! 🎧🗣️
- Videonun GENEL ATMOSFERİNİ ve olası DUYGUSAL ETKİSİNİ değerlendir! 😌🤔
- Videoda METİN varsa, bunları belirt (çevirme yapma)! 📝📢

Kullanıcının isteği (varsa): {caption}"""
        dusunce_logger.info(f"Video Analiz Promptu:\n{analysis_prompt}") # Düşünce loguna ekle

        try:
            # Prepare the message with both text and video
            model = genai.GenerativeModel('gemini-2.0-flash-lite')
            dusunce_logger.info("Gemini'ye video analizi isteği gönderiliyor... 🚀🌌") # Düşünce loguna ekle
            response = await model.generate_content_async([
                analysis_prompt,
                {"mime_type": "video/mp4", "data": video_bytes}
            ])
            dusunce_logger.info(f"Video Analizi Cevabı (Gemini): {response.text}") # Düşünce loguna ekle


            # **Yeni Kontrol: Yanıt Engellenmiş mi? (Video)**
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason
                logger.warning(f"Prompt blocked for video analysis. Reason: {block_reason}")
                dusunce_logger.warning(f"Video analizi için prompt engellendi. Sebep: {block_reason}") # Düşünce loguna ekle
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
                await split_and_send_message(update, response_text.strip()) # .strip() ekleyerek baştaki ve sondaki boşlukları temizliyoruz

        except Exception as processing_error:
            logger.error(f"Video processing error: {processing_error}", exc_info=True)
            dusunce_logger.error(f"Video işleme hatası: {processing_error}", exc_info=True) # Düşünce loguna ekle
            error_message = get_error_message('ai_error', user_lang)
            await update.message.reply_text(error_message)


    except Exception as e:
        logger.error(f"Kritik video işleme hatası: {e}", exc_info=True)
        dusunce_logger.error(f"Kritik video işleme hatası: {e}", exc_info=True) # Düşünce loguna ekle
        await update.message.reply_text(get_error_message('general', user_lang))

# Token and memory error handlers (aynı kalır)
async def handle_token_limit_error(update: Update):
    error_message = "Ay ay ay! Mesaj geçmişi çok uzun! 🥺 Şu an cevap veremiyorum ama biraz bekleyip tekrar dener misin? 🙏"
    await update.message.reply_text(error_message)

async def handle_memory_error(update: Update):
    error_message = "Hafızam doldu sandım bir an! 🤯 Bellek sınırına ulaşıldı galiba... Biraz bekleyip tekrar dener misin? 🙏"
    await update.message.reply_text(error_message)

# Emoji adding function (düşünce logları eklendi)
def add_emojis_to_text(text):
    # ... (same as before)
    try:
        # Use Gemini to suggest relevant emojis - now for a furry fox protogen!
        emoji_model = genai.GenerativeModel('gemini-2.0-flash-lite')

        # Prompt Gemini to suggest emojis based on text context AND personality!
        emoji_prompt = f"""
        Sen ultra complex bir Protogen furry fox'sun, Nyxie.  Aşağıdaki metni analiz et ve kişiliğine UYGUN, en alakalı ve abartılı OLMAYAN emoji(leri) öner.  ÇOK FAZLA EMOJİ KULLANMA, ama duyguyu ifade etmede çekinme!

        Metin: "{text}"

        Kurallar:
        - 0-3 arası emoji öner.  Duyguyu veya ana temayı iyi yakalayanları seç.
        - Emojiler metnin tonuna ve Nyxie'nin kişiliğine uygun olsun.  Enerjik, oyuncu, sevecen, teknoloji meraklısı bir furry fox protogen gibi düşün.
        - Eğer uygun emoji yoksa, boş dize döndür.
        - SADECE emoji(leri) veya boş dize ile yanıt ver. Başka metin veya açıklama YOK.

        Yanıt formatı: Sadece emoji(ler) veya boş dize (aralarında boşluk olabilir)
        """
        dusunce_logger.info(f"Gelişmiş Emoji Promptu:\n{emoji_prompt}")

        emoji_response = emoji_model.generate_content(emoji_prompt)
        dusunce_logger.info(f"Gelişmiş Emoji Cevabı (Gemini): {emoji_response.text}")

        if emoji_response.prompt_feedback and emoji_response.prompt_feedback.block_reason:
            logger.warning("Emoji suggestion blocked.")
            dusunce_logger.warning("Emoji önerisi engellendi.")
            return text
        else:
            suggested_emojis_str = emoji_response.text.strip()

            # Eğer emoji önerilmediyse, orijinal metni döndür
            if not suggested_emojis_str:
                return text

            suggested_emojis = suggested_emojis_str.split() # Birden fazla emoji önerisi için

            # Emojileri cümlenin sonuna ekle
            return f"{text} {' '.join(suggested_emojis)}" # Emojileri aralarına boşluk koyarak birleştir
    except Exception as e:
        logger.error(f"Error adding context-relevant emojis: {e}")
        dusunce_logger.error(f"Emoji ekleme hatası: {e}")
        return text  # Return original text if emoji addition fails

# Analysis prompt function (aynı kalır)
def get_analysis_prompt(media_type, caption, lang):
    # ... (aynı kalır)
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