from django.core.validators import RegexValidator


TelephoneValidators = [RegexValidator(r'^0([0-9]{2,3})(-)?([0-9]{3,4})(-)?([0-9]{4})$',)]

MobileValidators = [RegexValidator(r'^01([0|1|6|7|8|9]?)(-)?([0-9]{3,4})(-)?([0-9]{4})$',)]

MobileNumberOnlyValidators = [RegexValidator(r'^01([0|1|6|7|8|9]?)([0-9]{3,4})([0-9]{4})$',)]
