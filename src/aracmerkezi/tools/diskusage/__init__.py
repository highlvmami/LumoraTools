from ...registry import ToolInfo
from .page import DiskUsagePage

TOOL = ToolInfo(
    id="boyut",
    name="Boyut Analizcisi",
    icon="📊",
    description="Diskte yeri en çok kimin kapladığını gösterir: klasörlere inen çubuk grafik ve en büyük dosyalar.",
    build=lambda parent, hub: DiskUsagePage(parent, hub),
    order=40,
)
