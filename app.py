import logging
import requests
import time
import os
from bs4 import BeautifulSoup
import pdfkit
from telebot import types, telebot
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# Replace with your actual LNMU URL and path to wkhtmltopdf executable
LNMU_RESULT_URL = "https://lnmuniversity.com/LNMU_ERP/SearchResultFirstPart_22_25.aspx"
LNMU_ADMIT_CARD_URL = "https://lnmuniversity.com/UG2225/PrintAdmit_II_2225.aspx"

# Get the path to wkhtmltopdf and Telegram bot token from environment variables
WKHTMLTOPDF_PATH = os.getenv('WKHTMLTOPDF_PATH', '/usr/bin/wkhtmltopdf')
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Initialize telebot with your Telegram bot token
bot = telebot.TeleBot(TOKEN)

# Directory for temporary PDF files
HOME_DIR = '/home/ayushroyll/'
TEMP_DIR = os.path.join(HOME_DIR, 'results/lnmu/')

def cleanup_temp_files(age_in_seconds=120):
    """Clean up temporary files older than the specified age."""
    now = time.time()
    for filename in os.listdir(TEMP_DIR):
        file_path = os.path.join(TEMP_DIR, filename)
        if os.stat(file_path).st_mtime < now - age_in_seconds:
            if os.path.isfile(file_path):
                os.remove(file_path)
# Ensure the temporary directory exists
os.makedirs(TEMP_DIR, exist_ok=True)

# Handler for /start command
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, f"Hi! {message.chat.first_name}, I'm your bot from LNMU.")
    markup = types.ReplyKeyboardMarkup(row_width=1, one_time_keyboard=True, resize_keyboard=True)
    itembtn_result = types.KeyboardButton('Result(22-25)')
    itembtn_admit_card = types.KeyboardButton('Admit Card(22-25)')
    markup.add(itembtn_result, itembtn_admit_card)
    bot.send_message(message.chat.id, "Please choose an option:", reply_markup=markup)

def user_choice(chat_id):
    markup = types.ReplyKeyboardMarkup(row_width=1, one_time_keyboard=True, resize_keyboard=True)
    itembtn_result = types.KeyboardButton('Result(22-25)')
    itembtn_admit_card = types.KeyboardButton('Admit Card(22-25)')
    markup.add(itembtn_result, itembtn_admit_card)
    bot.send_message(chat_id, "Please choose an option:", reply_markup=markup)

# Handler for user's choice
@bot.message_handler(func=lambda message: message.text in ['Result(22-25)', 'Admit Card(22-25)'])
def choice(message):
    bot.send_message(message.chat.id, f"Please enter your roll number for {message.text}:")
    bot.register_next_step_handler(message, process_roll_number, message.text)

# Function to handle roll number input and generate PDF
def process_roll_number(message, choice):
    roll_number = message.text.strip()

    if choice == 'Result(22-25)':
        bot.send_message(message.chat.id, f"Wait.. Aapka Result bhej raha hu😊")
        url = LNMU_RESULT_URL
    else:
        bot.send_message(message.chat.id, "Please enter your mobile number for Admit Card:")
        bot.register_next_step_handler(message, process_mobile_number, roll_number)
        return

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses
        soup = BeautifulSoup(response.content, 'html.parser')
        viewstate = soup.find('input', {'id': '__VIEWSTATE'})['value']
        eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})['value']

        data = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': '38A17705',  # Value from the hidden field
            '__EVENTVALIDATION': eventvalidation,
            'txtRollNo': roll_number,
            'btnSearch': 'Search'
        }

        response = requests.post(url, data=data)
        response.raise_for_status()  # Raise an HTTPError for bad responses

        if "no result found" in response.text.lower():  # Example condition, adjust based on actual content
            bot.send_message(message.chat.id, "Please enter a valid Roll Number")
            user_choice(message.chat.id)
            return

        final_url = response.url
        unique_filename = f'{uuid.uuid4()}.pdf'
        pdf_output_path = os.path.join(TEMP_DIR, unique_filename)

        config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

        pdfkit.from_url(final_url, pdf_output_path, configuration=config)

        with open(pdf_output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption=f"{choice} PDF generated")

        share_markup = types.InlineKeyboardMarkup(row_width=1)
        share_btn = types.InlineKeyboardButton('Share this bot', url=f"https://api.whatsapp.com/send?text=Hey.. this is a bot which helps you download the result and admit card\n https://t.me/lnmu_result_bot")
        back_btn = types.InlineKeyboardButton('Check another', callback_data='check_another')
        share_markup.add(share_btn, back_btn)
        bot.send_message(message.chat.id, "If you are happy with this bot then share with your friends😊", reply_markup=share_markup)

        # Cleanup old files
        cleanup_temp_files()
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP error: {e}")
        bot.send_message(message.chat.id, "There was an error connecting to the server. Please try again later.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        bot.send_message(message.chat.id, "An error occurred. Please try again later.")
        user_choice(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == 'check_another')
def callback_query(call):
    bot.answer_callback_query(call.id)
    user_choice(call.message.chat.id)

# Function to handle Admit Card with mobile number
def process_mobile_number(message, roll_number):
    bot.send_message(message.chat.id, "Wait.. bhej raha hu Admit Card😊")
    mobile_number = message.text.strip()
    url = f"{LNMU_ADMIT_CARD_URL}?p1={roll_number}&p2={mobile_number}"
    unique_filename = f'AdmitCard_{roll_number}.pdf'
    pdf_output_path = os.path.join(TEMP_DIR, unique_filename)

    config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

    try:
        pdfkit.from_url(url, pdf_output_path, configuration=config)
        with open(pdf_output_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="Admit Card PDF generated.")

        share_markup = types.InlineKeyboardMarkup(row_width=1)
        share_btn = types.InlineKeyboardButton('Share this bot', url=f"https://api.whatsapp.com/send?text=Hey.. this is a bot which help you to download the result and admit card\n https://t.me/lnmu_result_bot")
        back_btn = types.InlineKeyboardButton('Check another', callback_data='check_another')
        share_markup.add(share_btn, back_btn)
        bot.send_message(message.chat.id, "If You are happy with this bot then share with your friends😊", reply_markup=share_markup)

        # Cleanup old files
        cleanup_temp_files()
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        bot.send_message(message.chat.id, "Please enter a valid Roll/Mobile number.")
        user_choice(message.chat.id)

print("bot is running..")
# Start the bot
bot.polling()
                     
