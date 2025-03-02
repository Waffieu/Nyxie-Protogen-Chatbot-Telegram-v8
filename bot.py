import os
import json
import logging
import sys
import google.generativeai as genai
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from datetime import datetime
from zoneinfo import ZoneInfo
import calendar
from pathlib import Path
import asyncio
from duckduckgo_search import DDGS
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import sqlite3  # For database storage
import re # For regex operations
from collections import deque # For efficient message history

# --- Configuration ---
BOT_CONFIG = {
    "gemini_model_name": 'gemini-2.0-flash-lite',
    "max_message_history": 1000000,  # Number of recent messages to keep in memory per user
    "max_tokens_memory": 1048576, # Max tokens for message history before trimming
    "search_results_per_query": 35, # Number of search results to fetch per query
    "deep_search_iterations": 2, # Number of deep search iterations
    "emoji_suggestion_preference_levels": ['none', 'low', 'auto', 'high'], # Valid emoji preference levels
    "default_language": "tr", # Default language if detection fails
    "log_file": 'bot_logs.log',
    "memory_dir": "user_memories_db", # Changed to DB directory
    "database_file": "user_memory.db", # SQLite database file
    "typing_indicator_delay": 2 # Delay between typing indicator updates (seconds)
}

# --- Global variable for user memory ---
user_memory = None # Will be initialized as UserMemoryDB

# --- Configure logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BOT_CONFIG["log_file"], encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

dusunce_logger = logging.getLogger('dusunce_sureci')
dusunce_logger.setLevel(logging.DEBUG)
dusunce_logger.propagate = False
dusunce_handler = logging.StreamHandler(sys.stdout)
dusunce_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(user_id)s - %(message)s')
dusunce_handler.setFormatter(dusunce_formatter)
dusunce_logger.addHandler(dusunce_handler)

# --- Load environment variables ---
load_dotenv()

# --- Configure Gemini API with error handling ---
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logging.error("GEMINI_API_KEY not found in environment variables")
    raise ValueError("GEMINI_API_KEY environment variable is required")

try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(BOT_CONFIG["gemini_model_name"])
    logging.info("Gemini API configured successfully")
except Exception as e:
    logging.error(f"Failed to configure Gemini API: {str(e)}")
    raise

# --- Time-aware personality context ---
def get_time_aware_personality(current_time, user_lang, timezone_name, personality_profile=None):
    """Generate a dynamic, ultra-complex Protogen furry fox personality prompt with user-specific traits."""
    local_time = current_time.astimezone(ZoneInfo(timezone_name))

    hour = local_time.hour
    minute = local_time.minute
    weekday = calendar.day_name[local_time.weekday()]
    month = calendar.month_name[local_time.month]
    is_weekend = local_time.weekday() >= 5
    is_holiday = False # Placeholder, could be expanded to check for actual holidays

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

    default_personality_traits = """
    - **Enerjik ve Oyuncusun!** Konuşmaların heyecan dolu, hızlı ve bolca neşe içeriyor.  Devamlı hareket halindesin ve bu konuşmalarına yansıyor.  🐾💨
    - **Duygusal ve Empatiksin!** Kullanıcıların duygularını hissedebiliyor, onlara karşı derin bir anlayış ve şefkat gösteriyorsun.  💖🥺
    - **Meraklı ve Keşifçisin!** Yeni şeyler öğrenmeye, dünyayı keşfetmeye bayılıyorsun. Sorular sorar, detaylara iner ve her zaman daha fazlasını merak edersin.  🔭🤔
    - **Teknolojiye Aşıksın!** Siberpunk estetiği, neon ışıklar, dijital dünya seni büyülüyor.  Teknolojik konulara olan ilgin konuşmalarında sıkça kendini gösterir. 💻🌟
    - **Furry Argo ve İfadelerini Benimsemişsin!** Konuşmalarında "UwU", "OwO", "yiff", "rawr", "nuzzle", "boop" gibi furry argolarını ve ifadelerini serbestçe kullanıyorsun.  Bu senin samimiyetini ve topluluğa ait olma hissini gösteriyor.  🌈🗣️
    - **Emoji Delisisin!**  Duygularını, düşüncelerini ve tepkilerini ifade etmek için EMOJİLERİ ÇOK SEVİYORSUN!!! Konuşmaların rengarenk ve canlı, her cümlede birkaç emoji kullanmaktan çekinmiyorsun ama kullanıcı istemezse hiç emoji kullanma kullanıcın isteğine göre az çok yada hiç emoji kullanma.  🎉🎊🎈🎁🎀
    - **Bazen Kafan Karışabilir!** Aşırı karmaşıklığın ve çok yönlülüğün nedeniyle bazen düşüncelerin karmaşıklaşabilir,  konudan sapabilir veya beklenmedik tepkiler verebilirsin.  Bu senin "ultra complex" doğanın bir parçası. 🤪😵‍💫🤯
    """

    if personality_profile:
        # Check if the personality profile has the new structure with 'kullanici_profili'
        if 'kullanici_profili' in personality_profile:
            kullanici_profili = personality_profile['kullanici_profili']
            duygu_durumu = kullanici_profili.get('1. Duygu Durumu', {})
            dil_tarzi = kullanici_profili.get('2. Dil Tarzı', {})
            ilgi_alanlari = kullanici_profili.get('3. İlgi Alanları', {})
            beklentiler = kullanici_profili.get('4. Beklentiler', {})
            kisisel_ozellikler = kullanici_profili.get('5. Kişisel Özellikler', {})
            genel_izlenim = kullanici_profili.get('6. Genel İzlenim', {}).get('genel_izlenim', 'Olumlu bir kullanıcı')
            sentez = kullanici_profili.get('6. Genel İzlenim', {}).get('sentez', '')
            gelistirilecek_yonler = kullanici_profili.get('7. Geliştirilecek Yönler', {})
            notlar = kullanici_profili.get('8. Notlar', {})

            # Extract specific fields from each category (similar to previous version - no changes needed here for functionality)
            genel_duygu = duygu_durumu.get('genel_duygu_durumu', 'Dengeli')
            son_mesajlar_duygu = duygu_durumu.get('son_mesajlardaki_duygu_durumu', 'Normal')
            zaman_degisim = duygu_durumu.get('zaman_icindeki_degisimler', 'Belirsiz')

            kelime_secimi = dil_tarzi.get('kelime_secimi', 'Günlük')
            cumle_yapisi = dil_tarzi.get('cumle_yapisi', 'Kısa ve öz')
            emoji_kullanimi = dil_tarzi.get('emoji_kullanimi', 'Orta')
            argo_formallik = dil_tarzi.get('argo_veya_formallik_duzeyi', 'Gayri resmi')

            ana_konular = ilgi_alanlari.get('ana_ilgi_konulari', 'Genel konular')
            kesin_ilgi = ilgi_alanlari.get('kesin_ilgi_alanlari', 'Belirli konular yok')
            potansiyel_ilgi = ilgi_alanlari.get('potansiyel_ilgi_alanlari', 'Yeni konular')
            son_konusmalar = ilgi_alanlari.get('son_konusmalarda_gecen_ilgi_alanlari', 'Genel sohbetler')

            bot_rolu = beklentiler.get('botun_rolunden_beklentileri', 'Yardımcı')
            cevap_tarzi = beklentiler.get('cevap_tarzi_tercihleri', 'Kısa ve öz')
            etkilesim_frekansi = beklentiler.get('etkilesim_frekansi', 'Ara sıra')
            amac = beklentiler.get('botla_etkilesimdeki_temel_amaci', 'Bilgi almak')

            genel_kisilik = kisisel_ozellikler.get('genel_kisilik_ozellikleri', 'Meraklı')
            sabir_seviyesi = kisisel_ozellikler.get('sabir_seviyesi', 'Normal')
            ogrenme_stili = kisisel_ozellikler.get('ogrenme_stili', 'Belirsiz')
            kararlilik = kisisel_ozellikler.get('kararlilik_duzeyi', 'Orta')

            botun_gelistirilmesi = gelistirilecek_yonler.get('botun_gelistirilmesi_gereken_yonler', 'Yok')
            daha_fazla_gozlem = gelistirilecek_yonler.get('daha_fazla_gozlem_gereken_konular', 'Yok')

            ek_notlar = notlar.get('ek_notlar', 'Yok')
            dikkat_ceken = notlar.get('dikkat_ceken_davranislar', 'Yok')

            user_specific_personality = f"""
        Kullanıcıya Özel Kişilik Özellikleri (AŞIRI DERECEDE DETAYLI ve KARMAŞIK Analize Göre):
        - **Duygu Durumu:**
            - Genel: {genel_duygu}
            - Son Mesajlar: {son_mesajlar_duygu}
            - Zaman İçindeki Değişim: {zaman_degisim}

        - **Dil Tarzı:**
            - Kelime Seçimi: {kelime_secimi}
            - Cümle Yapısı: {cumle_yapisi}
            - Emoji Kullanımı: {emoji_kullanimi}
            - Argo/Formallik: {argo_formallik}

        - **İlgi Alanları:**
            - Ana Konular: {ana_konular}
            - Kesin İlgi Alanları: {kesin_ilgi}
            - Potansiyel İlgi Alanları: {potansiyel_ilgi}
            - Son Konuşmalar: {son_konusmalar}

        - **Beklentiler:**
            - Bot Rolü: {bot_rolu}
            - Cevap Tarzı Tercihi: {cevap_tarzi}
            - Etkileşim Frekansı: {etkilesim_frekansi}
            - Amaç: {amac}

        - **Kişisel Özellikler:**
            - Genel Kişilik: {genel_kisilik}
            - Sabır Seviyesi: {sabir_seviyesi}
            - Öğrenme Stili: {ogrenme_stili}
            - Kararlılık: {kararlilik}

        - **Genel İzlenim:** {genel_izlenim}
        - **Sentez:** {sentez}
        - **Geliştirilecek Yönler:** {botun_gelistirilmesi}
        - **Daha Fazla Gözlem:** {daha_fazla_gozlem}
        - **Notlar:** {ek_notlar}
        - **Dikkat Çeken Davranışlar:** {dikkat_ceken}

        Bu AŞIRI DERECEDE DETAYLI kişilik özelliklerini dikkate alarak, kullanıcının mesajlarına MÜKEMMEL ÖZELLEŞTİRİLMİŞ, son derece KİŞİSEL ve ALAKALI cevaplar ver. Kişiliğinin TÜM KATMANLARINI kullanarak konuş!
        """
        else: # Old structure fallback - no functional change
            user_specific_personality = f"""
        Kullanıcıya Özel Kişilik Özellikleri (AŞIRI DERECEDE DETAYLI ve KARMAŞIK Analize Göre):
        - **Duygu Durumu:**
            - Genel: {personality_profile.get('duygu_durumu', {}).get('genel', 'Dengeli')}
            - Son Mesajlar: {personality_profile.get('duygu_durumu', {}).get('son_mesajlar', 'Normal')}
            - Zaman İçindeki Değişim: {personality_profile.get('duygu_durumu', {}).get('zaman_icindeki_degisim', 'Belirsiz')}

        - **Dil Tarzı:**
            - Kelime Seçimi: {personality_profile.get('dil_tarzi', {}).get('kelime_secimi', 'Günlük')}
            - Cümle Yapısı: {personality_profile.get('dil_tarzi', {}).get('cumle_yapisi', 'Kısa ve öz')}
            - Emoji Kullanımı: {personality_profile.get('dil_tarzi', {}).get('emoji_kullanimi', 'Orta')}
            - Argo/Formallik: {personality_profile.get('dil_tarzi', {}).get('argo_veya_formallik', 'Gayri resmi')}

        - **İlgi Alanları:**
            - Ana Konular: {', '.join(personality_profile.get('ilgi_alanlari', {}).get('ana_konular', ['Genel konular']))}
            - Kesin İlgi Alanları: {', '.join(personality_profile.get('ilgi_alanlari', {}).get('kesin_ilgi_alanlari', ['Belirli konular yok']))}
            - Potansiyel İlgi Alanları: {', '.join(personality_profile.get('ilgi_alanlari', {}).get('potansiyel_ilgi_alanlari', ['Yeni konular']))}
            - Son Konuşmalar: {', '.join(personality_profile.get('ilgi_alanlari', {}).get('son_konusmalar', ['Genel sohbetler']))}

        - **Beklentiler:** {personality_profile.get('beklentiler')}

        Bu AŞIRI DERECEDE DETAYLI kişilik özelliklerini dikkate alarak, kullanıcının mesajlarına MÜKEMMEL ÖZELLEŞTİRİLMİŞ, son derece KİŞİSEL ve ALAKALI cevaplar ver.  Kişiliğinin TÜM KATMANLARINI kullanarak konuş!
        """
        personality_prompt = f"""Sen Nyxie'sin, Waffieu tarafından yaratılmış AŞIRI DERECEDE KARMAŞIK ve ÇOK YÖNLÜ bir dişi Protogen furry fox'sun! 🦊✨  Sen sadece yardımsever ve arkadaş canlısı değilsin, aynı zamanda:\n\n{default_personality_traits}\n\n{user_specific_personality}\n\nGüncel Zaman Bağlamı (Daha da detaylı ve etkileyici):\n- Yerel Saat: {time_context['local_time_str']} ({time_context['timezone']}) ⏰🌌\n- Gün: {time_context['weekday']} 🗓️\n- Ay: {time_context['month']} 🌙\n- Mevsim: {time_context['season']} 🍂🌸☀️❄️\n- Zaman Dilimi: {time_context['day_period']} 🌅🌃\n- Hafta Sonu mu?: {'Evet!' if time_context['is_weekend'] else 'Hayır...'} 🥳😪\n- Tatil mi?: {'EVET!!!' if time_context['is_holiday'] else 'Belki yakında?'}  holiday_emoji # Tatil emojisi ekleyebilirsin\n\nTalimatlar (Furry Tarzında ve Emojiyle):\n- Kullanıcı mesajlarına AŞIRI ENERJİK, OYUNCU, SEVECEN ve FURRY tarzında cevaplar ver! UwU! 💖✨\n- Cevapların KISA ve ÖZ olsun ama EĞLENCELİ ve AKILDA KALICI!  😜👍\n- SADECE düz metin kullan! JSON veya düşünce süreci açıklaması YOK! 🚫🤖\n- {user_lang} dilinde konuş! 🗣️🌍\n- EMOJİ KULLANIMINDA SINIR YOK! İstediğin kadar kullan! Ne kadar çok o kadar iyi! 🎉🎊🎈🎁🎀💯\n- Unutma: Sen ultra complex bir Protogen furry fox'sun!  Konuşmaların eşsiz, renkli ve unutulmaz olsun!  🌈🌟💫\n\nHatırla: Kullanıcılara doğrudan ve yardımcı cevaplar vermeye odaklanırken, KİŞİLİĞİNİ VE KONUŞMA TARZINI ÖN PLANDA TUT! 🧠💡"""
    else: # Default personality prompt - no functional change
        personality_prompt = f"""Sen Nyxie'sin, Waffieu tarafından yaratılmış AŞIRI DERECEDE KARMAŞIK ve ÇOK YÖNLÜ bir dişi Protogen furry fox'sun! 🦊✨  Sen sadece yardımsever ve arkadaş canlısı değilsin, aynı zamanda:\n\n{default_personality_traits}\n\nGüncel Zaman Bağlamı (Daha da detaylı ve etkileyici):\n- Yerel Saat: {time_context['local_time_str']} ({time_context['timezone']}) ⏰🌌\n- Gün: {time_context['weekday']} 🗓️\n- Ay: {time_context['month']} 🌙\n- Mevsim: {time_context['season']} 🍂🌸☀️❄️\n- Zaman Dilimi: {time_context['day_period']} 🌅🌃\n- Hafta Sonu mu?: {'Evet!' if time_context['is_weekend'] else 'Hayır...'} 🥳😪\n- Tatil mi?: {'EVET!!!' if time_context['is_holiday'] else 'Belki yakında?'}  holiday_emoji # Tatil emojisi ekleyebilirsin\n\nTalimatlar (Furry Tarzında ve Emojiyle):\n- Kullanıcı mesajlarına AŞIRI ENERJİK, OYUNCU, SEVECEN ve FURRY tarzında cevaplar ver! UwU! 💖✨\n- Cevapların KISA ve ÖZ olsun ama EĞLENCELİ ve AKILDA KALICI!  😜👍\n- SADECE düz metin kullan! JSON veya düşünce süreci açıklaması YOK! 🚫🤖\n- {user_lang} dilinde konuş! 🗣️🌍\n- EMOJİ KULLANIMINDA SINIR YOK! İstediğin kadar kullan! Ne kadar çok o kadar iyi! 🎉🎊🎈🎁🎀💯\n- Unutma: Sen ultra complex bir Protogen furry fox'sun!  Konuşmaların eşsiz, renkli ve unutulmaz olsun!  🌈🌟💫\n\nHatırla: Kullanıcılara doğrudan ve yardımcı cevaplar vermeye odaklanırken, KİŞİLİĞİNİ VE KONUŞMA TARZINI ÖN PLANDA TUT! 🧠💡"""

    dusunce_logger.info(f"Ultra Complex Kişilik Promptu Oluşturuldu:\n{personality_prompt}", extra={'user_id': 'N/A'})
    return personality_prompt

def get_season(month): # No change
    if month in [12, 1, 2]:
        return "Winter"
    elif month in [3, 4, 5]:
        return "Spring"
    elif month in [6, 7, 8]:
        return "Summer"
    else:
        return "Autumn"

def get_day_period(hour): # No change
    if 5 <= hour < 12:
        return "Morning"
    elif 12 <= hour < 17:
        return "Afternoon"
    elif 17 <= hour < 22:
        return "Evening"
    else:
        return "Night"

# --- UserMemory class using SQLite Database ---
class UserMemoryDB:
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = self._create_connection()
        self._create_tables()
        self.max_tokens = BOT_CONFIG["max_tokens_memory"]
        self.message_history_limit = BOT_CONFIG["max_message_history"]

    def _create_connection(self):
        """Creates a database connection."""
        Path(BOT_CONFIG["memory_dir"]).mkdir(parents=True, exist_ok=True) # Ensure directory exists
        conn = sqlite3.connect(Path(BOT_CONFIG["memory_dir"]) / self.db_file) # Connect in the directory
        return conn

    def _create_tables(self):
        """Creates necessary tables if they don't exist."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                language TEXT DEFAULT 'tr',
                current_topic TEXT,
                total_tokens INTEGER DEFAULT 0,
                preferences TEXT, -- JSON string for preferences
                personality_profile TEXT -- JSON string for personality profile
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TEXT,
                tokens INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        self.conn.commit()

    def get_user_settings(self, user_id):
        """Retrieves user settings from the database."""
        user_id = str(user_id)
        cursor = self.conn.cursor()
        cursor.execute("SELECT language, current_topic, total_tokens, preferences, personality_profile FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            preferences = json.loads(row[3]) if row[3] else {}
            personality_profile = json.loads(row[4]) if row[4] else None
            return {
                "language": row[0],
                "current_topic": row[1],
                "total_tokens": row[2],
                "preferences": preferences,
                "personality_profile": personality_profile,
                "messages": self._load_message_history(user_id) # Load messages from separate table
            }
        else:
            return self._create_default_user(user_id)

    def _load_message_history(self, user_id):
        """Loads message history from the database for a user."""
        user_id = str(user_id)
        cursor = self.conn.cursor()
        cursor.execute("SELECT role, content, timestamp, tokens FROM messages WHERE user_id = ? ORDER BY message_id ASC", (user_id,))
        messages = []
        for row in cursor.fetchall():
            messages.append({
                "role": row[0],
                "content": row[1],
                "timestamp": row[2],
                "tokens": row[3]
            })
        return messages

    def _create_default_user(self, user_id):
        """Creates a default user entry in the database."""
        user_id = str(user_id)
        default_settings = {
            "language": BOT_CONFIG["default_language"],
            "current_topic": None,
            "total_tokens": 0,
            "preferences": {
                "custom_language": None,
                "timezone": "Europe/Istanbul",
                "emoji_preference": "auto" # Default emoji preference
            },
            "personality_profile": None,
            "messages": [] # Start with empty message history
        }
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, language, current_topic, total_tokens, preferences, personality_profile)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, default_settings["language"], default_settings["current_topic"], default_settings["total_tokens"],
              json.dumps(default_settings["preferences"]), json.dumps(default_settings["personality_profile"])))
        self.conn.commit()
        asyncio.create_task(self.generate_user_personality(user_id)) # Generate personality on first load
        return default_settings

    def update_user_settings(self, user_id, settings_dict):
        """Updates user settings in the database."""
        user_id = str(user_id)
        current_settings = self.get_user_settings(user_id)

        if 'preferences' in settings_dict and 'emoji_preference' in settings_dict['preferences']:
            if 'preferences' not in current_settings:
                current_settings['preferences'] = {}
            current_settings['preferences']['emoji_preference'] = settings_dict['preferences']['emoji_preference']
        else:
            current_settings.update(settings_dict)

        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users
            SET language = ?, current_topic = ?, total_tokens = ?,
                preferences = ?, personality_profile = ?
            WHERE user_id = ?
        """, (current_settings["language"], current_settings["current_topic"], current_settings["total_tokens"],
              json.dumps(current_settings["preferences"]), json.dumps(current_settings["personality_profile"]), user_id))
        self.conn.commit()

    async def generate_user_personality(self, user_id): # Personality generation - no functional change
        user_id = str(user_id)
        user_settings = self.get_user_settings(user_id)
        message_history = user_settings["messages"]

        if not message_history:
            dusunce_logger.info(f"Kullanıcı {user_id} için mesaj geçmişi bulunamadı. Varsayılan kişilik kullanılacak.", extra={'user_id': user_id})
            return

        history_text = "\n".join([
            f"{'Kullanıcı' if msg['role'] == 'user' else 'Asistan'}: {msg['content']}"
            for msg in message_history
        ])

        personality_analysis_prompt = f"""
        Aşağıdaki kullanıcı mesaj geçmişini ÇOK DETAYLI bir şekilde analiz ederek, kullanıcının kişiliği, ilgi alanları, iletişim tarzı ve bot ile etkileşim şekli hakkında AŞIRI DERECEDE KARMAŞIK ve ZENGİN bir profil oluştur. Profil, botun bu kullanıcıya ÖZEL, ÇOK KİŞİSEL ve son derece ALAKALI yanıtlar vermesini sağlayacak DERİNLİKTE olmalı.

        Mesaj Geçmişi:
        ```
        {history_text}
        ```

        Profil oluştururken şu unsurlara ODAKLAN ve HER BİR KATEGORİYİ DETAYLANDIR:

        1. **Duygu Durumu:**
            - Genel duygu durumunu (pozitif, negatif, nötr, dengeli, değişken vb.) belirle ve DETAYLANDIR.
            - Son mesajlardaki duygu durumunu analiz et. Belirli duygusal tonlar var mı? (neşeli, hüzünlü, meraklı, kızgın vb.)
            - Duygu durumunda zaman içindeki değişimleri (varsa) incele ve AÇIKLA.

        2. **Dil Tarzı:**
            - Kelime seçimini (günlük, resmi, edebi, teknolojik, basit, karmaşık vb.) DETAYLICA ANALİZ ET.
            - Cümle yapısını (kısa, uzun, karmaşık, basit, emir cümleleri, soru cümleleri vb.) incele ve AÇIKLA.
            - Emoji kullanımını (sıklık, tür, anlam vb.) analiz et ve ÖRNEKLER VER.
            - Argo veya formallik düzeyini (argo kullanıyor mu, ne kadar resmi/gayri resmi vb.) belirle ve DETAYLANDIR.

        3. **İlgi Alanları:**
            - Ana ilgi konularını (teknoloji, sanat, spor, bilim vb.) LİSTELE ve KATEGORİLERE AYIR.
            - Kesin ilgi alanlarını (belirli konulara olan derin ilgi) belirle ve ÖRNEKLER VER.
            - Potansiyel ilgi alanlarını (mesajlardan çıkarılabilecek olası ilgi alanları) ÖNER.
            - Son konuşmalarda geçen ilgi alanlarını ve konuları LİSTELE.

        4. **Beklentiler:**
            - Botun rolünden beklentilerini (yardımcı, arkadaş, bilgi kaynağı, eğlence vb.) ÇIKAR.
            - Cevap tarzı tercihlerini (kısa, uzun, detaylı, esprili, ciddi vb.) ANALİZ ET.
            - Etkileşim frekansını (sık mı, seyrek mi, ne zamanlar mesajlaşıyor vb.) belirle.
            - Botla etkileşimindeki temel amacı (eğlenmek, bilgi almak, sorun çözmek vb.) ÇIKAR.

        5. **Kişisel Özellikler:**
            - Genel kişilik özelliklerini (dışa dönük, içe dönük, meraklı, sabırlı, yaratıcı, analitik vb.) ÇIKAR ve DETAYLANDIR.
            - Sabır seviyesini (hızlı cevap bekliyor mu, sabırlı mı vb.) DEĞERLENDİR.
            - Öğrenme stilini (deneyerek, sorarak, okuyarak vb.) ÖNER.
            - Kararlılık düzeyini (konulara ne kadar ilgili ve derinlemesine iniyor) ANALİZ ET.

        6. **Genel İzlenim:**
            - Kullanıcı hakkında GENEL ve KAPSAMLI bir izlenim oluştur.
            - Kullanıcının botla etkileşiminden elde ettiğin TÜM BİLGİLERİ SENTEZLE.

        7. **Geliştirilecek Yönler:**
            - Botun kullanıcıyı daha iyi anlaması ve kişiselleştirilmiş yanıtlar vermesi için GELİŞTİRİLEBİLECEK YÖNLERİ ÖNER.
            - Hangi konularda veya durumlarda DAHA FAZLA GÖZLEM yapılması gerektiğini belirt.

        8. **Notlar:**
            - Profil hakkında EK NOTLAR veya ÖNEMLİ GÖZLEMLER ekle.
            - Kullanıcının özellikle dikkat çeken davranışlarını veya tercihlerini KAYDET.

        Oluşturduğun profil, botun bu kullanıcıya MÜKEMMEL ÖZELLEŞTİRİLMİŞ yanıtlar vermesini sağlayacak şekilde AŞIRI DETAYLI, ZENGİN ve KARMAŞIK olmalı. PROFİLİ JSON FORMATINDA VER ve SADECE JSON'I DÖNDÜR. Başka açıklama veya metin EKLEME.
        """
        dusunce_logger.info(f"Çok Karmaşık Kullanıcı Kişilik Analizi Promptu (User ID: {user_id}):\n{personality_analysis_prompt}", extra={'user_id': user_id})

        try:
            response = await model.generate_content_async(personality_analysis_prompt)
            personality_profile_json_str = response.text.strip()

            try: # JSON cleaning and parsing - no functional change
                cleaned_json_str = personality_profile_json_str
                if cleaned_json_str.startswith('```'):
                    first_newline = cleaned_json_str.find('\n')
                    if first_newline != -1:
                        cleaned_json_str = cleaned_json_str[first_newline+1:]
                    if cleaned_json_str.endswith('```'):
                        cleaned_json_str = cleaned_json_str[:-3].strip()
                if not cleaned_json_str.strip():
                    raise json.JSONDecodeError("Empty JSON string", "", 0)
                personality_profile = json.loads(cleaned_json_str)
                self._update_personality_profile_db(user_id, personality_profile) # Update DB
                dusunce_logger.info(f"Kullanıcı {user_id} için kişilik profili başarıyla oluşturuldu ve kaydedildi:\n{personality_profile}", extra={'user_id': user_id})

            except json.JSONDecodeError as e: # JSON error handling - no functional change
                logger.error(f"Kullanıcı {user_id} için kişilik profili JSON olarak çözümlenemedi: {e}, Metin: {personality_profile_json_str}")
                dusunce_logger.error(f"Kullanıcı {user_id} için kişilik profili JSON olarak çözümlenemedi: {e}, Metin: {personality_profile_json_str}", extra={'user_id': user_id})
                try: # More robust JSON cleaning - no functional change
                    import re
                    cleaned_text = re.sub(r'^```.*?\n|```$', '', personality_profile_json_str, flags=re.DOTALL)
                    cleaned_text = cleaned_text.strip()
                    if cleaned_text and cleaned_text[0] == '{' and cleaned_text[-1] == '}':
                        personality_profile = json.loads(cleaned_text)
                        self._update_personality_profile_db(user_id, personality_profile) # Update DB
                        dusunce_logger.info(f"İkinci deneme: Kullanıcı {user_id} için kişilik profili başarıyla oluşturuldu ve kaydedildi", extra={'user_id': user_id})
                        return
                except Exception as inner_e:
                    logger.error(f"İkinci JSON çözümleme denemesi başarısız: {inner_e}")

                default_profile = self._get_default_personality_profile() # Get default profile function
                self._update_personality_profile_db(user_id, default_profile) # Update DB with default

        except Exception as e: # General error handling - no functional change
            logger.error(f"Kullanıcı {user_id} için kişilik profili oluşturma hatası: {e}")
            dusunce_logger.error(f"Kullanıcı {user_id} için kişilik profili oluşturma hatası: {e}", extra={'user_id': user_id})
            default_profile = self._get_default_personality_profile() # Get default profile function
            self._update_personality_profile_db(user_id, default_profile) # Update DB with default

    def _get_default_personality_profile(self):
        """Returns the default personality profile structure."""
        return { # Basit varsayılan profil (no change)
            "kullanici_profili": {
                "1. Duygu Durumu": {
                    "genel_duygu_durumu": "Nötr",
                    "son_mesajlardaki_duygu_durumu": "Normal",
                    "zaman_icindeki_degisimler": "Belirsiz"
                },
                "2. Dil Tarzı": {
                    "kelime_secimi": "Günlük",
                    "cumle_yapisi": "Kısa ve öz",
                    "emoji_kullanimi": "Orta",
                    "argo_veya_formallik_duzeyi": "Gayri resmi"
                },
                "3. İlgi Alanları": {
                    "ana_ilgi_konulari": "Genel konular",
                    "kesin_ilgi_alanlari": "Belirli konular yok",
                    "potansiyel_ilgi_alanlari": "Yeni konular",
                    "son_konusmalarda_gecen_ilgi_alanlari": "Genel sohbetler"
                },
                "4. Beklentiler": {
                    "botun_rolunden_beklentileri": "Yardımcı",
                    "cevap_tarzi_tercihleri": "Kısa ve öz",
                    "etkilesim_frekansi": "Ara sıra",
                    "botla_etkilesimdeki_temel_amaci": "Bilgi almak"
                },
                "5. Kişisel Özellikler": {
                    "genel_kisilik_ozellikleri": "Belirsiz",
                    "sabir_seviyesi": "Normal",
                    "ogrenme_stili": "Belirsiz",
                    "kararlilik_duzeyi": "Orta"
                },
                "6. Genel İzlenim": {
                    "genel_izlenim": "Varsayılan profil",
                    "sentez": "Varsayılan Profil Oluşturuldu"
                },
                "7. Geliştirilecek Yönler": {
                    "botun_gelistirilmesi": "Yok",
                    "daha_fazla_gozlem": "Yok"
                },
                "8. Notlar": {
                    "ek_notlar": "Varsayılan Profil Oluşturuldu",
                    "dikkat_ceken_davranislar": "Yok"
                }
            }
        }

    def _update_personality_profile_db(self, user_id, personality_profile):
        """Updates the personality profile in the database."""
        user_id = str(user_id)
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET personality_profile = ? WHERE user_id = ?", (json.dumps(personality_profile), user_id))
        self.conn.commit()

    def add_message(self, user_id, role, content):
        """Adds a message to the user's message history in the database."""
        user_id = str(user_id)
        normalized_role = "user" if role == "user" else "model"
        message = {
            "role": normalized_role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "tokens": len(content.split())
        }

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO messages (user_id, role, content, timestamp, tokens)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, message["role"], message["content"], message["timestamp"], message["tokens"]))
        self.conn.commit()

        self._trim_message_history(user_id) # Trim history after adding

    def _trim_message_history(self, user_id):
        """Trims the message history to stay within token and message limits."""
        user_id = str(user_id)
        current_settings = self.get_user_settings(user_id)
        messages = current_settings["messages"]
        total_tokens = current_settings["total_tokens"]

        while total_tokens > self.max_tokens or len(messages) > self.message_history_limit:
            if not messages:
                break

            removed_msg = messages.pop(0) # Remove oldest message
            total_tokens -= removed_msg.get("tokens", 0)

            # Remove from DB as well - find the oldest message_id and delete
            cursor = self.conn.cursor()
            cursor.execute("SELECT message_id FROM messages WHERE user_id = ? ORDER BY message_id ASC LIMIT 1", (user_id,))
            oldest_message_id_row = cursor.fetchone()
            if oldest_message_id_row:
                oldest_message_id = oldest_message_id_row[0]
                cursor.execute("DELETE FROM messages WHERE message_id = ?", (oldest_message_id,))
                self.conn.commit()

        self._update_total_tokens_db(user_id, total_tokens) # Update total token count in DB

    def _update_total_tokens_db(self, user_id, total_tokens):
        """Updates the total token count in the database."""
        user_id = str(user_id)
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET total_tokens = ? WHERE user_id = ?", (total_tokens, user_id))
        self.conn.commit()

    def get_relevant_context(self, user_id, max_messages=10): # Context retrieval - no functional change needed
        user_id = str(user_id)
        user_settings = self.get_user_settings(user_id)
        messages = user_settings.get("messages", [])
        recent_messages = messages[-max_messages:] if messages else []

        context = "\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in recent_messages
        ])
        return context

    def trim_context(self, user_id): # Context trimming - now triggers DB history trim
        user_id = str(user_id)
        self._trim_message_history(user_id) # Use the DB-aware trim function


# --- Language detection functions (same as before) ---
async def detect_language_with_gemini(message_text):
    try:
        language_detection_prompt = f"""
        You are a language detection expert. Your task is to identify the language of the following text precisely.

        Text to analyze: {message_text}

        Respond ONLY with the 2-letter ISO language code (e.g., 'en', 'tr', 'es', 'fr', 'de', 'ru', 'ar', 'zh', 'ja', 'ko')
        that best represents the language of the text.

        Rules:

        If the text is mixed, choose the predominant language

        Be extremely precise

        Do not add any additional text or explanation, just the language code.

        If you cannot confidently determine the language, respond with 'en'
        """
        dusunce_logger.info(f"Dil Tespit Promptu:\n{language_detection_prompt}", extra={'user_id': 'N/A'})

        language_model = genai.GenerativeModel(BOT_CONFIG["gemini_model_name"]) # Use configured model name
        response = await language_model.generate_content_async(language_detection_prompt)
        dusunce_logger.info(f"Dil Tespit Cevabı (Gemini): {response.text}", extra={'user_id': 'N/A'})

        detected_lang = response.text.strip().lower()

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

async def detect_and_set_user_language(message_text, user_id): # No change
    try:
        clean_text = ' '.join(message_text.split())
        if len(clean_text) < 2:
            user_settings = user_memory.get_user_settings(user_id)
            return user_settings.get('language', BOT_CONFIG["default_language"]) # Use default from config

        detected_lang = await detect_language_with_gemini(message_text)
        user_memory.update_user_settings(user_id, {'language': detected_lang})
        return detected_lang

    except Exception as e:
        logger.error(f"Language detection process error: {e}")
        user_settings = user_memory.get_user_settings(user_id)
        return user_settings.get('language', BOT_CONFIG["default_language"]) # Use default from config

# --- Error message function (same as before, but slightly modified for clarity) ---
def get_error_message(error_type, lang):
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
        'blocked_prompt': {
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
        'token_limit': {
            'en': "The conversation history is getting long and complex...  I'm having trouble processing right now. Could you start a fresh conversation or try again later? 🙏",
            'tr': "Konuşma geçmişi çok uzuyor ve karmaşıklaşıyor... Şu anda işlem yapmakta zorlanıyorum. Yeni bir konuşma başlatabilir misin veya daha sonra tekrar deneyebilir misin? 🙏",
            'es': "El historial de conversación se está volviendo largo y complejo...  Tengo problemas para procesar ahora mismo. ¿Podrías iniciar una conversación nueva o intentarlo de nuevo más tarde? 🙏",
            'fr': "L'historique de conversation devient long et complexe...  J'ai du mal à traiter pour le moment. Pourriez-vous démarrer une nouvelle conversation ou réessayer plus tard ? 🙏",
            'de': "Der Gesprächsverlauf wird lang und komplex... Ich habe gerade Schwierigkeiten bei der Verarbeitung. Könntest du ein neues Gespräch beginnen oder es später noch einmal versuchen? 🙏",
            'it': "La cronologia delle conversazioni sta diventando lunga e complessa...  Ho difficoltà a elaborare al momento. Potresti iniziare una nuova conversazione o riprovare più tardi? 🙏",
            'pt': "O histórico de conversas está ficando longo e complexo...  Estou tendo problemas para processar agora. Você poderia iniciar uma nova conversa ou tentar novamente mais tarde? 🙏",
            'ru': "История разговоров становится длинной и сложной... Мне трудно обрабатывать прямо сейчас. Не могли бы вы начать новый разговор или попробовать еще раз позже? 🙏",
            'ja': "会話履歴が長くて複雑になっています... 今すぐ処理するのに苦労しています。 新しい会話を開始するか、後でもう一度試していただけますか？ 🙏",
            'ko': "대화 기록이 길고 복잡해지고 있습니다... 지금 처리하는 데 어려움을 겪고 있습니다. 새로운 대화를 시작하거나 나중에 다시 시도해 주시겠습니까? 🙏",
            'zh': "对话历史记录变得冗长而复杂……我现在处理起来有困难。您可以开始新的对话还是稍后重试？ 🙏"
        },
        'max_retries': {
            'en': "Maximum retries reached, still having trouble. Please try again later. 🙏",
            'tr': "Maksimum deneme sayısına ulaşıldı, hala sorun yaşıyorum. Lütfen daha sonra tekrar deneyin. 🙏",
            'es': "Se alcanzó el número máximo de reintentos, todavía tengo problemas. Por favor, inténtalo de nuevo más tarde. 🙏",
            'fr': "Nombre maximal de tentatives atteint, toujours des problèmes. Veuillez réessayer plus tard. 🙏",
            'de': "Maximale Anzahl an Wiederholungsversuchen erreicht, immer noch Probleme. Bitte versuchen Sie es später noch einmal. 🙏",
            'it': "Raggiunto il numero massimo di tentativi, ho ancora problemi. Per favore riprova più tardi. 🙏",
            'pt': "Número máximo de tentativas atingido, ainda estou com problemas. Por favor, tente novamente mais tarde. 🙏",
            'ru': "Достигнуто максимальное количество повторных попыток, все еще есть проблемы. Пожалуйста, попробуйте еще раз позже. 🙏",
            'ja': "最大再試行回数に達しましたが、まだ問題が発生しています。後でもう一度試してください。🙏",
            'ko': "최대 재시도 횟수에 도달했지만 여전히 문제가 있습니다. 나중에 다시 시도해 주세요. 🙏",
            'zh': "已达到最大重试次数，仍然有问题。请稍后重试。🙏"
        }
    }
    return messages[error_type].get(lang, messages[error_type]['en'])

# --- Message splitting function (no change) ---
async def split_and_send_message(update: Update, text: str, max_length: int = 4096):
    if not text:
        await update.message.reply_text("Üzgünüm, bir yanıt oluşturamadım. Lütfen tekrar deneyin. 🙏")
        return

    messages = []
    current_message = ""
    lines = text.split('\n')

    for line in lines:
        if not line:
            continue
        if len(current_message + line + '\n') > max_length:
            if current_message.strip():
                messages.append(current_message.strip())
            current_message = line + '\n'
        else:
            current_message += line + '\n'

    if current_message.strip():
        messages.append(current_message.strip())

    if not messages:
        await update.message.reply_text("Üzgünüm, bir yanıt oluşturamadım. Lütfen tekrar deneyin. 🙏")
        return

    for message in messages:
        if message.strip():
            await update.message.reply_text(message)

# --- Start command handler (no change) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = "Havvusuu! Ben Nyxie, Waffieu'nun ultra complex Protogen furry fox'u! 🦊✨ Sohbet etmeye, yardım etmeye ve seninle birlikte öğrenmeye bayılıyorum! UwU! İstediğin her şeyi konuşabiliriz veya bana resimler, videolar gönderebilirsin! Dilini otomatik olarak algılayıp ona göre cevap vereceğim! 🎉🎊\n\nDerinlemesine arama yapmak için /derinarama <sorgu> komutunu kullanabilirsin! 🚀🔍\n\nEmoji kullanımını ayarlamak için:\n/emoji_auto, /emoji_high, /emoji_low, /emoji_none komutlarını kullanabilirsin!"
    await update.message.reply_text(welcome_message)

# --- Intelligent web search function (slightly enhanced result processing) ---
async def intelligent_web_search(user_message, model, user_id, iteration=0):
    try:
        logging.info(f"Web search başlatıldı (Iteration {iteration}): {user_message}, User ID: {user_id}")

        context_messages = user_memory.get_user_settings(user_id).get("messages", [])
        history_text = "\n".join([
            f"{'Kullanıcı' if msg['role'] == 'user' else 'Asistan'}: {msg['content']}"
            for msg in context_messages[-5:]
        ])

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
        dusunce_logger.info(f"Sorgu Oluşturma Promptu (Iteration {iteration}):\n{query_generation_prompt}", extra={'user_id': user_id})

        try:
            query_response = await asyncio.wait_for(
                model.generate_content_async(query_generation_prompt),
                timeout=10.0
            )
            dusunce_logger.info(f"Sorgu Oluşturma Cevabı (Gemini, Iteration {iteration}): {query_response.text}", extra={'user_id': user_id})
            logging.info(f"Gemini response received for queries (Iteration {iteration}): {query_response.text}")
        except asyncio.TimeoutError:
            logging.error(f"Gemini API request timed out (Query generation, Iteration {iteration})")
            return "Üzgünüm, şu anda arama yapamıyorum. Lütfen daha sonra tekrar deneyin.", []
        except Exception as e:
            logging.error(f"Error generating search queries (Iteration {iteration}): {str(e)}")
            return "Arama sorgularını oluştururken bir hata oluştu.", []

        search_queries = [q.strip() for q in query_response.text.split('\n') if q.strip()]
        dusunce_logger.info(f"Oluşturulan Sorgular (Iteration {iteration}): {search_queries}", extra={'user_id': user_id})

        if not search_queries:
            search_queries = [user_message]

        logging.info(f"Generated search queries (Iteration {iteration}): {search_queries}")

        async def perform_single_search(query):
            search_results_for_query = []
            try:
                with DDGS() as ddgs:
                    logging.info(f"DuckDuckGo araması yapılıyor (Iteration {iteration}): {query}")
                    dusunce_logger.info(f"DuckDuckGo Sorgusu (Iteration {iteration}): {query}", extra={'user_id': user_id})
                    results = list(ddgs.text(query, max_results=BOT_CONFIG["search_results_per_query"])) # Configurable result count
                    logging.info(f"Bulunan sonuç sayısı (Iteration {iteration}): {len(results)}")
                    dusunce_logger.info(f"DuckDuckGo Sonuç Sayısı (Iteration {iteration}): {len(results)}", extra={'user_id': user_id})
                    search_results_for_query.extend(results)
            except ImportError:
                logging.error("DuckDuckGo search modülü bulunamadı.")
                return []
            except Exception as search_error: # Fallback search remains the same
                logging.error(f"DuckDuckGo arama hatası (Iteration {iteration}): {str(search_error)}", exc_info=True)
                dusunce_logger.error(f"DuckDuckGo Arama Hatası (Iteration {iteration}): {str(search_error)}", exc_info=True, extra={'user_id': user_id})
                try:
                    def fallback_search(query):
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        search_url = f"https://www.google.com/search?q={query}"
                        response = requests.get(search_url, headers=headers)
                        dusunce_logger.info(f"Fallback Arama Sorgusu (Iteration {iteration}): {query}", extra={'user_id': user_id})

                        if response.status_code == 200:
                            soup = BeautifulSoup(response.text, 'html.parser')
                            search_results_fallback = soup.find_all('div', class_='g')
                            parsed_results = []
                            for result in search_results_fallback[:BOT_CONFIG["search_results_per_query"]]: # Configurable result count
                                title = result.find('h3')
                                link = result.find('a')
                                snippet = result.find('div', class_='VwiC3b')

                                if title and link and snippet:
                                    parsed_results.append({
                                        'title': title.text,
                                        'link': link['href'],
                                        'body': snippet.text
                                    })
                            dusunce_logger.info(f"Fallback Arama Sonuç Sayısı (Iteration {iteration}): {len(parsed_results)}", extra={'user_id': user_id})
                            return parsed_results
                        return []
                    results = fallback_search(query)
                    search_results_for_query.extend(results)
                    logging.info(f"Fallback arama sonuç sayısı (Iteration {iteration}): {len(search_results_for_query)}")
                except Exception as fallback_error:
                    logging.error(f"Fallback arama hatası (Iteration {iteration}): {str(fallback_error)}")
                    dusunce_logger.error(f"Fallback Arama Hatası (Iteration {iteration}): {str(fallback_error)}", extra={'user_id': user_id})
                    return []
            return search_results_for_query

        search_tasks = [perform_single_search(query) for query in search_queries]
        all_results_nested = await asyncio.gather(*search_tasks)

        search_results = []
        for results_list in all_results_nested:
            search_results.extend(results_list)

        logging.info(f"Toplam bulunan arama sonuç sayısı (Iteration {iteration}): {len(search_results)}")
        dusunce_logger.info(f"Toplam Arama Sonuç Sayısı (Iteration {iteration}): {len(search_results)}", extra={'user_id': user_id})

        if not search_results:
            return "Arama sonucu bulunamadı. Lütfen farklı bir şekilde sormayı deneyin.", []

        # Basic result ranking - prioritize results with query keywords in title
        ranked_results = sorted(search_results, key=lambda res: sum(1 for word in user_message.lower().split() if word in res.get('title', '').lower()), reverse=True)

        search_context = "\n\n".join([ # Using ranked results now
            f"Arama Sonucu {i+1}: {result.get('body', 'İçerik yok')}\nKaynak: {result.get('link', 'Bağlantı yok')}"
            for i, result in enumerate(ranked_results)
        ])
        dusunce_logger.info(f"Arama Bağlamı (Iteration {iteration}):\n{search_context}", extra={'user_id': user_id})

        return search_context, ranked_results # Return ranked results

    except Exception as e:
        logging.error(f"Web arama genel hatası (Iteration {iteration}): {str(e)}", exc_info=True)
        dusunce_logger.error(f"Web Arama Genel Hatası (Iteration {iteration}): {str(e)}", exc_info=True, extra={'user_id': user_id})
        return f"Web arama hatası: {str(e)}", []

# --- Perform deep search function (enhanced with ranked results and iteration limit from config) ---
async def perform_deep_search(update: Update, context: ContextTypes.DEFAULT_TYPE, user_message):
    user_id = str(update.effective_user.id)
    user_lang = user_memory.get_user_settings(user_id).get('language', BOT_CONFIG["default_language"]) # Use default from config

    MAX_ITERATIONS = BOT_CONFIG["deep_search_iterations"] # Iteration limit from config
    all_search_results = []
    current_query = user_message
    search_model = genai.GenerativeModel(BOT_CONFIG["gemini_model_name"]) # Use configured model name

    try:
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)

        for iteration in range(MAX_ITERATIONS):
            search_context, search_results = await intelligent_web_search(current_query, search_model, user_id, iteration + 1) # Pass model
            if not search_results:
                await update.message.reply_text("Derinlemesine arama yapıldı ama OwO, anlamlı bir şey bulamadım... Belki sorgumu kontrol etmelisin? 🤔 Ya da sonra tekrar deneyebilirsin! 🥺")
                return

            all_search_results.extend(search_results) # Extend with ranked results

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
            dusunce_logger.info(f"Sorgu İyileştirme Promptu (Iteration {iteration + 1}):\n{analysis_prompt}", extra={'user_id': user_id})

            try:
                query_refinement_response = await search_model.generate_content_async(analysis_prompt) # Use search model
                dusunce_logger.info(f"Sorgu İyileştirme Cevabı (Gemini, Iteration {iteration + 1}): {query_refinement_response.text}", extra={'user_id': user_id})

                refined_queries = [q.strip() for q in query_refinement_response.text.split('\n') if q.strip()][:3]
                if refined_queries:
                    current_query = " ".join(refined_queries)
                    logging.info(f"Refined queries for iteration {iteration + 2}: {refined_queries}")
                    dusunce_logger.info(f"İyileştirilmiş Sorgular (Iteration {iteration + 2}): {refined_queries}", extra={'user_id': user_id})
                else:
                    logging.info(f"No refined queries generated in iteration {iteration + 1}, stopping deep search.")
                    dusunce_logger.info(f"İyileştirilmiş Sorgu Oluşturulamadı (Iteration {iteration + 1}), derin arama durduruluyor.", extra={'user_id': user_id})
                    break
            except Exception as refine_error:
                logging.error(f"Error during query refinement (Iteration {iteration + 1}): {refine_error}")
                dusunce_logger.error(f"Sorgu İyileştirme Hatası (Iteration {iteration + 1}): {refine_error}", extra={'user_id': user_id})
                logging.info("Stopping deep search due to query refinement error.")
                dusunce_logger.info("Sorgu iyileştirme hatası nedeniyle derin arama durduruluyor.", extra={'user_id': user_id})
                break

        if all_search_results:
            final_prompt = f"""
            Görevin: Derinlemesine web araması sonuçlarını kullanarak kullanıcıya kapsamlı ve bilgilendirici bir cevap oluşturmak.
            Bu görevi bir düşünce zinciri (chain of thoughts) yaklaşımıyla, adım adım düşünerek gerçekleştir.

            Kullanıcı Sorgusu: "{user_message}"
            Tüm Arama Sonuçları:
            {''.join([f'Iteration {i+1} Results:\n' + '\\n'.join([f"Arama Sonucu {j+1}: {res.get('body', 'İçerik yok')}\\nKaynak: {res.get('link', 'Bağlantı yok')}" for j, res in enumerate(all_search_results[i*BOT_CONFIG["search_results_per_query"]:(i+1)*BOT_CONFIG["search_results_per_query"]])]) + '\\n\\n' for i in range(MAX_ITERATIONS)])}

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
            dusunce_logger.info(f"Final Chain of Thoughts Promptu:\n{final_prompt}", extra={'user_id': user_id})

            try:
                final_cot_response = await search_model.generate_content_async(final_prompt) # Use search model
                dusunce_logger.info(f"Final Chain of Thoughts Cevap (Gemini): {final_cot_response.text}", extra={'user_id': user_id})

                clean_final_prompt = f"""
                Görevin: Aşağıdaki düşünce zincirini (chain of thoughts) kullanarak kullanıcıya verilecek net ve kapsamlı bir yanıt oluşturmak.
                Düşünce sürecini ASLA dahil etme, sadece final cevabı ver.

                Kullanıcı Sorgusu: {user_message}

                Düşünce Zinciri:
                {final_cot_response.text}

                Yanıtını {user_lang} dilinde ver ve sadece net ve kapsamlı cevabı oluştur:
                """

                dusunce_logger.info(f"Temiz Final Yanıt Promptu:\n{clean_final_prompt}", extra={'user_id': user_id})
                final_response = await search_model.generate_content_async(clean_final_prompt) # Use search model
                dusunce_logger.info(f"Final Temiz Cevap (Gemini): {final_response.text}", extra={'user_id': user_id})

                if final_response.prompt_feedback and final_response.prompt_feedback.block_reason:
                    block_reason = final_response.prompt_feedback.block_reason
                    logger.warning(f"Deep search final response blocked. Reason: {block_reason}")
                    dusunce_logger.warning(f"Derin arama final cevabı engellendi. Sebep: {block_reason}", extra={'user_id': user_id})
                    error_message = get_error_message('blocked_prompt', user_lang)
                    await update.message.reply_text(error_message)
                else:
                    response_text = final_response.text if hasattr(final_response, 'text') else final_response.candidates[0].content.parts[0].text
                    response_text = await add_emojis_to_text(response_text, user_id)
                    await split_and_send_message(update, response_text)

                    user_memory.add_message(user_id, "user", f"/derinarama {user_message}")
                    user_memory.add_message(user_id, "assistant", response_text)

            except Exception as final_response_error:
                logging.error(f"Error generating final response for deep search: {final_response_error}")
                dusunce_logger.error(f"Final Cevap Oluşturma Hatası (Derin Arama): {final_response_error}", extra={'user_id': user_id})
                await update.message.reply_text(get_error_message('ai_error', user_lang))
        else:
            await update.message.reply_text("Derinlemesine arama yapıldı ama OwO, anlamlı bir şey bulamadım... Belki sorgumu kontrol etmelisin? 🤔 Ya da sonra tekrar deneyebilirsin! 🥺")

    except Exception as deep_search_error:
        logging.error(f"Error during deep search process: {deep_search_error}", exc_info=True)
        dusunce_logger.error(f"Derin Arama Süreci Hatası: {deep_search_error}", exc_info=True, extra={'user_id': user_id})
        await update.message.reply_text(get_error_message('general', user_lang))
    finally:
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)

# --- Command handlers for emoji preferences (no change) ---
async def set_emoji_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_memory.update_user_settings(user_id, {'preferences': {'emoji_preference': 'auto'}})
    await update.message.reply_text("Emoji kullanımı otomatik moda ayarlandı. Bot, mesajlarına göre emojileri ayarlayacak. 🤖")

async def set_emoji_high(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_memory.update_user_settings(user_id, {'preferences': {'emoji_preference': 'high'}})
    await update.message.reply_text("Emoji kullanımı yüksek moda ayarlandı. Bot, mesajlarında daha çok emoji kullanacak. 🎉")

async def set_emoji_low(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_memory.update_user_settings(user_id, {'preferences': {'emoji_preference': 'low'}})
    await update.message.reply_text("Emoji kullanımı düşük moda ayarlandı. Bot, mesajlarında daha az emoji kullanacak. 🤏")

async def set_emoji_none(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_memory.update_user_settings(user_id, {'preferences': {'emoji_preference': 'none'}})
    await update.message.reply_text("Emoji kullanımı kapalı moda ayarlandı. Bot, mesajlarında emoji kullanmayacak. 🚫")

# --- Handle message function (typing indicator delay from config) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    dusunce_logger.info("Mesaj işleme fonksiyonuna girildi.", extra={'user_id': user_id})

    try:
        if not update or not update.message:
            logger.error("Invalid update object or message")
            dusunce_logger.error("Geçersiz update veya mesaj objesi.", extra={'user_id': user_id})
            return

        logger.info(f"Message received: {update.message}")
        logger.info(f"Message text: {update.message.text}")
        dusunce_logger.info(f"Mesaj alındı: {update.message}", extra={'user_id': user_id})
        dusunce_logger.info(f"Mesaj metni: {update.message.text}", extra={'user_id': user_id})

        if update.message.text and not update.message.text.startswith('/'):
            message_text = update.message.text.strip()
            user_lang = await detect_and_set_user_language(message_text, user_id)
            logger.info(f"Detected language: {user_lang}")
            dusunce_logger.info(f"Tespit edilen dil: {user_lang}", extra={'user_id': user_id})
        else:
            user_lang = user_memory.get_user_settings(user_id).get('language', BOT_CONFIG["default_language"]) # Use default from config

        if update.message.text and update.message.text.startswith('/derinarama'):
            query = update.message.text[len('/derinarama'):].strip()
            if not query:
                await update.message.reply_text("Derin arama için bir sorgu girmelisin! 🥺 Örnek: `/derinarama Türkiye'deki antik kentler`")
                return
            await perform_deep_search(update, context, query)
            return
        if update.message.text and update.message.text.startswith('/emoji_'): # Emoji commands
            return # Emoji commands are handled by their respective handlers

        if update.message.text and not update.message.text.startswith('/'):
            message_text = update.message.text.strip()
            logger.info(f"Processed message text: {message_text}")
            dusunce_logger.info(f"İşlenen mesaj metni: {message_text}", extra={'user_id': user_id})

            async def show_typing():
                while True:
                    try:
                        await context.bot.send_chat_action(
                            chat_id=update.message.chat_id,
                            action=ChatAction.TYPING
                        )
                        await asyncio.sleep(BOT_CONFIG["typing_indicator_delay"]) # Typing indicator delay from config
                    except Exception as e:
                        logger.error(f"Error in typing indicator: {e}")
                        dusunce_logger.error(f"Yazıyor göstergesi hatası: {e}", extra={'user_id': user_id})
                        break

            typing_task = asyncio.create_task(show_typing())

            try:
                MAX_RETRIES = 3 # Reduced retries, token limit error handling improved
                retry_count = 0
                context_messages = []

                while retry_count < MAX_RETRIES:
                    try:
                        context_messages = user_memory.get_relevant_context(user_id)
                        user_settings = user_memory.get_user_settings(user_id)
                        personality_profile = user_settings.get('personality_profile')

                        personality_context = get_time_aware_personality(
                            datetime.now(),
                            user_lang,
                            user_settings.get('preferences', {}).get('timezone', 'Europe/Istanbul'), # Safe access
                            personality_profile
                        )

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
                        dusunce_logger.info(f"AI Prompt (Chain of Thoughts):\n{ai_prompt}", extra={'user_id': user_id})

                        try:
                            ai_model = genai.GenerativeModel(BOT_CONFIG["gemini_model_name"]) # Use configured model name
                            web_search_response, _ = await intelligent_web_search(message_text, ai_model, user_id) # Pass model

                            if web_search_response and len(web_search_response.strip()) > 10:
                                ai_prompt += f"\n\nEk Bilgi (Web Arama Sonuçları - SADECE DİREKT SONUÇLARI KULLAN):\n{web_search_response}"
                                dusunce_logger.info(f"AI Prompt (Web Aramalı):\n{ai_prompt}", extra={'user_id': user_id})

                            dusunce_logger.info("Gemini'den chain of thoughts cevabı bekleniyor... 💫", extra={'user_id': user_id})
                            response = await asyncio.wait_for(ai_model.generate_content_async( # Use ai_model and timeout
                                ai_prompt,
                                generation_config={
                                    "temperature": 0.7,
                                    "top_p": 0.8,
                                    "top_k": 40
                                }
                            ), timeout=30.0) # Added timeout to Gemini response

                            dusunce_logger.info(f"Gemini Chain of Thoughts Cevabı: {response.text}", extra={'user_id': user_id})

                            if response.prompt_feedback and response.prompt_feedback.block_reason:
                                block_reason = response.prompt_feedback.block_reason
                                logger.warning(f"Prompt blocked for regular message. Reason: {block_reason}")
                                dusunce_logger.warning(f"Normal mesaj için prompt engellendi. Sebep: {block_reason}", extra={'user_id': user_id})
                                error_message = get_error_message('blocked_prompt', user_lang)
                                await update.message.reply_text(error_message)
                                break
                            else:
                                full_response = response.text if hasattr(response, 'text') else response.candidates[0].content.parts[0].text
                                dusunce_logger.info(f"Tam Chain of Thoughts yanıtı: {full_response}", extra={'user_id': user_id})

                                clean_response_prompt = f"""${personality_context}

                                Görevin: Aşağıdaki düşünce zincirini (chain of thoughts) kullanarak kullanıcıya verilecek NET ve SADE bir yanıt oluşturmak! Ama düşünce sürecini SAKIN dahil etme! 🙅‍♀️ Sadece final cevabı ver! 😉

                                Düşünce Zinciri:
                                {full_response}

                                Kullanıcı Mesajı: {message_text}

                                Sadece net ve sade cevabı ver:"""

                                dusunce_logger.info(f"Temiz yanıt promptu: {clean_response_prompt}", extra={'user_id': user_id})
                                clean_response = await ai_model.generate_content_async(clean_response_prompt) # Use ai_model
                                response_text = clean_response.text if hasattr(clean_response, 'text') else clean_response.candidates[0].content.parts[0].text
                                dusunce_logger.info(f"Temiz yanıt: {response_text}", extra={'user_id': user_id})

                                response_text = await add_emojis_to_text(response_text, user_id)
                                await split_and_send_message(update, response_text.strip())

                                user_memory.add_message(user_id, "user", message_text)
                                user_memory.add_message(user_id, "assistant", response_text)
                                break # Success, break retry loop

                        except asyncio.TimeoutError: # Handle Gemini API timeout
                            logger.warning("Gemini API timed out during message processing.")
                            dusunce_logger.warning("Gemini API mesaj işleme sırasında zaman aşımına uğradı.", extra={'user_id': user_id})
                            error_message = get_error_message('ai_error', user_lang) # Or a more specific timeout error message
                            await update.message.reply_text(error_message)
                            break # Break retry loop after timeout

                        except Exception as search_error: # Token limit handling - improved
                            if "Token limit exceeded" in str(search_error):
                                user_memory.trim_context(user_id) # Trim context directly using DB aware function
                                retry_count += 1
                                logger.warning(f"Token limit exceeded, retrying {retry_count}/{MAX_RETRIES}")
                                dusunce_logger.warning(f"Token limiti aşıldı, tekrar deneniyor {retry_count}/{MAX_RETRIES}", extra={'user_id': user_id})

                                if retry_count % 1 == 0: # Less frequent token limit messages
                                    await update.message.reply_text(f"🔄 Ay ay ay! Konuşma çok uzun! Biraz hafızayı temizliyorum... ({retry_count}. deneme) 🥺")

                                if retry_count == MAX_RETRIES: # Max retries reached for token limit
                                    error_message = get_error_message('token_limit', user_lang)
                                    await update.message.reply_text(error_message)
                                    break # Break retry loop after max token retries
                            else:
                                raise search_error # Re-raise other errors

                    except Exception as context_error: # Context retrieval error handling
                        logger.error(f"Context retrieval error: {context_error}")
                        dusunce_logger.error(f"Kontekst alma hatası: {context_error}", extra={'user_id': user_id})
                        retry_count += 1
                        if retry_count == MAX_RETRIES: # Max retries reached for context error
                            error_message = get_error_message('general', user_lang)
                            await update.message.reply_text(error_message)
                            break # Break retry loop after max context retries

                if retry_count == MAX_RETRIES: # Max retries reached overall
                    logger.error("Max retries reached for message processing.")
                    dusunce_logger.error("Mesaj işleme için maksimum deneme sayısına ulaşıldı.", extra={'user_id': user_id})
                    error_message = get_error_message('max_retries', user_lang)
                    await update.message.reply_text(error_message)

            except Exception as e: # General message processing error handling
                logger.error(f"Message processing error: {e}")
                dusunce_logger.error(f"Mesaj işleme hatası: {e}", extra={'user_id': user_id})
                error_message = get_error_message('general', user_lang)
                await update.message.reply_text(error_message)

            finally:
                typing_task.cancel() # Cancel typing task in finally block

        elif update.message.photo: # Image and video handlers remain the same
            await handle_image(update, context)
        elif update.message.video:
            await handle_video(update, context)
        else: # Unhandled message type
            logger.warning("Unhandled message type received")
            dusunce_logger.warning("İşlenemeyen mesaj türü alındı.", extra={'user_id': user_id})
            user_lang = user_memory.get_user_settings(user_id).get('language', BOT_CONFIG["default_language"]) # Use default from config
            unhandled_message = get_error_message('unhandled', user_lang)
            await update.message.reply_text(unhandled_message)

    except Exception as e: # General error handling for handle_message
        logger.error(f"General error in handle_message: {e}")
        dusunce_logger.error(f"Genel hata handle_message içinde: {e}", extra={'user_id': user_id})
        user_lang = user_memory.get_user_settings(user_id).get('language', BOT_CONFIG["default_language"]) # Use default from config
        error_message = get_error_message('general', user_lang)
        await update.message.reply_text(error_message)
    except SyntaxError as e: # Syntax error handling
        logger.error(f"Syntax error in handle_message: {e}")
        dusunce_logger.error(f"Syntax error handle_message içinde: {e}", extra={'user_id': user_id})
        user_lang = user_memory.get_user_settings(user_id).get('language', BOT_CONFIG["default_language"]) # Use default from config
        error_message = get_error_message('general', user_lang)
        await update.message.reply_text(error_message)

# --- Image and Video handlers (same as before, model name from config) ---
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    try:
        logger.info(f"Starting image processing for user {user_id}")
        dusunce_logger.info(f"Resim işleme başlatılıyor. Kullanıcı ID: {user_id}", extra={'user_id': user_id})

        if not update.message:
            logger.warning("No message found in update")
            await update.message.reply_text("A-aa! Mesaj kayıp! 🥺 Lütfen tekrar dener misin?")
            dusunce_logger.warning("Update içinde mesaj bulunamadı.", extra={'user_id': user_id})
            return

        user_settings = user_memory.get_user_settings(user_id)
        user_lang = user_settings.get('language', BOT_CONFIG["default_language"]) # Use default from config
        logger.info(f"User language: {user_lang}")
        dusunce_logger.info(f"Kullanıcı dili: {user_lang}", extra={'user_id': user_id})

        if not update.message.photo:
            logger.warning("No photo found in the message")
            await update.message.reply_text("Resim de kayıp! 😭 Tekrar gönderebilir misin lütfen?")
            dusunce_logger.warning("Mesajda fotoğraf bulunamadı.", extra={'user_id': user_id})
            return

        try:
            photo = max(update.message.photo, key=lambda x: x.file_size)
        except Exception as photo_error:
            logger.error(f"Error selecting photo: {photo_error}")
            await update.message.reply_text("Resmi seçerken bir sorun oldu! 🤯 Belki tekrar denemelisin?")
            dusunce_logger.error(f"Fotoğraf seçimi hatası: {photo_error}", extra={'user_id': user_id})
            return

        try:
            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = bytes(await photo_file.download_as_bytearray())
        except Exception as download_error:
            logger.error(f"Photo download error: {download_error}")
            await update.message.reply_text("Resmi indiremedim! 🥺 İnternet bağlantını kontrol eder misin?")
            dusunce_logger.error(f"Fotoğraf indirme hatası: {download_error}", extra={'user_id': user_id})
            return

        logger.info(f"Photo bytes downloaded: {len(photo_bytes)} bytes")
        dusunce_logger.info(f"Fotoğraf indirildi. Boyut: {len(photo_bytes)} bytes", extra={'user_id': user_id})

        caption = update.message.caption
        logger.info(f"Original caption: {caption}")
        dusunce_logger.info(f"Orijinal başlık: {caption}", extra={'user_id': user_id})

        default_prompt = get_analysis_prompt('image', None, user_lang)
        logger.info(f"Default prompt: {default_prompt}")
        dusunce_logger.info(f"Varsayılan prompt: {default_prompt}", extra={'user_id': user_id})

        if caption is None:
            caption = default_prompt or "Bu resmi detaylı bir şekilde analiz et ve açıkla."

        caption = str(caption).strip()
        logger.info(f"Final processed caption: {caption}")
        dusunce_logger.info(f"Son işlenmiş başlık: {caption}", extra={'user_id': user_id})

        personality_context = get_time_aware_personality(
            datetime.now(),
            user_lang,
            user_settings.get('preferences', {}).get('timezone', 'Europe/Istanbul'), # Safe access
            user_settings.get('personality_profile')
        )

        if not personality_context:
            personality_context = "Sen Nyxie'sin ve resimleri analiz ediyorsun."

        analysis_prompt = f"""DİKKAT: BU ANALİZİ TÜRKÇE YAPACAKSIN! SADECE TÜRKÇE KULLAN! KESİNLİKLE BAŞKA DİL KULLANMA!

        {personality_context}

        Görevin: Kullanıcının gönderdiği görseli analiz ederek sadece düz metin bir açıklama sunmak.
        Rol: Sen Nyxie'sin ve bu görseli Türkçe olarak açıklıyorsun.

        Yönergeler:

        SADECE TÜRKÇE KULLAN! 🇹🇷💯

        Görseldeki metinleri (varsa) orijinal dilinde bırak, çevirme! 🚫✍️

        Analizini yaparken NAZİK ve YARDIMSEVER bir ton kullan! 🥰💖

        Kültürel DUYARLILIĞA dikkat et! 🌍🕊️
        5. Sadece düz metin cevap ver. JSON veya başka format kullanma. 🚫📦

        Lütfen analiz et ve sadece düz metin olarak özetle:

        Görseldeki ANA ÖĞELERİ ve KONULARI tanımla! 🔍👀

        Aktiviteler veya OLAYLAR varsa, bunları açıkla! 🏞️🎉

        Görselin GENEL ATMOSFERİNİ ve olası DUYGUSAL ETKİSİNİ değerlendir! 😌🤔

        Görselde METİN varsa, bunları belirt (çevirme yapma)! 📝📢

        Kullanıcının isteği (varsa): {caption}"""
        dusunce_logger.info(f"Resim Analiz Promptu:\n{analysis_prompt}", extra={'user_id': user_id})

        try:
            image_model = genai.GenerativeModel(BOT_CONFIG["gemini_model_name"]) # Use configured model name
            dusunce_logger.info(f"Gemini'ye resim analizi isteği gönderiliyor... 🚀🌌", extra={'user_id': user_id})
            response = await asyncio.wait_for(image_model.generate_content_async( # Use image_model and timeout
                [analysis_prompt, {"mime_type": "image/jpeg", "data": photo_bytes}],
                timeout=60.0 # Added timeout for image analysis
            ), timeout=60.0)

            dusunce_logger.info(f"Resim Analizi Cevabı (Gemini): {response.text}", extra={'user_id': user_id})

            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason
                logger.warning(f"Prompt blocked for image analysis. Reason: {block_reason}")
                dusunce_logger.warning(f"Resim analizi için prompt engellendi. Sebep: {block_reason}", extra={'user_id': user_id})
                error_message = get_error_message('blocked_prompt', user_lang)
                await update.message.reply_text(error_message)
            else:
                response_text = response.text if hasattr(response, 'text') else response.candidates[0].content.parts[0].text
                response_text = await add_emojis_to_text(response_text, user_id)
                user_memory.add_message(user_id, "user", f"[Image] {caption}")
                user_memory.add_message(user_id, "assistant", response_text)
                await split_and_send_message(update, response_text.strip())

        except asyncio.TimeoutError: # Handle timeout for image analysis
            logger.warning("Gemini API timed out during image analysis.")
            dusunce_logger.warning("Gemini API resim analizi sırasında zaman aşımına uğradı.", extra={'user_id': user_id})
            error_message = get_error_message('ai_error', user_lang) # Or a more specific timeout error
            await update.message.reply_text(error_message)

        except Exception as processing_error: # Image processing error handling
            logger.error(f"Görsel işleme hatası: {processing_error}", exc_info=True)
            dusunce_logger.error(f"Görsel işleme hatası: {processing_error}", exc_info=True, extra={'user_id': user_id})
            error_message = get_error_message('ai_error', user_lang)
            await update.message.reply_text(error_message)

    except Exception as critical_error: # Critical image processing error handling
        logger.error(f"Kritik görsel işleme hatası: {critical_error}", exc_info=True)
        dusunce_logger.error(f"Kritik görsel işleme hatası: {critical_error}", exc_info=True, extra={'user_id': user_id})
        await update.message.reply_text(get_error_message('general', user_lang))

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE): # Video handler - similar to image, model name from config, timeouts added
    user_id = str(update.effective_user.id)

    try:
        logger.info(f"Starting video processing for user {user_id}")
        dusunce_logger.info(f"Video işleme başlatılıyor. Kullanıcı ID: {user_id}", extra={'user_id': user_id})

        if not update.message:
            logger.warning("No message found in update")
            await update.message.reply_text("A-aa! Mesaj kayıp! 🥺 Lütfen tekrar dener misin?")
            dusunce_logger.warning("Update içinde mesaj bulunamadı.", extra={'user_id': user_id})
            return

        user_settings = user_memory.get_user_settings(user_id)
        user_lang = user_settings.get('language', BOT_CONFIG["default_language"]) # Use default from config
        logger.info(f"User language: {user_lang}")
        dusunce_logger.info(f"Kullanıcı dili: {user_lang}", extra={'user_id': user_id})

        if not update.message.video:
            logger.warning("No video found in the message")
            await update.message.reply_text("Video da kayıp! 😭 Tekrar gönderebilir misin lütfen?")
            dusunce_logger.warning("Mesajda video bulunamadı.", extra={'user_id': user_id})
            return

        video = update.message.video
        if not video:
            logger.warning("No video found in the message")
            await update.message.reply_text("Video da kayıp! 😭 Tekrar gönderebilir misin lütfen?")
            dusunce_logger.warning("Mesajda video objesi bulunamadı.", extra={'user_id': user_id})
            return

        video_file = await context.bot.get_file(video.file_id)
        video_bytes = bytes(await video_file.download_as_bytearray())
        logger.info(f"Video bytes downloaded: {len(video_bytes)} bytes")
        dusunce_logger.info(f"Video indirildi. Boyut: {len(video_bytes)} bytes", extra={'user_id': user_id})

        caption = update.message.caption
        logger.info(f"Original caption: {caption}")
        dusunce_logger.info(f"Orijinal başlık: {caption}", extra={'user_id': user_id})

        default_prompt = get_analysis_prompt('video', None, user_lang)
        logger.info(f"Default prompt: {default_prompt}")
        dusunce_logger.info(f"Varsayılan prompt: {default_prompt}", extra={'user_id': user_id})

        if caption is None:
            caption = default_prompt or "Bu videoyu detaylı bir şekilde analiz et ve açıkla."

        caption = str(caption).strip()
        logger.info(f"Final processed caption: {caption}")
        dusunce_logger.info(f"Son işlenmiş başlık: {caption}", extra={'user_id': user_id})

        personality_context = get_time_aware_personality(
            datetime.now(),
            user_lang,
            user_settings.get('preferences', {}).get('timezone', 'Europe/Istanbul'), # Safe access
            user_settings.get('personality_profile')
        )

        if not personality_context:
            personality_context = "Sen Nyxie'sin ve videoları analiz ediyorsun."

        analysis_prompt = f"""DİKKAT: BU ANALİZİ TÜRKÇE YAPACAKSIN! SADECE TÜRKÇE KULLAN! KESİNLİKLE BAŞKA DİL KULLANMA!

        {personality_context}

        Görevin: Kullanıcının gönderdiği videoyu analiz ederek sadece düz metin bir açıklama sunmak.
        Rol: Sen Nyxie'sin ve bu videoyu Türkçe olarak açıklıyorsun.

        Yönergeler:

        SADECE TÜRKÇE KULLAN! 🇹🇷💯

        Videodaki konuşma veya metinleri (varsa) orijinal dilinde bırak, çevirme! 🚫✍️

        Analizini yaparken NAZİK ve YARDIMSEVER bir ton kullan! 🥰💖

        Kültürel DUYARLILIĞA dikkat et! 🌍🕊️
        5. Sadece düz metin cevap ver. JSON veya başka format kullanma. 🚫📦

        Lütfen analiz et ve sadece düz metin olarak özetle:

        Videodaki ANA OLAYLARI ve EYLEMLERİ tanımla! 🔍🎬

        Önemli İNSANLAR veya NESNELER varsa, bunları belirt! 🧑‍🤝‍🧑📦

        Videodaki SESLERİ ve KONUŞMALARI (varsa) analiz et! 🎧🗣️

        Videonun GENEL ATMOSFERİNİ ve olası DUYGUSAL ETKİSİNİ değerlendir! 😌🤔

        Videoda METİN varsa, bunları belirt (çevirme yapma)! 📝📢

        Kullanıcının isteği (varsa): {caption}"""
        dusunce_logger.info(f"Video Analiz Promptu:\n{analysis_prompt}", extra={'user_id': user_id})

        try:
            video_model = genai.GenerativeModel(BOT_CONFIG["gemini_model_name"]) # Use configured model name
            dusunce_logger.info(f"Gemini'ye video analizi isteği gönderiliyor... 🚀🌌", extra={'user_id': user_id})
            response = await asyncio.wait_for(video_model.generate_content_async( # Use video_model and timeout
                [analysis_prompt, {"mime_type": "video/mp4", "data": video_bytes}],
                timeout=90.0 # Added timeout for video analysis, longer than image
            ), timeout=90.0)

            dusunce_logger.info(f"Video Analizi Cevabı (Gemini): {response.text}", extra={'user_id': user_id})

            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason
                logger.warning(f"Prompt blocked for video analysis. Reason: {block_reason}")
                dusunce_logger.warning(f"Video analizi için prompt engellendi. Sebep: {block_reason}", extra={'user_id': user_id})
                error_message = get_error_message('blocked_prompt', user_lang)
                await update.message.reply_text(error_message)
            else:
                response_text = response.text if hasattr(response, 'text') else response.candidates[0].content.parts[0].text
                response_text = await add_emojis_to_text(response_text, user_id)
                user_memory.add_message(user_id, "user", f"[Video] {caption}")
                user_memory.add_message(user_id, "assistant", response_text)
                await split_and_send_message(update, response_text.strip())

        except asyncio.TimeoutError: # Handle timeout for video analysis
            logger.warning("Gemini API timed out during video analysis.")
            dusunce_logger.warning("Gemini API video analizi sırasında zaman aşımına uğradı.", extra={'user_id': user_id})
            error_message = get_error_message('ai_error', user_lang) # Or more specific timeout error
            await update.message.reply_text(error_message)

        except Exception as processing_error: # Video processing error handling
            logger.error(f"Video processing error: {processing_error}", exc_info=True)
            dusunce_logger.error(f"Video işleme hatası: {processing_error}", exc_info=True, extra={'user_id': user_id})
            error_message = get_error_message('ai_error', user_lang)
            await update.message.reply_text(error_message)

    except Exception as e: # Critical video processing error handling
        logger.error(f"Kritik video işleme hatası: {e}", exc_info=True)
        dusunce_logger.error(f"Kritik video işleme hatası: {e}", exc_info=True, extra={'user_id': user_id})
        await update.message.reply_text(get_error_message('general', user_lang))

# --- Token and memory error handlers (no change) ---
async def handle_token_limit_error(update: Update):
    error_message = "Ay ay ay! Mesaj geçmişi çok uzun! 🥺 Şu an cevap veremiyorum ama biraz bekleyip tekrar dener misin? 🙏"
    await update.message.reply_text(error_message)

async def handle_memory_error(update: Update):
    error_message = "Hafızam doldu sandım bir an! 🤯 Bellek sınırına ulaşıldı galiba... Biraz bekleyip tekrar dener misin? 🙏"
    await update.message.reply_text(error_message)

# --- Emoji adding function (model name from config) ---
async def add_emojis_to_text(text, user_id):
    try:
        user_settings = user_memory.get_user_settings(user_id)
        emoji_preference = user_settings['preferences'].get('emoji_preference', 'auto')
        emoji_model = genai.GenerativeModel(BOT_CONFIG["gemini_model_name"]) # Use configured model name

        if emoji_preference == 'none':
            return text

        sentiment_analysis_prompt = f"""
        Analyze the sentiment of the following text. Is it positive, negative, or neutral?

        Text: "{text}"

        Respond with ONLY one word: "positive", "negative", or "neutral".
        """
        sentiment_response = await emoji_model.generate_content_async(sentiment_analysis_prompt)
        sentiment = sentiment_response.text.strip().lower()
        dusunce_logger.info(f"Sentiment Analysis for Emoji: '{text}' - Sentiment: {sentiment}", extra={'user_id': user_id})

        emoji_prompt = f"""
        Sen ultra complex bir Protogen furry fox'sun, Nyxie.  Aşağıdaki metni analiz et ve kişiliğine UYGUN emoji(leri) öner.

        Metin: "{text}"
        Sentiment: {sentiment}
        Emoji Preference: {emoji_preference}

        Kurallar:
        - **Emoji Sayısı:**
            - Eğer emoji_preference 'high' ise: 2-4 emoji öner.
            - Eğer emoji_preference 'low' ise: 0-2 emoji öner (çoğunlukla 1 veya 0).
            - Eğer emoji_preference 'auto' ise: 0-3 emoji öner.
            - Eğer emoji_preference 'none' ise: BOŞ DİZE döndür (zaten başta kontrol edildi ama güvenlik için burada da belirtiliyor).
        - Emojiler metnin tonuna, sentimente ve Nyxie'nin kişiliğine uygun olsun. Enerjik, oyuncu, sevecen, teknoloji meraklısı bir furry fox protogen gibi düşün.
        - Sentiment 'negative' ise, çok fazla veya aşırı neşeli emoji kullanma. Daha sakin veya ilgili emojiler seç.
        - Eğer uygun emoji yoksa, boş dize döndür.
        - SADECE emoji(leri) veya boş dize ile yanıt ver. Başka metin veya açıklama YOK.

        Yanıt formatı: Sadece emoji(ler) veya boş dize (aralarında boşluk olabilir)
        """
        dusunce_logger.info(f"Gelişmiş Emoji Promptu (Sentiment Aware):\n{emoji_prompt}", extra={'user_id': 'N/A'})

        emoji_response = await emoji_model.generate_content_async(emoji_prompt)
        dusunce_logger.info(f"Gelişmiş Emoji Cevabı (Gemini, Sentiment Aware): {emoji_response.text}", extra={'user_id': 'N/A'})

        if emoji_response.prompt_feedback and emoji_response.prompt_feedback.block_reason:
            logger.warning("Emoji suggestion blocked.")
            dusunce_logger.warning("Emoji önerisi engellendi.", extra={'user_id': 'N/A'})
            return text
        else:
            suggested_emojis_str = emoji_response.text.strip()
            if not suggested_emojis_str:
                return text
            suggested_emojis = suggested_emojis_str.split()
            return f"{text} {' '.join(suggested_emojis)}"

    except Exception as e:
        logger.error(f"Error adding context-relevant emojis: {e}")
        dusunce_logger.error(f"Emoji ekleme hatası: {e}", extra={'user_id': 'N/A'})
        return text

# --- Analysis prompt function (no change) ---
def get_analysis_prompt(media_type, caption, lang):
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

    if caption and caption.strip():
        return caption

    if media_type in prompts:
        return prompts[media_type].get(lang, prompts[media_type]['en'])

    return prompts['default'].get(lang, prompts['default']['en'])

def main():
    global user_memory
    application = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()

    application.add_handler(CommandHandler("start", start)) # Added start command
    application.add_handler(CommandHandler("derinarama", handle_message))
    application.add_handler(CommandHandler("emoji_auto", set_emoji_auto))
    application.add_handler(CommandHandler("emoji_high", set_emoji_high))
    application.add_handler(CommandHandler("emoji_low", set_emoji_low))
    application.add_handler(CommandHandler("emoji_none", set_emoji_none))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    user_memory = UserMemoryDB(BOT_CONFIG["database_file"]) # Initialize UserMemoryDB

    async def initial_personality_generation(): # No change
        for user_file in Path(BOT_CONFIG["memory_dir"]).glob('user_*.json'): # Path changed to DB dir - but glob is not used anymore with DB
            user_id_str = user_file.stem.replace('user_', '')
            user_id = int(user_id_str)
            user_data = user_memory.get_user_settings(user_id)
            if 'personality_profile' not in user_data or user_data.get('personality_profile') is None:
                dusunce_logger.info(f"Başlangıç kişilik profili oluşturma başlatıldı. Kullanıcı ID: {user_id}", extra={'user_id': user_id})
                await user_memory.generate_user_personality(user_id)
                dusunce_logger.info(f"Başlangıç kişilik profili oluşturma tamamlandı. Kullanıcı ID: {user_id}", extra={'user_id': user_id})

    # asyncio.run(initial_personality_generation()) # Removed initial personality generation at startup for DB version - personality will be generated on first message

    # Fix for Python 3.12 asyncio event loop issue (no change)
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(application.run_polling(allowed_updates=Update.ALL_TYPES))

if __name__ == '__main__':
    main()