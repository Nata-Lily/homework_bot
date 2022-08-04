class SendMessageFailure(Exception):
    pass


class APIResponseStatusCodeException(Exception):
    pass


class CheckResponseException(Exception):
    pass


class UnknownHWStatusException(Exception):
    pass


class MissingRequiredTokenException(Exception):
    pass


class IncorrectAPIResponseException(Exception):
    pass
