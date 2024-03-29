import os
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from dotenv import load_dotenv
from openai import OpenAI
from get_embedding import get_embd
from get_db import get_database

load_dotenv()
dbname = get_database()
collection = dbname["conv"]

PORT = int(os.environ.get('PORT', 5000))
# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')

vectore_store = get_embd()
def prompt_ai(context) :
    prompt_ai = f"""
    You role is to speak with someone who wanna learn english, by speaking, help the user to improve his speak skills. use the context delimited by double quotes to answer the user question
    Make sure to correct any spelling or writing errors made by the user and provide them with feedback.

    ""context : {context}""
    
    """
    return prompt_ai

def response(messages) :

    completion = client.chat.completions.create(
        model="gpt-4",
        temperature=0.8,
        messages=messages)

    return completion.choices[0].message.content

def TTS(msg,file_name):
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=msg,
    )

    response.stream_to_file(file_name)

    audio = open(file_name, "rb")
    return audio
def STT(bot,name_audio,file_id,chat_id) :
    file = bot.getFile(file_id)

    file.download(name_audio)

    file_path = f'voice_{chat_id}.mp3'
    audio_file = open(file_path, "rb")
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )
    return transcript.text

def start(update, context):
    """Send a message when the command /start is issued."""
    bot = context.bot
    chat_id = update.message.chat_id
    document = collection.find_one({'_id': chat_id})
    data = {"_id": chat_id, "conversation" : []}
    welcome = """Hello, 🌟
Step into a world of language mastery with CasablancaAI. Your AI Language Assistant is ready to embark on an engaging language learning journey with you. Whether you're here to improve your speaking, writing, or listening skills, CasablancaAI is your personalized language tutor."""
    if document :
        bot.send_message(chat_id=update.message.chat_id, text=welcome,parse_mode= 'Markdown')

    else:
        collection.insert_one(data)
        bot.send_message(chat_id=update.message.chat_id, text=welcome,parse_mode= 'Markdown')



def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def voice_handler(update, context):
    bot = context.bot
    chat_id = update.message.chat_id
    try:
        try:
            file_id = update.message.voice.file_id
        except:
            file_id = update.message.audio.file_id
        file_path = f'voice_{chat_id}.mp3'
        msg = STT(bot,file_path,file_id,chat_id)
        existing_document = collection.find_one({"_id": chat_id})
        existing_document['conversation'].append({ "role": "user", "content": msg })
        docs = vectore_store.similarity_search(msg)
        existing_document['conversation'][0] =  {"role": "system", "content": prompt_ai(docs)}

        output_ai = response(existing_document['conversation'])
        print(output_ai)
        audio = TTS(output_ai,file_path)
        bot.send_voice(chat_id=chat_id, voice=audio)

        existing_document['conversation'].append({ "role": "assistant", "content": output_ai })
        collection.update_one({"_id": chat_id}, {'$set': {'conversation': existing_document['conversation']}})

        if os.path.exists(file_path):
            # Delete the file
            os.remove(file_path)
            print(f"File {file_path} has been deleted.")
        else:
            print(f"File {file_path} does not exist.")



    except Exception as e:
        bot = context.bot
        chat_id = update.message.chat_id
        bot.send_message(chat_id=chat_id, text='We have a problem in our bot we gonna fix it ASAP')
        print(f"An unexpected error occurred: {e}")
    print("ok")

def text_handler(update, context):
    bot = context.bot
    chat_id = update.message.chat_id
    try:

        msg = update.message.text

        existing_document = collection.find_one({"_id": chat_id})
        existing_document['conversation'].append({ "role": "user", "content": msg })
        docs = vectore_store.similarity_search(msg)
        existing_document['conversation'][0] =  {"role": "system", "content": prompt_ai(docs)}

        output_ai = response(existing_document['conversation'])
        print(output_ai)
        bot.send_message(chat_id=update.message.chat_id, text=output_ai)

        existing_document['conversation'].append({ "role": "assistant", "content": output_ai })
        collection.update_one({"_id": chat_id}, {'$set': {'conversation': existing_document['conversation']}})


    except Exception as e:
        bot = context.bot
        chat_id = update.message.chat_id
        bot.send_message(chat_id=chat_id, text='We have a problem in our bot we gonna fix it ASAP')
        print(f"An unexpected error occurred: {e}")
    print("ok")
def main():
    """Start the bot."""

    updater = Updater(bot_token)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))

    dp.add_handler(MessageHandler(Filters.voice, voice_handler))
    dp.add_handler(MessageHandler(Filters.audio, voice_handler))
    dp.add_handler(MessageHandler(Filters.text, text_handler))

    # log all errors
    dp.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
