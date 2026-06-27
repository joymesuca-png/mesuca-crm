"""
外贸获客系统 - 模拟数据生成器（降级方案）

当真实网络采集不可用时，自动生成符合行业特征的模拟线索。
数据尽可能贴近真实场景，用于系统演示和测试。
"""
import random
from datetime import datetime, UTC
from typing import List


# ── 地区数据 ──
_CITIES = {
    "USA": ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Miami", "Seattle", "Boston", "Dallas", "Atlanta"],
    "UK": ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Bristol", "Liverpool", "Sheffield"],
    "Germany": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne", "Stuttgart", "Düsseldorf"],
    "France": ["Paris", "Lyon", "Marseille", "Toulouse", "Bordeaux", "Lille", "Nice"],
    "Japan": ["Tokyo", "Osaka", "Nagoya", "Yokohama", "Kyoto", "Fukuoka", "Sapporo"],
    "Canada": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa", "Edmonton"],
    "Australia": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Gold Coast"],
    "Brazil": ["Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador", "Fortaleza"],
    "India": ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune"],
    "Korea": ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon"],
    "Italy": ["Milan", "Rome", "Turin", "Naples", "Florence"],
    "Spain": ["Madrid", "Barcelona", "Valencia", "Seville", "Bilbao"],
    "Netherlands": ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven"],
    "default": ["International City"],
}

_FIRST_NAMES = [
    "James", "Sarah", "Michael", "Emma", "David", "Lisa", "Robert", "Anna",
    "Daniel", "Sophia", "Thomas", "Olivia", "William", "Emily", "Kevin", "Grace",
    "Ryan", "Linda", "Jason", "Jessica", "Brian", "Amanda", "Chris", "Nancy",
    "Steven", "Michelle", "Mark", "Laura", "Paul", "Jennifer", "Andrew", "Rebecca",
]

_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Wilson", "Taylor",
    "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Thompson",
    "Garcia", "Martinez", "Robinson", "Clark", "Lewis", "Lee", "Walker", "Hall",
    "Young", "King", "Wright", "Scott", "Green", "Adams", "Baker", "Nelson",
]

_CO_SUFFIX = {
    "USA": ["Inc.", "LLC", "Corp.", "Ltd.", "Group", "Enterprises"],
    "UK": ["Ltd.", "PLC", "Group", "Holdings", "International"],
    "Germany": ["GmbH", "AG", "KG", "Group", "International"],
    "France": ["SARL", "SAS", "SA", "Group", "International"],
    "Japan": ["Co., Ltd.", "KK", "Corp.", "Group", "International"],
    "default": ["Co., Ltd.", "Group", "International", "Trading", "Corp.", "Import & Export"],
}

# 行业关键词映射（与 scraper.py 保持一致）
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


def _gen_company_name(keyword: str) -> str:
    """根据关键词生成相关的公司名"""
    kw = keyword.strip().title()
    patterns = [
        f"{kw} {random.choice(['International', 'Group', 'Trading', 'Industries', 'Products', 'Solutions', 'Hub', 'Zone', 'World', 'Direct', 'Express', 'Pro', 'Elite', 'Premium', 'Global', 'Supply', 'Link', 'Plus', 'Max', 'Star'])}",
        f"{random.choice(['Best', 'Prime', 'Apex', 'Nova', 'Ultra', 'Mega', 'Top', 'First', 'Royal', 'Sunrise', 'Pacific', 'Atlantic', 'Golden', 'Silver', 'Diamond', 'Crystal', 'Bright', 'Smart', 'Eco', 'True'])} {kw}",
        f"{kw} {random.choice(['Source', 'Line', 'Net', 'Way', 'Port', 'Trade', 'Mart', 'Expo'])}",
        f"{random.choice(['New', 'Modern', 'Advanced', 'Creative', 'Dynamic', 'United', 'Superior', 'Innovative'])} {kw}",
        f"{kw} {random.choice(['Manufacturing', 'Trading', 'Import & Export', 'Distribution', 'Supply Chain'])}",
    ]
    return f"{random.choice(patterns)} {random.choice(_CO_SUFFIX['default'])}"


def simulate_search_results(keyword: str, country: str, source_id: int, count: int) -> List[dict]:
    """生成模拟搜索引擎采集结果"""
    countries = [country] if country and country in _CITIES else list(_CITIES.keys() - {"default"})
    industry = _guess_industry(keyword)
    batch_id = datetime.now(UTC).strftime("%m%d%H%M") + str(random.randint(100, 999))
    results = []

    for i in range(count):
        c = random.choice(list(countries))
        comp_name = _gen_company_name(keyword)
        first = random.choice(_FIRST_NAMES)
        last = random.choice(_LAST_NAMES)
        contact = f"{first} {last}"
        email_slug = keyword.lower().replace(" ", "")[:10]
        domain = comp_name.lower().split()[0]
        email = f"{first.lower()}.{last.lower()}.{email_slug}{batch_id}.{i}@{domain}.com"
        cities = _CITIES.get(c, _CITIES["default"])

        results.append({
            "company_name": comp_name,
            "contact_name": contact,
            "email": email,
            "phone": f"+1-{random.randint(200, 999)}-{random.randint(1000, 9999)}",
            "website": f"https://www.{domain}.com",
            "country": c,
            "city": random.choice(cities),
            "industry": industry,
            "product_interest": keyword,
            "lead_score": round(random.uniform(40, 95), 1),
            "source_id": source_id,
            "source_url": f"https://www.google.com/search?q={keyword}",
            "status": "new",
            "original_data": f"模拟数据: {keyword} {industry}",
        })
    return results


def simulate_b2b_results(platform: str, keyword: str, source_id: int, count: int) -> List[dict]:
    """生成模拟 B2B 平台采集结果"""
    results = simulate_search_results(keyword, "China", source_id, count)
    for r in results:
        r["source_url"] = f"https://www.{platform}.com/search?q={keyword}"
        r["lead_score"] = round(random.uniform(50, 90), 1)
    return results