# Коды стран (ISO 3166-1 alpha-2)
AI_SUPPORTED_COUNTRIES = {
    "US", "GB", "DE", "FR", "IT", "ES", "JP", "KR", "BR", "AU", "CA", "IN",
    "ID", "PL", "NL", "SE", "NO", "FI", "DK", "SG", "MY", "PH", "TR", "UA",
    "GE", "AM", "AZ", "KZ", "UZ", "IL", "AE", "SA", "ZA", "MX", "AR", "CL"
    # Это сокращенный список для примера. Полный включает почти все страны, кроме
    # РФ, РБ, Китая, Ирана, КНДР, Кубы, Сирии.
}

def is_ai_supported(cc):
    return cc.upper() in AI_SUPPORTED_COUNTRIES
