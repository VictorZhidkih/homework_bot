class SendMessageFailure(Exception):
    """Ошибка отправк сообщени]"""

    pass

class FailureToGetAPI(Exception):
    """Ошибка при подключении к API"""
    
    pass

class UnknownStatusHomeWork(Exception):
    """Неизвестный статус дз"""
    
    pass

class IncorrectFormatResponse(Exception):
    """Некорректный формат данных"""
    
    pass