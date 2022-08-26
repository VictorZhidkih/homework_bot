class SendMessageFailure(Exception):
    """Ошибка отправк сообщени."""


class FailureToGetAPI(Exception):
    """Ошибка при подключении к API."""
    

class UnknownStatusHomeWork(Exception):
    """Неизвестный статус дз."""
    

class IncorrectFormatResponse(Exception):
    """Некорректный формат данных."""
    
class NoTelegramError(BaseException):
    """Ошибки которые не надо отправлять в ТГ."""
    
class CriticalError(NoTelegramError):
    """Критическая ошибка в работе Бота."""