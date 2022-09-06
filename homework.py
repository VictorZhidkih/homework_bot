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
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise ConnectionError(
                'Возникла ошибка соединения! \
                Проверьте Ваше подключение к интернету.'
            )
    except exceptions.FailureToGetAPI:
        logger.error('Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен.\
            Код ответа API: {response.status_code}')
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
        raise exceptions.CriticalError('Отсутсвие ожидаемых ключей')
    if not isinstance(homework_list, list):
        raise exceptions.IncorrectFormatResponse('Данные не читаемы')
    return homework_list


def parse_status(homework: dict):
    """Извлекает статус дз."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_name:
        raise KeyError(f'Ошибка доступа по ключу {homework_name}')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    if not verdict:
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
    if not check_tokens():
        msg = 'отсутствие обязательных переменных окружения во время '
        logger.critical(msg)
        sys.exit(msg)

    while True:
        try:
            logger.info('Начали запрос к API')
            response = get_api_answer(current_timestamp)
            if not response:
                logger.error('Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен.\
                             Код ответа API: {response.status_code}')
            current_timestamp = response.get('current_date', current_timestamp)
            homework = check_response(response)
            if not homework:
                logger.info('Домашних работ нет')
            new_status = parse_status(homework)
            if new_status != status:
                status = new_status
                message = new_status
                send_message(bot, message)
            else:
                logger.debug(f'Статус {homework} не изменился')
        except exceptions.NoTelegramError as error:
            logger.error(error)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
