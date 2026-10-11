from ...registry import Guide, ToolInfo
from .page import NetworkPage

GUIDE = Guide(
    summary="Bağlantılarını gösterir, ping atar, DNS sorgular ve tek bir portun açık olup olmadığını dener.",
    steps=(
        "'Bağlantılar': hangi programın hangi adrese bağlandığını ve bilgisayarında dinleyen portları görürsün. "
        "Şüpheli bir bağlantının hangi programa ait olduğunu buradan bulabilirsin.",
        "'Ping': bir adrese ping atar; en az/ortalama/en çok süreyi ve kayıp yüzdesini gösterir (bağlantı kalitesini ölçmek için).",
        "'DNS': bir alan adının hangi IP adreslerine çözüldüğünü ve ne kadar sürdüğünü gösterir.",
        "'Port kontrol': tek bir ana bilgisayar:port'a bağlanmayı dener (ör. bir sunucunun 443 portu açık mı?).",
        "'Bilgi': ağ bağdaştırıcıların, IP adreslerin ve bağlantı hızın.",
    ),
    tips=(
        "Port kontrol bir port tarayıcısı değildir: yalnızca senin yazdığın tek bir host:port'u dener.",
        "Girdiler komuta verilmeden doğrulanır; geçersiz adresler hiçbir zaman çalıştırılmaz.",
        "Başka kullanıcıların ya da yönetici yetkili programların adları için yönetici izni gerekebilir.",
    ),
)

TOOL = ToolInfo(
    id="ag",
    name="Ağ Araçları",
    icon="🌐",
    description="Etkin bağlantıları ve dinleyen portları gösterir; ping, DNS sorgusu ve port kontrolü yapar.",
    build=lambda parent, hub: NetworkPage(parent, hub),
    order=110,
    guide=GUIDE,
    category="sistem",
)
