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


def send_message(bot, message: str):
    """Отправляем сообщение в телеграм."""
    try:
        logger.info('Начали отправку сообщения')
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError:
        raise exceptions.CriticalError('Сообщения не отправлены')
    else:
        logger.info(f'Сообщение успешно отправилось в чат {TELEGRAM_CHAT_ID}')


def get_api_answer(current_timestamp: int):
    """Делает зпрос к API."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        logger.info('Начали запрос к API')
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            logger.error('ConnectionError')
            raise requests.exceptions.ConnectionError
    except exceptions.FailureToGetAPI:
        logger.error('Не удалось подключиться к API{response.status_code}')
        raise ConnectionError(
            f'Не удалось подключиться к API{response.status_code}')

    return response.json()


def check_response(response: dict):
    """Проверяем API на корректность."""
    logging.info('Проверяем ответ сервера')
    if not isinstance(response, dict):
        raise TypeError('Ответ API отличен от словаря')
    homework_list = response.get('homeworks')
    current_date = response.get('current_date')
    if not homework_list or not current_date:
        raise exceptions.CriticalError('Ревьюер не взял на проверку')
    if not isinstance(homework_list, list):
        raise exceptions.IncorrectFormatResponse('Данные не читаемы')
    return homework_list


def parse_status(homework: dict):
    """Извлекает статус дз."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_name:
        raise KeyError('Ошибка доступа по ключу')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    if verdict is None:
        raise KeyError('Нет статуса домашней работы')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all((TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN))


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status = None
    privious_error = True
    if not check_tokens():
        msg = 'отсутствие обязательных переменных окружения во время '
        logger.critical(msg)
        sys.exit(msg)

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date', current_timestamp)
            homework = check_response(response)
            if not homework:
                logger.error(f'Ошибка доступа по ключу {homework}'
                             f'{__name__}: не согли найти ключ')
            new_status = homework[0].get('status')
            if new_status != status:
                status = new_status
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logger.debug('Статус не изменился')
        except exceptions.NoTelegramError as error:
            logger.info({error})

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            privious_error = message
            if privious_error:
                privious_error = False
                send_message(bot, message)
            logger.error(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
