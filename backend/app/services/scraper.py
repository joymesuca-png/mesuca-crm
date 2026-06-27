"""
外贸获客系统 - 真实数据采集引擎

多渠道客户信息采集，支持：
- 搜索引擎：Google、Bing 搜索企业信息
- B2B 平台：阿里巴巴国际站、中国制造网
- 商业目录：Yellow Pages、Yelp 企业列表
- 公司网站：深度挖掘联系邮箱、电话、社交账号
- 反爬处理：User-Agent 轮换、随机延迟、指数退避重试
"""
import logging
import re
import time
import random
import os
from typing import List, Optional, Dict, Tuple
from datetime import datetime, UTC
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── 延迟配置（境内网络环境缩短超时） ──
_MIN_DELAY = 0.8
_MAX_DELAY = 2.0
_RETRY_MAX = 1          # 只重试 1 次（境内网络避免长时间等待）
_RETRY_BACKOFF = 1.0
_REQUEST_TIMEOUT = 8.0   # 单次请求超时 8 秒
_QUICK_TIMEOUT = 4.0     # 连通性检查超时 4 秒

# ── 代理配置（可选，通过环境变量设置） ──
_PROXY_URL = os.getenv("SCRAPER_PROXY_URL", "")

# 配置了代理说明走 VPN，放宽超时和重试
if _PROXY_URL:
    _REQUEST_TIMEOUT = 15.0
    _QUICK_TIMEOUT = 8.0
    _RETRY_MAX = 2
    _MIN_DELAY = 1.0
    _MAX_DELAY = 3.0
    logger.info(f"检测到代理配置: {_PROXY_URL}，已调整超时参数")


def _sleep(min_s: float = None, max_s: float = None):
    """随机延迟，模拟人类行为"""
    time.sleep(random.uniform(min_s or _MIN_DELAY, max_s or _MAX_DELAY))


# ── User-Agent 轮换池 ──
_USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "en-GB,en;q=0.9,fr;q=0.8,de;q=0.7",
    "en-US,en;q=0.9,es;q=0.8,pt;q=0.7",
]


def _get_client(timeout: float = None) -> httpx.Client:
    """创建带随机 UA 的 HTTP 客户端"""
    if timeout is None:
        timeout = _REQUEST_TIMEOUT
    kwargs = {
        "headers": {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": random.choice(_ACCEPT_LANGUAGES),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        },
        "timeout": timeout,
        "follow_redirects": True,
    }
    if _PROXY_URL:
        kwargs["proxy"] = _PROXY_URL
    return httpx.Client(**kwargs)


def _fetch_with_retry(url: str, timeout: float = None) -> Tuple[Optional[str], int]:
    """带重试的 HTTP 请求，返回 (响应文本, 状态码)"""
    if timeout is None:
        timeout = _REQUEST_TIMEOUT
    last_error = None
    for attempt in range(_RETRY_MAX + 1):
        try:
            with _get_client(timeout) as client:
                resp = client.get(url)
                if resp.status_code == 429:
                    # 被限流，等待更长时间
                    wait = _RETRY_BACKOFF * (2 ** attempt) + random.uniform(1, 3)
                    logger.warning(f"HTTP 429，等待 {wait:.1f}s 后重试...")
                    time.sleep(wait)
                    continue
                return resp.text, resp.status_code
        except httpx.TimeoutException:
            logger.warning(f"请求超时 (attempt {attempt + 1}): {url[:80]}")
            last_error = "timeout"
        except Exception as e:
            logger.warning(f"请求失败 (attempt {attempt + 1}): {url[:80]} - {e}")
            last_error = str(e)

        if attempt < _RETRY_MAX:
            time.sleep(_RETRY_BACKOFF * (attempt + 1))

    return None, 0


# ── 邮箱/电话/社交账号提取 ──
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,6}"
)
_SKIP_EMAILS = {
    "example@", "user@", "admin@", "info@", "test@", "noreply@", "support@",
    "sales@", "contact@", "hello@", "email@", "mail@", "webmaster@", "postmaster@",
    "no-reply@", "donotreply@", "notifications@", "newsletter@", "marketing@",
    "service@", "help@", "feedback@", "team@", "office@", "enquiries@", "enquiry@",
}

# LinkedIn / Facebook / Twitter 账号提取
_SOCIAL_RE = {
    "linkedin": re.compile(r"(?:linkedin\.com/(?:company|in)/)([a-zA-Z0-9\-]+)", re.I),
    "facebook": re.compile(r"(?:facebook\.com/)([a-zA-Z0-9.\-]+)", re.I),
    "twitter": re.compile(r"(?:twitter\.com/)([a-zA-Z0-9_]+)", re.I),
    "instagram": re.compile(r"(?:instagram\.com/)([a-zA-Z0-9_.\-]+)", re.I),
}


def _extract_emails(text: str, domain: str = "") -> List[str]:
    """从文本中提取有效邮箱，优先匹配公司域名"""
    emails = set()
    for m in _EMAIL_RE.finditer(text):
        e = m.group().lower().strip()
        if any(e.startswith(s) for s in _SKIP_EMAILS):
            continue
        # 排除图片路径
        if any(x in e for x in [".png", ".jpg", ".gif", ".svg", ".webp"]):
            continue
        emails.add(e)

    if domain:
        # 优先返回公司域名邮箱
        domain_emails = [e for e in emails if e.endswith(f"@{domain}")]
        if domain_emails:
            return list(domain_emails)[:3]
    return list(emails)[:3]


def _extract_phones(text: str) -> List[str]:
    """从文本中提取有效电话号码"""
    phones = []
    seen = set()
    for m in _PHONE_RE.finditer(text):
        p = m.group().strip()
        digits = re.sub(r"\D", "", p)
        if len(digits) < 7 or len(digits) > 15:
            continue
        if digits.startswith("0") and len(digits) < 10:
            continue
        if p not in seen:
            seen.add(p)
            phones.append(p)
    return phones[:3]


def _extract_social_links(text: str) -> Dict[str, str]:
    """从文本中提取社交媒体链接"""
    result = {}
    for platform, pattern in _SOCIAL_RE.items():
        match = pattern.search(text)
        if match:
            result[platform] = match.group(1)
    return result


# ── 行业关键词映射 ──
_INDUSTRY_MAP = {
    "led": "Lighting & Electrical", "light": "Lighting & Electrical",
    "lamp": "Lighting & Electrical", "bulb": "Lighting & Electrical",
    "auto": "Auto Parts & Accessories", "car": "Auto Parts & Accessories",
    "vehicle": "Auto Parts & Accessories", "motorcycle": "Auto Parts & Accessories",
    "toy": "Toys & Hobbies", "doll": "Toys & Hobbies",
    "figure": "Toys & Hobbies", "game": "Toys & Hobbies",
    "fashion": "Apparel & Fashion", "clothing": "Apparel & Fashion",
    "garment": "Apparel & Fashion", "apparel": "Apparel & Fashion",
    "bag": "Bags & Luggage", "luggage": "Bags & Luggage",
    "backpack": "Bags & Luggage", "wallet": "Bags & Luggage",
    "shoe": "Footwear", "sneaker": "Footwear", "boot": "Footwear",
    "electronic": "Consumer Electronics", "phone": "Consumer Electronics",
    "earphone": "Consumer Electronics", "headphone": "Consumer Electronics",
    "speaker": "Consumer Electronics", "charger": "Consumer Electronics",
    "computer": "IT & Technology", "software": "IT & Technology",
    "laptop": "IT & Technology", "server": "IT & Technology",
    "machine": "Industrial Machinery", "machinery": "Industrial Machinery",
    "equipment": "Industrial Machinery", "cnc": "Industrial Machinery",
    "tool": "Hardware & Tools", "hardware": "Hardware & Tools",
    "furniture": "Furniture & Home", "sofa": "Furniture & Home",
    "chair": "Furniture & Home", "table": "Furniture & Home",
    "home": "Home & Garden", "garden": "Home & Garden",
    "kitchen": "Kitchen & Dining", "cookware": "Kitchen & Dining",
    "food": "Food & Beverage", "drink": "Food & Beverage",
    "beverage": "Food & Beverage", "snack": "Food & Beverage",
    "medical": "Medical Devices", "health": "Health & Beauty",
    "beauty": "Health & Beauty", "cosmetic": "Health & Beauty",
    "skincare": "Health & Beauty", "makeup": "Health & Beauty",
    "sport": "Sports & Outdoors", "fitness": "Sports & Outdoors",
    "outdoor": "Sports & Outdoors", "camping": "Sports & Outdoors",
    "chemical": "Chemicals & Materials", "plastic": "Plastics & Rubber",
    "rubber": "Plastics & Rubber", "metal": "Metals & Mining",
    "steel": "Metals & Mining", "aluminum": "Metals & Mining",
    "textile": "Textiles & Fabrics", "fabric": "Textiles & Fabrics",
    "yarn": "Textiles & Fabrics", "towel": "Textiles & Fabrics",
    "paper": "Packaging & Printing", "packaging": "Packaging & Printing",
    "printing": "Packaging & Printing", "box": "Packaging & Printing",
    "solar": "Renewable Energy", "energy": "Renewable Energy",
    "battery": "Renewable Energy", "panel": "Renewable Energy",
    "jewelry": "Jewelry & Watches", "watch": "Jewelry & Watches",
    "ring": "Jewelry & Watches", "necklace": "Jewelry & Watches",
    "pet": "Pet Supplies", "dog": "Pet Supplies", "cat": "Pet Supplies",
}


def _guess_industry(keyword: str) -> str:
    kw = keyword.lower()
    for k, v in _INDUSTRY_MAP.items():
        if k in kw:
            return v
    return "General Trade"


# ── 国家代码映射 ──
_COUNTRY_GL = {
    "USA": "us", "UK": "uk", "Germany": "de", "France": "fr",
    "Japan": "jp", "Canada": "ca", "Australia": "au", "Brazil": "br",
    "India": "in", "Italy": "it", "Spain": "es", "Netherlands": "nl",
    "Korea": "kr", "Mexico": "mx", "Turkey": "tr", "Russia": "ru",
    "UAE": "ae", "Saudi Arabia": "sa", "South Africa": "za",
    "Singapore": "sg", "Indonesia": "id", "Vietnam": "vn",
    "Thailand": "th", "Malaysia": "my", "Philippines": "ph",
}

_COUNTRY_TLDS = {
    "USA": ".com", "UK": ".co.uk", "Germany": ".de", "France": ".fr",
    "Japan": ".jp", "Canada": ".ca", "Australia": ".com.au",
    "Brazil": ".com.br", "India": ".in", "Italy": ".it",
    "Spain": ".es", "Netherlands": ".nl", "Korea": ".kr",
    "Mexico": ".mx", "Russia": ".ru", "UAE": ".ae",
}


# ================================================================
#  工具函数
# ================================================================

def _clean_company_name(raw: str) -> str:
    """清理公司名"""
    raw = raw.strip()
    raw = re.sub(r"\s+", " ", raw)
    raw = re.sub(r"\.{2,}$", "", raw)
    raw = re.sub(r"…$", "", raw)
    raw = re.sub(r"^\d+\.\s*", "", raw)  # 去掉编号
    if len(raw) < 3:
        return ""
    return raw[:200]


def _extract_domain(url: str) -> str:
    """从 URL 提取域名（不含 www）"""
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc.lower()
        domain = re.sub(r"^www\d?\.", "", domain)
        return domain
    except Exception:
        m = re.search(r"(?:https?://)?(?:www\d?\.)?([^/]+)", url)
        return m.group(1) if m else ""


def _build_lead(
    company_name: str,
    website: str = "",
    email: str = "",
    phone: str = "",
    country: str = "",
    city: str = "",
    keyword: str = "",
    source_url: str = "",
    snippet: str = "",
    social: Dict[str, str] = None,
) -> dict:
    """构建统一的线索数据字典"""
    return {
        "company_name": _clean_company_name(company_name),
        "contact_name": "",
        "email": email,
        "phone": phone,
        "website": website,
        "country": country or "",
        "city": city or "",
        "industry": _guess_industry(keyword),
        "product_interest": keyword,
        "lead_score": round(random.uniform(50, 85), 1),
        "source_url": source_url,
        "status": "new",
        "original_data": snippet[:500] if snippet else "",
        "social_links": social or {},
    }


# ================================================================
#  搜索引擎采集
# ================================================================

def search_google(keyword: str, country: str = "", max_results: int = 20) -> List[dict]:
    """
    通过 Google 搜索采集企业信息。
    使用 httpx 解析 Google 搜索结果页面。
    """
    leads = []
    gl = _COUNTRY_GL.get(country, "us")

    for start in range(0, min(max_results, 50), 10):
        try:
            q = quote_plus(keyword)
            url = f"https://www.google.com/search?q={q}&num=10&start={start}&gl={gl}&hl=en"
            logger.info(f"Google 搜索: keyword={keyword}, start={start}")

            html, status = _fetch_with_retry(url)
            if not html or status != 200:
                logger.warning(f"Google 返回 {status}，尝试下一页...")
                continue

            soup = BeautifulSoup(html, "lxml")

            # 检测是否被 Google 拦截
            if soup.select_one("form#captcha-form") or "unusual traffic" in html.lower():
                logger.warning("Google 检测到异常流量，可能需要验证码")
                break

            for g in soup.select("div.g, div[data-sokoban-container]"):
                try:
                    title_el = g.select_one("h3")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)

                    link_el = g.select_one("a[href^='http']")
                    link = link_el["href"] if link_el else ""
                    if not link or any(x in link for x in ["google.com", "youtube.com", "accounts.google"]):
                        continue

                    snippet_el = g.select_one("div.VwiC3b, span.aCOpRe, div[data-sncf], div[data-content-feature]")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                    domain = _extract_domain(link)

                    # 从标题提取公司名
                    company = ""
                    for sep in [" - ", " | ", " · ", " – ", " — "]:
                        if sep in title:
                            parts = title.split(sep, 1)
                            company = _clean_company_name(parts[0])
                            break
                    if not company:
                        company = _clean_company_name(title)

                    if not company or len(company) < 3:
                        continue

                    emails = _extract_emails(snippet, domain)
                    phones = _extract_phones(snippet)

                    leads.append(_build_lead(
                        company_name=company,
                        website=link,
                        email=emails[0] if emails else "",
                        phone=phones[0] if phones else "",
                        country=country,
                        keyword=keyword,
                        source_url=url,
                        snippet=snippet,
                    ))

                    if len(leads) >= max_results:
                        break
                except Exception as e:
                    logger.debug(f"解析 Google 搜索结果项失败: {e}")
                    continue

            _sleep()

            if len(leads) >= max_results:
                break
        except Exception as e:
            logger.error(f"Google 搜索失败: {e}")
            break

    logger.info(f"Google 搜索完成，采集 {len(leads)} 条线索")
    return leads


def search_bing(keyword: str, country: str = "", max_results: int = 20) -> List[dict]:
    """通过 Bing 搜索采集企业信息（Google 备选）"""
    leads = []
    cc = country.lower() if country else "us"

    for offset in range(0, min(max_results, 50), 10):
        try:
            q = quote_plus(keyword)
            url = f"https://www.bing.com/search?q={q}&count=10&offset={offset}&cc={cc}&setlang=en"
            logger.info(f"Bing 搜索: keyword={keyword}, offset={offset}")

            html, status = _fetch_with_retry(url)
            if not html or status != 200:
                continue

            soup = BeautifulSoup(html, "lxml")

            for li in soup.select("li.b_algo"):
                try:
                    title_el = li.select_one("h2 a")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    link = title_el.get("href", "")

                    snippet_el = li.select_one("div.b_caption p, .b_lineclamp2, .b_algoSlug")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                    if not link or "bing.com" in link:
                        continue

                    domain = _extract_domain(link)
                    company = ""
                    for sep in [" - ", " | ", " – ", " — "]:
                        if sep in title:
                            company = _clean_company_name(title.split(sep, 1)[0])
                            break
                    if not company:
                        company = _clean_company_name(title)

                    if not company or len(company) < 3:
                        continue

                    emails = _extract_emails(snippet, domain)
                    phones = _extract_phones(snippet)

                    leads.append(_build_lead(
                        company_name=company,
                        website=link,
                        email=emails[0] if emails else "",
                        phone=phones[0] if phones else "",
                        country=country,
                        keyword=keyword,
                        source_url=url,
                        snippet=snippet,
                    ))
                except Exception as e:
                    logger.debug(f"Bing 解析失败: {e}")
                    continue

            _sleep()
            if len(leads) >= max_results:
                break
        except Exception as e:
            logger.error(f"Bing 搜索失败: {e}")
            break

    return leads


# ================================================================
#  B2B 平台采集
# ================================================================

def search_alibaba(keyword: str, max_results: int = 20) -> List[dict]:
    """从阿里巴巴国际站采集供应商信息"""
    leads = []
    try:
        q = quote_plus(keyword)
        url = f"https://www.alibaba.com/trade/search?fsb=y&IndexArea=product_en&SearchText={q}"
        logger.info(f"阿里巴巴采集: {url}")

        html, status = _fetch_with_retry(url)
        if not html or status != 200:
            logger.warning(f"Alibaba 返回 {status}")
            return leads

        soup = BeautifulSoup(html, "lxml")

        selectors = [
            ".organic-list-offer-outter",
            ".organic-offer-wrapper",
            "[data-ctrdot]",
            ".search-card-wrap",
            ".traffic-card",
        ]
        cards = []
        for sel in selectors:
            cards = soup.select(sel)
            if cards:
                break

        for card in cards[:max_results]:
            try:
                company_el = (
                    card.select_one(".organic-offer-wrapper__company") or
                    card.select_one(".supplier-name") or
                    card.select_one("[data-domdot]") or
                    card.select_one(".company-name")
                )
                company = company_el.get_text(strip=True) if company_el else ""

                title_el = card.select_one("h2 a, .organic-title a, .title, .search-card-e-title")
                title = title_el.get_text(strip=True) if title_el else ""

                link_el = card.select_one("a[href*='product'], a[href*='offer']")
                link = link_el.get("href", "") if link_el else ""
                if link and not link.startswith("http"):
                    link = "https:" + link

                if not company:
                    company = title

                if not company or len(company) < 2:
                    continue

                leads.append(_build_lead(
                    company_name=company,
                    website=link,
                    country="China",
                    keyword=keyword,
                    source_url=url,
                    snippet=title,
                ))
            except Exception as e:
                logger.debug(f"Alibaba 解析失败: {e}")
                continue

            _sleep()
    except Exception as e:
        logger.error(f"阿里巴巴采集失败: {e}")

    logger.info(f"阿里巴巴采集完成，获取 {len(leads)} 条")
    return leads


def search_made_in_china(keyword: str, max_results: int = 20) -> List[dict]:
    """从中国制造网采集供应商信息"""
    leads = []
    try:
        q = quote_plus(keyword)
        url = f"https://www.made-in-china.com/multi-search/{q}/F1/catalog-1.html"
        logger.info(f"中国制造网采集: {url}")

        html, status = _fetch_with_retry(url)
        if not html or status != 200:
            logger.warning(f"Made-in-China 返回 {status}")
            return leads

        soup = BeautifulSoup(html, "lxml")

        items = soup.select(".prod-list-item, .product-item, .prod-item, .search-prod-item")
        for item in items[:max_results]:
            try:
                company_el = item.select_one(".company-name, .supplier-name, .comp-name")
                company = company_el.get_text(strip=True) if company_el else ""

                title_el = item.select_one(".prod-name, .product-name, a[title]")
                title = title_el.get("title", "") or title_el.get_text(strip=True) if title_el else ""

                link_el = item.select_one("a[href*='product']")
                link = link_el.get("href", "") if link_el else ""
                if link and not link.startswith("http"):
                    link = "https:" + link

                if not company:
                    continue

                leads.append(_build_lead(
                    company_name=company,
                    website=link,
                    country="China",
                    keyword=keyword,
                    source_url=url,
                    snippet=title,
                ))
            except Exception as e:
                logger.debug(f"Made-in-China 解析失败: {e}")
                continue

            _sleep()
    except Exception as e:
        logger.error(f"中国制造网采集失败: {e}")

    return leads


# ================================================================
#  商业目录采集
# ================================================================

def search_yellow_pages(keyword: str, country: str = "USA", max_results: int = 20) -> List[dict]:
    """
    从 Yellow Pages 商业目录采集企业信息。
    支持的国家：USA, UK, Canada, Australia
    """
    leads = []
    country_domains = {
        "USA": "www.yellowpages.com",
        "UK": "www.yell.com",
        "Canada": "www.yellowpages.ca",
        "Australia": "www.yellowpages.com.au",
    }
    domain = country_domains.get(country, "www.yellowpages.com")

    try:
        q = quote_plus(keyword)
        url = f"https://{domain}/search?search_terms={q}"
        logger.info(f"Yellow Pages 采集: {url}")

        html, status = _fetch_with_retry(url)
        if not html or status != 200:
            return leads

        soup = BeautifulSoup(html, "lxml")

        # Yellow Pages 通用选择器
        biz_selectors = [
            ".result", ".search-results .result", ".v-card",
            ".business-listing", ".organic .result", ".listing",
        ]
        for sel in biz_selectors:
            results = soup.select(sel)
            if results:
                break

        for card in results[:max_results]:
            try:
                name_el = (
                    card.select_one(".business-name") or
                    card.select_one(".n") or
                    card.select_one("h2 a") or
                    card.select_one("h3 a")
                )
                company = name_el.get_text(strip=True) if name_el else ""
                if not company:
                    continue

                phone_el = card.select_one(".phone, .phones, [itemprop='telephone']")
                phone = phone_el.get_text(strip=True) if phone_el else ""

                addr_el = card.select_one(".address, .street-address, [itemprop='streetAddress']")
                city = ""
                if addr_el:
                    addr_text = addr_el.get_text(strip=True)
                    # 尝试提取城市名
                    city_match = re.search(r"([A-Z][a-z]+),\s*([A-Z]{2})", addr_text)
                    if city_match:
                        city = city_match.group(1)

                website_el = card.select_one("a.track-visit-website, a.website-link, a[data-link='website']")
                website = website_el.get("href", "") if website_el else ""

                leads.append(_build_lead(
                    company_name=company,
                    website=website,
                    phone=phone,
                    country=country,
                    city=city,
                    keyword=keyword,
                    source_url=url,
                ))
            except Exception as e:
                logger.debug(f"Yellow Pages 解析失败: {e}")
                continue

            _sleep()
    except Exception as e:
        logger.error(f"Yellow Pages 采集失败: {e}")

    logger.info(f"Yellow Pages 采集完成，获取 {len(leads)} 条")
    return leads


# ================================================================
#  公司网站深度挖掘
# ================================================================

def _discover_contact_pages(soup: BeautifulSoup, base_url: str) -> List[str]:
    """
    从公司网站首页探索可能的联系页面。
    查找导航中包含 "contact", "about", "about-us" 的链接。
    """
    pages = []
    contact_keywords = [
        "contact", "contact-us", "contactus", "about", "about-us",
        "get-in-touch", "reach-us", "inquiry", "quote", "request-quote",
    ]
    for a in soup.select("a[href]"):
        href = a.get("href", "").lower()
        text = a.get_text(strip=True).lower()
        for kw in contact_keywords:
            if kw in href or kw in text:
                if href.startswith("/"):
                    href = base_url.rstrip("/") + "/" + href.lstrip("/")
                elif not href.startswith("http"):
                    continue
                if href not in pages:
                    pages.append(href)
                break
    return pages[:5]  # 最多访问5个页面


def scrape_company_website(url: str) -> Dict[str, str]:
    """
    访问公司网站，提取联系信息（邮箱、电话、地址、社交账号）。
    策略：先访问首页，再探索 Contact/About 页面。
    """
    result = {
        "email": "", "email_alt": "", "phone": "", "phone_alt": "",
        "address": "", "contact_name": "", "linkedin": "", "facebook": "",
        "twitter": "", "instagram": "",
    }

    if not url or not url.startswith("http"):
        return result

    domain = _extract_domain(url)

    try:
        # 1. 访问首页
        html, status = _fetch_with_retry(url, timeout=10.0)
        if not html or status != 200:
            return result

        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)

        # 提取邮箱
        emails = _extract_emails(text, domain)
        if emails:
            result["email"] = emails[0]
            result["email_alt"] = emails[1] if len(emails) > 1 else ""

        # 提取电话
        phones = _extract_phones(text)
        if phones:
            result["phone"] = phones[0]
            result["phone_alt"] = phones[1] if len(phones) > 1 else ""

        # 提取社交媒体链接
        social = _extract_social_links(html)
        result.update(social)

        # 提取地址
        for tag in soup.select("address, .address, .contact-address, [itemprop='address'], .location, .office-address"):
            addr = tag.get_text(" ", strip=True)
            if len(addr) > 10:
                result["address"] = addr[:300]
                break

        # 2. 探索 Contact / About 页面
        contact_pages = _discover_contact_pages(soup, url)
        for cp_url in contact_pages[:3]:
            _sleep(0.3, 0.8)
            try:
                cp_html, cp_status = _fetch_with_retry(cp_url, timeout=8.0)
                if not cp_html or cp_status != 200:
                    continue

                cp_soup = BeautifulSoup(cp_html, "lxml")
                cp_text = cp_soup.get_text(" ", strip=True)

                # 补充邮箱
                if not result["email"]:
                    cp_emails = _extract_emails(cp_text, domain)
                    if cp_emails:
                        result["email"] = cp_emails[0]

                # 补充电话
                if not result["phone"]:
                    cp_phones = _extract_phones(cp_text)
                    if cp_phones:
                        result["phone"] = cp_phones[0]

                # 补充地址
                if not result["address"]:
                    for tag in cp_soup.select("address, .address, .contact-address, [itemprop='address']"):
                        addr = tag.get_text(" ", strip=True)
                        if len(addr) > 10:
                            result["address"] = addr[:300]
                            break

                # 补充社交链接
                if not all(result.get(k) for k in ["linkedin", "facebook", "twitter"]):
                    cp_social = _extract_social_links(cp_html)
                    for k, v in cp_social.items():
                        if not result.get(k):
                            result[k] = v

            except Exception as e:
                logger.debug(f"联系页面挖掘失败 {cp_url}: {e}")
                continue

    except Exception as e:
        logger.debug(f"网站挖掘失败 {url}: {e}")

    return result


# ================================================================
#  国内数据源采集（无需代理，直接可用）
# ================================================================

def search_baidu(keyword: str, max_results: int = 20) -> List[dict]:
    """
    通过百度搜索采集企业信息（境内直连，无需代理）。
    百度搜索英文关键词也能找到外贸相关企业。
    """
    leads = []
    for page in range(0, min(max_results, 30), 10):
        try:
            q = quote_plus(keyword)
            url = f"https://www.baidu.com/s?wd={q}&pn={page}&rn=10"
            logger.info(f"百度搜索: keyword={keyword}, pn={page}")

            html, status = _fetch_with_retry(url)
            if not html or status != 200:
                continue

            soup = BeautifulSoup(html, "lxml")

            for div in soup.select("div.result, div.c-container"):
                try:
                    title_el = div.select_one("h3 a, .t a")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)

                    # 百度搜索结果中的真实 URL 存储在 mu 属性或通过跳转链接
                    link = ""
                    mu = title_el.get("mu", "")
                    if mu:
                        link = mu
                    else:
                        link = title_el.get("href", "")

                    snippet_el = div.select_one(".c-abstract, .c-span-last, .content-right_8Zs40")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                    domain = _extract_domain(link)
                    if not domain:
                        continue

                    company = ""
                    for sep in [" - ", " | ", " – ", " — ", "_"]:
                        if sep in title:
                            company = _clean_company_name(title.split(sep, 1)[0])
                            break
                    if not company:
                        company = _clean_company_name(title)

                    if not company or len(company) < 3:
                        continue

                    emails = _extract_emails(snippet, domain)
                    phones = _extract_phones(snippet)

                    leads.append(_build_lead(
                        company_name=company,
                        website=link,
                        email=emails[0] if emails else "",
                        phone=phones[0] if phones else "",
                        country="China",
                        keyword=keyword,
                        source_url=url,
                        snippet=snippet,
                    ))

                    if len(leads) >= max_results:
                        break
                except Exception as e:
                    logger.debug(f"百度解析失败: {e}")
                    continue

            _sleep(0.5, 1.5)
            if len(leads) >= max_results:
                break
        except Exception as e:
            logger.error(f"百度搜索失败: {e}")
            break

    logger.info(f"百度搜索完成，采集 {len(leads)} 条线索")
    return leads


def search_1688(keyword: str, max_results: int = 20) -> List[dict]:
    """
    从 1688.com（阿里巴巴国内站）采集供应商信息。
    境内直连，无需代理。
    """
    leads = []
    try:
        q = quote_plus(keyword)
        url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={q}&n=y"
        logger.info(f"1688 采集: {url}")

        html, status = _fetch_with_retry(url)
        if not html or status != 200:
            logger.warning(f"1688 返回 {status}")
            return leads

        soup = BeautifulSoup(html, "lxml")

        # 1688 搜索结果选择器
        selectors = [
            ".sm-offer-item", ".offer-list-item", ".offer-item",
            ".list-item", ".offer_grid_item", ".imgofferresult",
        ]
        items = []
        for sel in selectors:
            items = soup.select(sel)
            if items:
                break

        for item in items[:max_results]:
            try:
                # 公司名
                company_el = (
                    item.select_one(".sm-company-name, .company-name, .supplier, .company") or
                    item.select_one("[data-company-name]")
                )
                company = company_el.get_text(strip=True) if company_el else ""
                if not company:
                    company = company_el.get("title", "") if company_el else ""

                # 产品标题
                title_el = item.select_one(".sm-offer-title, .offer-title, .title, .product-title, a[title]")
                title = title_el.get_text(strip=True) or title_el.get("title", "") if title_el else ""

                # 链接
                link_el = item.select_one("a[href*='offer'], a.sm-offer-title, a.offer-title")
                link = link_el.get("href", "") if link_el else ""
                if link and not link.startswith("http"):
                    link = "https:" + link if link.startswith("//") else "https://detail.1688.com" + link

                if not company or len(company) < 2:
                    continue

                leads.append(_build_lead(
                    company_name=company,
                    website=link,
                    country="China",
                    keyword=keyword,
                    source_url=url,
                    snippet=title,
                ))
            except Exception as e:
                logger.debug(f"1688 解析失败: {e}")
                continue

            _sleep(0.5, 1.5)
    except Exception as e:
        logger.error(f"1688 采集失败: {e}")

    logger.info(f"1688 采集完成，获取 {len(leads)} 条")
    return leads


# ================================================================
#  网络连通性预检
# ================================================================

_CONNECTIVITY_TARGETS = {
    # 国内源（无需代理，优先使用）
    "baidu": "https://www.baidu.com",
    "1688": "https://www.1688.com",
    # 境外源（需要代理）
    "google": "https://www.google.com",
    "bing": "https://www.bing.com",
    "alibaba": "https://www.alibaba.com",
    "made_in_china": "https://www.made-in-china.com",
    "yellow_pages": "https://www.yellowpages.com",
}


def check_connectivity() -> Dict[str, dict]:
    """
    快速检查各采集源的网络连通性（4 秒超时，不重试）。

    返回: { source_name: {"reachable": bool, "latency_ms": float, "error": str} }
    """
    results = {}
    for name, url in _CONNECTIVITY_TARGETS.items():
        start = time.time()
        try:
            with _get_client(_QUICK_TIMEOUT) as client:
                resp = client.get(url)
                latency = (time.time() - start) * 1000
                results[name] = {
                    "reachable": resp.status_code < 500,
                    "latency_ms": round(latency, 1),
                    "error": "" if resp.status_code < 500 else f"HTTP {resp.status_code}",
                }
        except httpx.TimeoutException:
            results[name] = {
                "reachable": False,
                "latency_ms": round((time.time() - start) * 1000, 1),
                "error": "连接超时（可能被防火墙拦截）",
            }
        except Exception as e:
            results[name] = {
                "reachable": False,
                "latency_ms": round((time.time() - start) * 1000, 1),
                "error": str(e)[:100],
            }
    return results


# ================================================================
#  统一采集入口
# ================================================================

def collect_search_engine(keyword: str, country: str = "", max_results: int = 20) -> List[dict]:
    """
    搜索引擎采集入口：优先国内源（百度），再尝试境外源（Google/Bing）。
    """
    logger.info(f"搜索引擎采集: keyword={keyword}, country={country}")

    # 快速连通性检查
    connectivity = check_connectivity()
    baidu_ok = connectivity.get("baidu", {}).get("reachable", False)
    google_ok = connectivity.get("google", {}).get("reachable", False)
    bing_ok = connectivity.get("bing", {}).get("reachable", False)
    yp_ok = connectivity.get("yellow_pages", {}).get("reachable", False)

    if not baidu_ok and not google_ok and not bing_ok and not yp_ok:
        logger.warning("所有搜索引擎均不可达")
        return []

    # 1. 优先百度（国内直连，无需代理）
    if baidu_ok:
        leads = search_baidu(keyword, max_results)
        if leads:
            logger.info(f"百度搜索成功，获取 {len(leads)} 条")
            return leads

    # 2. 尝试 Google
    if google_ok:
        leads = search_google(keyword, country, max_results)
        if leads:
            return leads
        logger.info("Google 无结果，尝试 Bing...")

    # 3. 降级到 Bing
    if bing_ok:
        leads = search_bing(keyword, country, max_results)
        if leads:
            return leads
        logger.info("Bing 无结果，尝试 Yellow Pages...")

    # 4. 降级到 Yellow Pages
    if yp_ok:
        leads = search_yellow_pages(keyword, country, max_results)
        return leads

    return []


def collect_b2b(platform: str, keyword: str, max_results: int = 20) -> List[dict]:
    """B2B 平台采集入口：优先 1688（国内），再试阿里巴巴国际站"""
    # 如果平台是 alibaba，先检查 1688 是否可用
    if platform.lower() == "alibaba":
        connectivity = check_connectivity()
        if connectivity.get("1688", {}).get("reachable", False):
            logger.info("优先使用 1688.com（国内直连）")
            leads = search_1688(keyword, max_results)
            if leads:
                return leads
        # 1688 不行再试阿里巴巴国际站
        if connectivity.get("alibaba", {}).get("reachable", False):
            leads = search_alibaba(keyword, max_results)
            return leads
        return []

    scrapers = {
        "alibaba": search_alibaba,
        "1688": search_1688,
        "globalsources": lambda k, m: [],
        "made-in-china": search_made_in_china,
        "tradekey": lambda k, m: [],
    }

    connectivity = check_connectivity()
    reachable = connectivity.get(
        "alibaba" if platform == "globalsources" else platform,
        {}
    ).get("reachable", False)

    if not reachable:
        logger.warning(f"平台 {platform} 不可达，跳过采集")
        return []

    scraper = scrapers.get(platform.lower())
    if not scraper:
        logger.warning(f"不支持的平台: {platform}")
        return []
    return scraper(keyword, max_results)


def enrich_lead_with_website(lead: dict) -> dict:
    """
    对已采集的线索，访问其公司网站提取更多联系信息。
    返回更新后的线索字典。
    """
    url = lead.get("website", "")
    if not url:
        return lead

    logger.info(f"深度挖掘网站: {url}")
    info = scrape_company_website(url)

    if info.get("email") and not lead.get("email"):
        lead["email"] = info["email"]
    if info.get("phone") and not lead.get("phone"):
        lead["phone"] = info["phone"]
    if info.get("contact_name"):
        lead["contact_name"] = info["contact_name"]
    if info.get("address"):
        lead["city"] = lead.get("city") or ""
        if not lead.get("city"):
            # 尝试从地址中提取城市
            city_match = re.search(r"([A-Z][a-z]+),\s*([A-Z]{2})", info["address"])
            if city_match:
                lead["city"] = city_match.group(1)
        lead["original_data"] = (lead.get("original_data", "") or "") + f" | Address: {info['address']}"

    # 社交链接
    social = {}
    for k in ["linkedin", "facebook", "twitter", "instagram"]:
        if info.get(k):
            social[k] = info[k]
    if social:
        lead["social_links"] = social

    return lead