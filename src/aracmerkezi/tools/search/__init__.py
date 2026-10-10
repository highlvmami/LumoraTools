from ...registry import ToolInfo
from .page import SearchPage

TOOL = ToolInfo(
    id="arama",
    name="Yerel Arama",
    icon="🔎",
    description="Seçtiğin klasörlerdeki dosyaların içeriğini dizinler ve anında arar. Metin, kod, Word ve PDF.",
    build=lambda parent, hub: SearchPage(parent, hub),
    order=30,
)
