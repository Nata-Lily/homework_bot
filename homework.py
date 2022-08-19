import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from requests.exceptions import RequestException

import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
SEND_MESSAGE = 'Отправлено сообщение: {}'
API_ANSWER_ERROR = ('Ошибка подключения к API: {error}. '
                    'endpoint: {url}, headers: {headers}, params: {params}')
RESPONSE_ERROR = ('Отказ от обслуживания: {error}, key {key}. '
                  'endpoint: {url}, headers: {headers}, params: {params}')
STATUS_CODE_ERROR = ('Ошибка при запросе к API: '
                     'status_code: {status_code}, endpoint: {url}, '
                     'headers: {headers}, params: {params}')
UNKNOWN_STATUS_ERROR = 'Неизвестный статус: {}'
CHANGED_STATUS = 'Изменился статус проверки работы "{}". {}'
RESPONSE_NOT_DICT = 'Ответ API в формате {}'
HOMEWORKS_NOT_IN_RESPONSE = 'Ошибка доступа по ключу homeworks'
HOMEWORKS_NOT_LIST = 'Под ключом homeworks домашки приходят в виде {}'
TOKEN_NOT_FOUND = 'Отсутствует обязательная переменная окружения {}'
ERROR_MESSAGE = 'Сбой в работе программы: {}'
HOMEWORK_STATUS_NOT_FOUND = 'Не найден ключ status!'
SEND_MESSAGE_ERROR = 'Ошибка при отправке сообщения: {}'
TOKEN_ERROR = 'Переменная окружения недоступна!'
EMPTY_LIST = 'Список пуст'
NO_STATUS_CHANGES = 'Обновления статуса нет'

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=None)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения об изменении статуса."""
    bot.send_message(TELEGRAM_CHAT_ID, text=message)
    logger.info(SEND_MESSAGE.format(message), exc_info=True)


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту API-сервиса."""
    parameters = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': current_timestamp}
        )
    try:
        response = requests.get(**parameters)
    except RequestException as error:
        raise ConnectionError(
            API_ANSWER_ERROR.format(
                error=error, **parameters
            )
        )
    status_code = response.status_code
    if response.status_code != HTTPStatus.OK:
        raise exceptions.StatusCodeError(
            STATUS_CODE_ERROR.format(
                status_code=status_code, **parameters
            )
        )
    response_json = response.json()
    for key in ('error', 'code'):
        if key in response_json:
            raise exceptions.ResponseError(
                RESPONSE_ERROR.format(
                    error=response_json[key],
                    key=key,
                    **parameters
                ))
    return response_json


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(RESPONSE_NOT_DICT.format(type(response)))
    if 'homeworks' not in response:
        raise KeyError(HOMEWORKS_NOT_IN_RESPONSE)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(HOMEWORKS_NOT_LIST.format(type(homeworks)))
    return homeworks


def parse_status(homework):
    """Извлечение из информации о домашней работе статуса этой работы."""
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(UNKNOWN_STATUS_ERROR.format(str(homework_status)))
    return (CHANGED_STATUS.format(
        homework['homework_name'],
        HOMEWORK_VERDICTS.get(homework_status)))


def check_tokens():
    """Проверка наличия токенов."""
    flag = True
    for token in TOKENS:
        if globals()[token] is None:
            logger.critical(
                TOKEN_NOT_FOUND.format(token)
            )
            flag = False
    return flag


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError(TOKEN_ERROR)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    previous_status = None
    previous_error = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                hw_status = homeworks[0].get('homework_status')
                if hw_status != previous_status:
                    message = parse_status(homeworks[0])
                    send_message(bot, message)
                    current_timestamp = response.get(
                        'current_date', current_timestamp
                    )
                    previous_status = hw_status
                else:
                    logger.debug(NO_STATUS_CHANGES)

        except Exception as error:
            message = ERROR_MESSAGE.format(error)
            logger.error(message)
            if previous_error != message:
                try:
                    send_message(bot, message)
                    previous_error = message
                except Exception as error:
                    logger.exception(SEND_MESSAGE_ERROR.format(error))
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename=__file__ + '.log',
        format='%(asctime)s, %(levelname)s, %(name)s, %(message)s'
    )
    main()
