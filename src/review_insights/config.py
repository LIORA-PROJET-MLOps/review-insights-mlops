from dataclasses import dataclass


APP_TITLE = "Review Insights+"
APP_SUBTITLE = (
    "POC MVP pour l'analyse thematique et sentimentale de commentaires clients "
    "en anglais."
)
DEFAULT_THEME_THRESHOLD = 0.34
MAX_SELECTABLE_ROWS = 1500


@dataclass(frozen=True)
class ThemeDefinition:
    key: str
    label_fr: str
    label_en: str
    icon: str


THEMES = (
    ThemeDefinition("livraison", "Livraison", "Delivery", "🚚"),
    ThemeDefinition("sav", "Service client", "Customer Support", "🎧"),
    ThemeDefinition("produit", "Produit", "Product", "📦"),
)
