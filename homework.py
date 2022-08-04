import logging
import os
import time

from http import HTTPStatus
from dotenv import load_dotenv
import requests
import telegram

import exceptions

load_dotenv()


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

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=None)
logger.addHandler(handler)


def send_message(bot, message):
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
        logger.info('Сообщение в чат отправлено')
    except exceptions.SendMessageFailure:
        logger.error('Сбой при отправке сообщения в чат')


def get_api_answer(current_timestamp):
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except exceptions.APIResponseStatusCodeException:
        logger.error('Сбой при запросе к эндпоинту')
    if response.status_code != HTTPStatus.OK:
        logger.error('Сбой при запросе к эндпоинту')
        raise exceptions.APIResponseStatusCodeException()
    return response.json()


def check_response(response):
    try:
        homeworks_list = response['homeworks']
    except KeyError as error:
        logger.error(f'Ошибка доступа по ключу homeworks: {error}')
        raise exceptions.CheckResponseException()
    if homeworks_list is None:
        logger.error('В ответе API нет словаря с домашними работами')
        raise exceptions.CheckResponseException()
    if len(homeworks_list) == 0:
        logger.error('Список домашних работ пуст')
        raise exceptions.CheckResponseException('Список домашних работ пуст')
    if type(homeworks_list) is not list:
        logger.error('Домашние работы представлены не списком')
        raise exceptions.CheckResponseException()
    return homeworks_list


def parse_status(homework):
    try:
        homework_name = homework.get('homework_name')
    except KeyError as error:
        logger.error(f'Ошибка доступа по ключу homework_name: {error}')
    try:
        homework_status = homework.get('status')
    except KeyError as error:
        logger.error(f'Ошибка доступа по ключу status: {error}')

    verdict = HOMEWORK_STATUSES[homework_status]
    if verdict is None:
        logger.error('Недокументированный статус домашней работы')
        raise exceptions.UnknownHWStatusException()
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    for token in ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID'):
        if globals()[token] is None:
            logger.error(
                f'Отсутствует обязательная переменная окружения: {token}'
            )
            return False
    return True


def main():
    if not check_tokens():
        logger.critical('Переменная окружения недоступна')
        raise exceptions.MissingRequiredTokenException()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    previous_status = None
    previous_error = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
        except exceptions.IncorrectAPIResponseException as error:
            if str(error) != previous_error:
                previous_error = str(error)
                send_message(bot, error)
            logger.error(error)
            time.sleep(RETRY_TIME)
            continue
        try:
            homeworks = check_response(response)
            hw_status = homeworks[0].get('status')
            if hw_status != previous_status:
                previous_status = hw_status
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logger.debug('Обновления статуса нет')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if previous_error != str(error):
                previous_error = str(error)
                send_message(bot, message)
            logger.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
