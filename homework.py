import logging
import os
import sys
import time
from logging import FileHandler, StreamHandler
from typing import Dict
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()
logging.basicConfig(
    filename='app.log',
    filemode='w',
    level=logging.DEBUG,
    format='%(asctime)s, %(name)s,%(levelname)s, %(message)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stream_handler = StreamHandler()
file_handler = FileHandler('file.log')
logger.addHandler(stream_handler)
logger.addHandler(file_handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
date_3_days_ago = 1660987256

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляем сообщение в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
        logger.info(f'Сообщение в чат {TELEGRAM_CHAT_ID} отправлено')
    except telegram.error.TelegramError:
        raise telegram.error.TelegramError('Сообщения не отправлены')


def get_api_answer(current_timestamp):
    """Делает зпрос к API."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    logger.info('Начали запрос к API')
    response = requests.get(
        ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != HTTPStatus.OK:
        logger.error(f'{__name__}:Ошибка при запросе к основному API: '
                     f'{ENDPOINT}')
        raise requests.exceptions.ConnectionError

    return response.json()


def check_response(response):
    """Проверяем API на корректность."""
    logging.info('Проверяем ответ сервера')
    if not isinstance(response, dict):
        logger.debug(f'{__name__}: проверяем тип'
                     f'данных response: {type(response)}')
        raise TypeError('Ответ API отличен от словаря')
    try:
        homework_list = response.get('homeworks')
        current_date = response.get('current_date')
    except KeyError as e:
        raise KeyError(f'Ошибка доступа по ключу homeworks: {e}')
    if not homework_list and current_date:
        logger.info('Ревьюер не взял на проверку')
        raise exceptions.CriticalError('Ревьюер не взял на проверку')
    if not isinstance(homework_list, list):
        logger.debug(f'{__name__}: проверяем тип данных'
                     f'homework_list: {type(homework_list)}')
        raise exceptions.IncorrectFormatResponse('Данные не читаемы')
    return homework_list


def parse_status(homework: Dict):
    """Извлекает статус дз."""
    try:
        homework_name = homework['homework_name']
    except KeyError as err:
        logger.error(f'Ошибка доступа по ключу {err}')
    try:
        homework_status = homework['status']
    except KeyError as err:
        logger.error(f'Ошибка доступа по ключу {err}')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    if verdict is None:
        msg = 'Неизвестный статус домашки'
        raise exceptions.UnknownHWStatusException(msg)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all((TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN))


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(date_3_days_ago)
    status = None
    privious_error = None
    if not check_tokens():
        msg = 'отсутствие обязательных переменных окружения во время '
        logger.critical(msg)
        sys.exit(msg)

    while True:
        try:
            response = get_api_answer(current_timestamp)
            try:
                homework = check_response(response)
            except KeyError as e:
                logger.error(f'Ошибка доступа по ключу homeworks: {e}')
            new_status = homework[0].get('status')
            if new_status != status:
                status = new_status
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logger.info('Статус не изменился')
                time.sleep(RETRY_TIME)
        except exceptions.NoTelegramError as error:
            logger.error(f'Критическая ошибка в работе бота {error}')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if privious_error != str(error):
                privious_error = str(error)
                send_message(bot, message)
            logger.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
