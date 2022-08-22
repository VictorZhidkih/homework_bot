import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(name)s,%(levelname)s, %(message)s'
)

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


logger = logging.getLogger(__name__)


def send_message(bot, message):
    """Отправляем сообщение в телеграм."""
    chat_id = TELEGRAM_CHAT_ID
    try:
        bot.send_message(chat_id, text=message)
        logger.info(f'Сообщение в чат {TELEGRAM_CHAT_ID} отправлено')
    except exceptions.SendMessageFailure:
        logger.error('Ошибка отправки сообщения в телеграм')


def get_api_answer(current_timestamp):
    """Делает зпрос к API."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
    except exceptions.FailureToGetAPI as err:
        logger.error(f'Ошибка при запросе к основному API:{err}')
        raise exceptions.FailureToGetAPI(
            f'Ошибка при запросе к основному API:{err}'
        )
    if response.status_code != HTTPStatus.OK:
        logger.error('недоступность эндпоинта')
        raise Exception('недоступность эндпоинта')

    return response.json()


def check_response(response):
    """Проверяем API на корректность."""
    try:
        homework_list = response['homeworks']
    except KeyError as e:
        logger.error(f'Ошибка доступа по ключу homeworks: {e}')
        raise KeyError(f'Ошибка доступа по ключу homeworks: {e}')
    if len(homework_list) == 0:
        logger.error('Список домашних работ пуст')
        raise IndexError('Список домашних работ пуст')
    if isinstance(homework_list, list):
        logger.error('Данные не читаемы')
        raise exceptions.IncorrectFormatResponse('Данные не читаемы')
    return homework_list


def parse_status(homework):
    """Извлекает статус дз."""
    try:
        homework_name = homework.get('homework_name')
    except KeyError as err:
        logger.error(f'Ошибка доступа по ключу {err}')
    try:
        homework_status = homework.get('status')
    except KeyError as err:
        logger.error(f'Ошибка доступа по ключу {err}')
    if homework_status not in HOMEWORK_STATUSES:
        logger.error('Неизвестный статус работы')
        raise exceptions.UnknownStatusHomeWork('Неизвестный статус работы')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN])


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = {'from_date':1657971146}
    STATUS = ''
    PRIVIOUS_ERROR = ''
    if not check_tokens():
        msg = 'отсутствие обязательных переменных окружения во время '
        logger.critical(msg)
        raise Exception(msg)

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            new_status = homework[0].get('status')
            if new_status != STATUS:
                STATUS = new_status
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logger.INFO('Статус не изменился')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if PRIVIOUS_ERROR != str(error):
                PRIVIOUS_ERROR = str(error)
                send_message(bot, message)
            logger.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
