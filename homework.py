import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(name)s,%(levelname)s, %(message)s',
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler('file.log')])

logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

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
    except telegram.error.TelegramError:
        raise exceptions.CriticalError('Сообщения не отправлены')
    else:
        logger.info(f'Начинаем отправку сообщения в чат {TELEGRAM_CHAT_ID}')


def get_api_answer(current_timestamp):
    """Делает зпрос к API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logger.info('Начали запрос к API')
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise requests.exceptions.ConnectionError
    except exceptions.FailureToGetAPI:
        raise requests.exceptions.ConnectionError(
            f'Не удалось подключиться к API{response.status_code}')

    return response.json()


def check_response(response):
    """Проверяем API на корректность."""
    logging.info('Проверяем ответ сервера')
    if not isinstance(response, dict):
        logger.debug(f'{__name__}: проверяем тип'
                     f'данных response: {type(response)}')
        raise TypeError('Ответ API отличен от словаря')
    homework_list = response.get('homeworks')
    current_date = response.get('current_date')
    if not homework_list and not current_date:
        raise exceptions.CriticalError('Ревьюер не взял на проверку')
    if not isinstance(homework_list, list):
        raise exceptions.IncorrectFormatResponse('Данные не читаемы')
    return homework_list


def parse_status(homework: dict):
    """Извлекает статус дз."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_name and not homework_status:
        raise KeyError('Ошибка доступа по ключу')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all((TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN))


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time() - 1660987256)
    status = None
    privious_error = None
    if not check_tokens():
        msg = 'отсутствие обязательных переменных окружения во время '
        logger.critical(msg)
        sys.exit(msg)

    while True:
        try:
            response = get_api_answer(current_timestamp)
            response.get('current_date', current_timestamp)
            logger.error(f'{__name__}:Ошибка при запросе к основному API: '
                         f'{ENDPOINT}')
            logger.debug(f'{__name__}: проверяем тип'
                         f'данных response: {type(response)}')
            homework = check_response(response)
            if not homework:
                logger.error('Ошибка доступа по ключу homeworks')
            new_status = homework[0].get('status')
            if new_status != status:
                status = new_status
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logger.info('Статус не изменился')
        except exceptions.NoTelegramError as error:
            logger.info(f'{error}')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if privious_error != str(error):
                privious_error = message
                send_message(bot, message)
            logger.error(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
