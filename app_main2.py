import streamlit as st
from streamlit_folium import st_folium
import folium
from datetime import date, timedelta
import datetime as dt
import random
import time
import json
import uuid
import requests
from typing import Dict, Any, List, Tuple

# [NEW] Amadeus Import
try:
    from amadeus import Client, ResponseError
except ImportError:
    st.error("amadeus 패키지가 설치되지 않았습니다. pip install amadeus를 실행해주세요.")

# ==============================================================================
# [CONFIG] API Keys & Page Setup
# ==============================================================================
# 실제 서비스 시에는 st.secrets를 사용하는 것이 좋습니다.
KAKAO_REST_KEY = "b8d55948ead19bbcc601ef925ca2e513"
TOUR_API_KEY   = "f00743a5b81524c48f4b77f29b01f3e5cbca2806573aa1e86b8b0babe"
GOOGLE_MAPS_KEY = "AIzaSyAs0N-PdsGa1ChGry_whs29u49pMzSTP-A"

# [NEW] Amadeus Keys (Placeholders)
AMADEUS_CLIENT_ID = "GjyGb5418m14v149AxCViQmKIoHP0WxA" 
AMADEUS_CLIENT_SECRET = "9TxFuldkVX3DK5Qc"

st.set_page_config(
    page_title="PickNGo | 맞춤형 여행 플래너",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==============================================================================
# [STYLE] Common CSS (Modern & Clean)
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    
    /* Headers */
    .main-header { margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 20px; }
    .title-badge { background-color: #e8f0fe; color: #1a73e8; padding: 5px 10px; border-radius: 20px; font-size: 0.9rem; font-weight: 700; }
    .highlight-title { font-size: 2.2rem; font-weight: 800; color: #202124; margin-top: 10px; }
    
    /* Section Boxes */
    .section-box {
        background-color: #ffffff;
        border-radius: 16px;
        padding: 24px;
        border: 1px solid #e1e5f0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
        margin-bottom: 24px;
    }
    .section-title { font-size: 1.3rem; font-weight: 700; margin-bottom: 16px; color: #1a73e8; }
    .section-subtitle { font-size: 0.9rem; color: #666; margin-bottom: 12px; }
    
    /* Timeline Styles */
    .timeline-container {
        position: relative; padding-left: 30px; border-left: 2px solid #e0e0e0;
        margin-left: 15px; padding-bottom: 30px;
    }
    .timeline-dot {
        position: absolute; left: -11px; top: 0; width: 20px; height: 20px;
        border-radius: 50%; background-color: #1a73e8; border: 3px solid white;
        box-shadow: 0 0 0 2px #1a73e8;
        color: white; font-size: 11px; font-weight: bold; text-align: center; line-height: 15px;
        z-index: 1;
    }
    .time-label { font-size: 0.9rem; font-weight: 700; color: #1a73e8; margin-bottom: 4px; }
    .place-title { font-size: 1.15rem; font-weight: 800; color: #202124; margin-bottom: 4px; }
    .place-desc { font-size: 0.95rem; color: #5f6368; line-height: 1.5; }
    
    /* Buttons */
    .action-btn {
        text-decoration: none; font-size: 0.85rem; font-weight: 600;
        padding: 6px 12px; border-radius: 8px; transition: all 0.2s;
        display: inline-block; border: 1px solid #dadce0; color: #3c4043; background: white;
    }
    .action-btn:hover { background-color: #f1f3f4; border-color: #dadce0; color: #202124; }
    
    /* Badges */
    .score-badge {
        display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 20px;
        font-size: 0.95rem; font-weight: 700; margin-right: 8px; margin-bottom: 8px;
        background-color: #fff; border: 1px solid #dadce0; color: #3c4043;
    }
    .score-val { color: #1a73e8; margin-left: 5px; }
    
    /* Sliders */
    .slider-label { font-weight: 600; margin-bottom: -6px; font-size: 0.9rem; color: #555; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# [LOGIC] Backend Engine (Amadeus + Hybrid)
# ==============================================================================

# [NEW] IATA Code Helper
def get_iata_code(city_name: str) -> str:
    mapping = {
        "서울": "SEL", "인천": "ICN", "김포": "GMP",
        "제주": "CJU", "부산": "PUS",
        "도쿄": "TYO", "오사카": "OSA", "후쿠오카": "FUK", "삿포로": "CTS", "오키나와": "OKA",
        "방콕": "BKK", "다낭": "DAD", "싱가포르": "SIN", "발리": "DPS",
        "파리": "PAR", "런던": "LON", "로마": "ROM", "바르셀로나": "BCN", "마드리드": "MAD",
        "뉴욕": "NYC", "LA": "LAX", "샌프란시스코": "SFO", "하와이": "HNL",
        "시드니": "SYD", "멜버른": "MEL"
    }
    return mapping.get(city_name, "ICN") # 기본값 인천

# [NEW] Flight Service
class FlightService:
    def __init__(self):
        self.client = None
        if AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET and "YOUR_" not in AMADEUS_CLIENT_ID:
            try:
                self.client = Client(
                    client_id=AMADEUS_CLIENT_ID,
                    client_secret=AMADEUS_CLIENT_SECRET
                )
            except Exception as e:
                print(f"Amadeus Init Error: {e}")

    def search_flights(self, origin: str, destination: str, departure_date: str) -> Dict:
        if not self.client:
            return None

        try:
            response = self.client.shopping.flight_offers_search.get(
                originLocationCode=get_iata_code(origin),
                destinationLocationCode=get_iata_code(destination),
                departureDate=departure_date,
                adults=1,
                max=3
            )
            
            if not response.data:
                return None

            offer = response.data[0]
            itinerary = offer['itineraries'][0]
            segment = itinerary['segments'][0]
            price = offer['price']['total']
            
            return {
                "type": "항공",
                "carrier": segment['carrierCode'],
                "flight_no": f"{segment['carrierCode']}{segment['number']}",
                "price": float(price), 
                "duration": int(itinerary['duration'][2:-1].replace('H', '60').replace('M', '')) if 'H' in itinerary['duration'] else 60,
                "detail": f"{segment['departure']['at'].split('T')[1][:5]} 출발",
                "is_real": True
            }

        except ResponseError as error:
            print(f"Amadeus API Error: {error}")
            return None
        except Exception as e:
            print(f"Flight Search Error: {e}")
            return None

# [NEW] Google Places Service (Hybrid: New & Legacy)
class GooglePlacesService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.v1_url = "https://places.googleapis.com/v1/places:searchText"
        self.legacy_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    def search_places(self, query: str) -> List[Dict]:
        if not self.api_key: return []
        
        # 1. Try New API (v1)
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.photos,places.location,places.id"
            }
            payload = {"textQuery": query, "languageCode": "ko"}
            res = requests.post(self.v1_url, json=payload, headers=headers)
            
            if res.status_code == 200:
                results = res.json().get('places', [])
                return self._parse_v1_results(results, query)
        except Exception as e:
            print(f"Google v1 Error: {e}")

        # 2. Try Legacy API (Fallback)
        try:
            params = {"query": query, "key": self.api_key, "language": "ko"}
            res = requests.get(self.legacy_url, params=params)
            if res.status_code == 200:
                results = res.json().get('results', [])
                return self._parse_legacy_results(results, query)
        except Exception as e:
            print(f"Google Legacy Error: {e}")
            
        return []

    def _parse_v1_results(self, results, query):
        places = []
        for p in results[:3]:
            img_url = f"https://source.unsplash.com/400x300/?{query.split()[-1]},{p['displayName']['text']}"
            lat = p.get('location', {}).get('latitude', 33.5)
            lng = p.get('location', {}).get('longitude', 126.5)
            places.append({
                "name": p['displayName']['text'],
                "category": "관광/맛집",
                "source": "Google(v1)",
                "url": f"https://www.google.com/maps/search/?api=1&query={lat},{lng}&query_place_id={p.get('id')}",
                "image": img_url,
                "lat": lat, "lng": lng,
                "rating": p.get('rating', 4.5)
            })
        return places

    def _parse_legacy_results(self, results, query):
        places = []
        for p in results[:3]:
            img_url = f"https://source.unsplash.com/400x300/?{query.split()[-1]},{p['name']}"
            places.append({
                "name": p['name'],
                "category": "관광/맛집",
                "source": "Google(Legacy)",
                "url": f"https://www.google.com/maps/place/?q=place_id:{p['place_id']}",
                "image": img_url,
                "lat": p['geometry']['location']['lat'],
                "lng": p['geometry']['location']['lng'],
                "rating": p.get('rating', 4.5)
            })
        return places

# [NEW] Kakao Local Service (Korea Place Search)
class KakaoLocalService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    
    def search_places(self, city: str, category: str) -> List[Dict]:
        if not self.api_key: return []
        
        try:
            query = f"{city} {category}"
            headers = {"Authorization": f"KakaoAK {self.api_key}"}
            params = {"query": query, "size": 5}
            
            res = requests.get(self.base_url, headers=headers, params=params)
            if res.status_code == 200:
                results = res.json().get('documents', [])
                places = []
                for p in results:
                    places.append({
                        "name": p['place_name'],
                        "category": category,
                        "source": "Kakao",
                        "url": p.get('place_url', '#'),
                        "image": f"https://source.unsplash.com/400x300/?{city},{p['place_name']}",
                        "lat": float(p['y']),
                        "lng": float(p['x']),
                        "rating": 4.5,
                        "address": p.get('address_name', '')
                    })
                return places
        except Exception as e:
            print(f"Kakao Local Error: {e}")
        return []

# [NEW] TourAPI Service (Korea Descriptions)
class TourAPIService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "http://apis.data.go.kr/B551011/KorService1"
    
    def get_area_based_list(self, city: str) -> List[Dict]:
        """지역 기반 관광정보 조회"""
        if not self.api_key: return []
        
        try:
            # 시/도 코드 매핑 (간단 버전)
            area_codes = {
                "서울": "1", "인천": "2", "대전": "3", "대구": "4", "광주": "5",
                "부산": "6", "울산": "7", "세종": "8", "경기": "31", "강원": "32",
                "충북": "33", "충남": "34", "경북": "35", "경남": "36", "전북": "37",
                "전남": "38", "제주": "39"
            }
            
            area_code = area_codes.get(city, "39")  # 기본값 제주
            
            params = {
                "serviceKey": self.api_key,
                "numOfRows": "10",
                "pageNo": "1",
                "MobileOS": "ETC",
                "MobileApp": "PickNGo",
                "areaCode": area_code,
                "_type": "json"
            }
            
            res = requests.get(f"{self.base_url}/areaBasedList1", params=params)
            if res.status_code == 200:
                data = res.json()
                items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                if isinstance(items, dict): items = [items]
                
                results = []
                for item in items[:5]:
                    results.append({
                        "name": item.get('title', ''),
                        "desc": item.get('overview', '관광지 설명'),
                        "image": item.get('firstimage', ''),
                        "addr": item.get('addr1', ''),
                        "lat": float(item.get('mapy', 33.5)) if item.get('mapy') else 33.5,
                        "lng": float(item.get('mapx', 126.5)) if item.get('mapx') else 126.5
                    })
                return results
        except Exception as e:
            print(f"TourAPI Error: {e}")
        return []

# [NEW] Wikipedia Service (Global Descriptions)
class WikipediaService:
    def __init__(self):
        self.base_url = "https://ko.wikipedia.org/w/api.php"
    
    def search_by_coords(self, lat: float, lng: float) -> str:
        """좌표 기반 위키백과 검색"""
        try:
            # 1. GeoSearch로 근처 문서 찾기
            params = {
                "action": "query",
                "list": "geosearch",
                "gscoord": f"{lat}|{lng}",
                "gsradius": "1000",  # 1km 반경
                "gslimit": "1",
                "format": "json"
            }
            
            res = requests.get(self.base_url, params=params)
            if res.status_code == 200:
                data = res.json()
                pages = data.get('query', {}).get('geosearch', [])
                if pages:
                    page_id = pages[0]['pageid']
                    
                    # 2. 해당 문서의 요약 가져오기
                    extract_params = {
                        "action": "query",
                        "prop": "extracts",
                        "exintro": True,
                        "explaintext": True,
                        "pageids": page_id,
                        "format": "json"
                    }
                    
                    extract_res = requests.get(self.base_url, params=extract_params)
                    if extract_res.status_code == 200:
                        extract_data = extract_res.json()
                        page_data = extract_data.get('query', {}).get('pages', {}).get(str(page_id), {})
                        extract = page_data.get('extract', '')
                        # 첫 2문장만 추출
                        sentences = extract.split('. ')[:2]
                        return '. '.join(sentences) + '.' if sentences else '역사적인 명소입니다.'
        except Exception as e:
            print(f"Wikipedia Error: {e}")
        return "유명한 관광 명소입니다."

# [HELPER] Korea City Detection
def is_korea_city(city: str) -> bool:
    """한국 도시 여부 판별"""
    korea_cities = [
        "서울", "부산", "인천", "대구", "대전", "광주", "울산", "세종",
        "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
        "수원", "성남", "고양", "용인", "청주", "천안", "전주", "포항", "창원",
        "제주도", "강릉", "속초", "경주", "여수", "통영", "거제"
    ]
    return any(k in city for k in korea_cities)

class HybridDatabase:
    def __init__(self):
        self.flight_service = FlightService()
        self.google_service = GooglePlacesService(GOOGLE_MAPS_KEY)
        self.kakao_service = KakaoLocalService(KAKAO_REST_KEY)
        self.tour_service = TourAPIService(TOUR_API_KEY)
        self.wiki_service = WikipediaService()
        
        # [NEW] Expanded Mock DB for Major Cities
        self.mock_db = {
            "바르셀로나": {
                "lat": 41.3851, "lng": 2.1734,
                "spots": [
                    {"name": "사그라다 파밀리아", "category": "관광명소", "lat": 41.4036, "lng": 2.1744, "rating": 4.9},
                    {"name": "구엘 공원", "category": "휴양/힐링", "lat": 41.4145, "lng": 2.1527, "rating": 4.7},
                    {"name": "카사 바트요", "category": "관광명소", "lat": 41.3916, "lng": 2.1649, "rating": 4.8},
                    {"name": "보케리아 시장", "category": "맛집탐방", "lat": 41.3817, "lng": 2.1715, "rating": 4.6},
                    {"name": "바르셀로네타 해변", "category": "휴양/힐링", "lat": 41.3784, "lng": 2.1925, "rating": 4.5},
                    {"name": "고딕 지구", "category": "관광명소", "lat": 41.3825, "lng": 2.1760, "rating": 4.7},
                    {"name": "카사 밀라", "category": "관광명소", "lat": 41.3954, "lng": 2.1619, "rating": 4.6},
                    {"name": "몬주익 언덕", "category": "자연풍경", "lat": 41.3635, "lng": 2.1658, "rating": 4.6},
                    {"name": "피카소 미술관", "category": "관광명소", "lat": 41.3852, "lng": 2.1809, "rating": 4.5},
                    {"name": "캄프 누 (FC바르셀로나)", "category": "액티비티", "lat": 41.3809, "lng": 2.1228, "rating": 4.8},
                    {"name": "시우타데야 공원", "category": "휴양/힐링", "lat": 41.3884, "lng": 2.1874, "rating": 4.5},
                    {"name": "El Glop (빠에야 맛집)", "category": "맛집탐방", "lat": 41.4010, "lng": 2.1560, "rating": 4.4},
                    {"name": "Cervecería Catalana", "category": "맛집탐방", "lat": 41.3923, "lng": 2.1609, "rating": 4.6},
                    {"name": "그라시아 거리 쇼핑", "category": "쇼핑", "lat": 41.3922, "lng": 2.1647, "rating": 4.5}
                ],
                "accommodations": [
                    {"name": "W 바르셀로나", "type": "호텔", "stars": 5, "price_per_night": 55, "lat": 41.3684, "lng": 2.1901},
                    {"name": "호텔 아츠 바르셀로나", "type": "호텔", "stars": 5, "price_per_night": 60, "lat": 41.3879, "lng": 2.1963},
                    {"name": "H10 카사 밈사", "type": "호텔", "stars": 4, "price_per_night": 25, "lat": 41.3967, "lng": 2.1616},
                    {"name": "호텔 1898", "type": "호텔", "stars": 4, "price_per_night": 30, "lat": 41.3833, "lng": 2.1706},
                    {"name": "제너레이터 호스텔", "type": "게스트하우스", "stars": 3, "price_per_night": 8, "lat": 41.3986, "lng": 2.1643},
                    {"name": "아이레 호텔 로셀론", "type": "호텔", "stars": 4, "price_per_night": 28, "lat": 41.4056, "lng": 2.1736}
                ]
            },
            "파리": {
                "lat": 48.8566, "lng": 2.3522,
                "spots": [
                    {"name": "에펠탑", "category": "관광명소", "lat": 48.8584, "lng": 2.2945, "rating": 4.9},
                    {"name": "루브르 박물관", "category": "관광명소", "lat": 48.8606, "lng": 2.3376, "rating": 4.8},
                    {"name": "몽마르뜨 언덕", "category": "휴양/힐링", "lat": 48.8867, "lng": 2.3431, "rating": 4.7},
                    {"name": "오르세 미술관", "category": "관광명소", "lat": 48.8600, "lng": 2.3266, "rating": 4.8},
                    {"name": "개선문", "category": "관광명소", "lat": 48.8738, "lng": 2.2950, "rating": 4.7},
                    {"name": "샹젤리제 거리", "category": "쇼핑", "lat": 48.8698, "lng": 2.3075, "rating": 4.6},
                    {"name": "노트르담 대성당", "category": "관광명소", "lat": 48.8530, "lng": 2.3499, "rating": 4.8},
                    {"name": "뤽상부르 공원", "category": "휴양/힐링", "lat": 48.8462, "lng": 2.3372, "rating": 4.7},
                    {"name": "마레 지구", "category": "쇼핑", "lat": 48.8575, "lng": 2.3590, "rating": 4.6},
                    {"name": "Le Relais de l'Entrecôte", "category": "맛집탐방", "lat": 48.8711, "lng": 2.3018, "rating": 4.5},
                    {"name": "Angelina Paris", "category": "맛집탐방", "lat": 48.8650, "lng": 2.3286, "rating": 4.6}
                ],
                "accommodations": [
                    {"name": "리츠 파리", "type": "호텔", "stars": 5, "price_per_night": 150, "lat": 48.8681, "lng": 2.3289},
                    {"name": "풀만 파리 투르 에펠", "type": "호텔", "stars": 4, "price_per_night": 45, "lat": 48.8556, "lng": 2.2916},
                    {"name": "노보텔 파리 레 알", "type": "호텔", "stars": 4, "price_per_night": 35, "lat": 48.8606, "lng": 2.3463},
                    {"name": "이비스 파리 에펠", "type": "호텔", "stars": 3, "price_per_night": 15, "lat": 48.8492, "lng": 2.3024}
                ]
            }
        }

    def get_transport_options(self, dep: str, dest: str, transport_type: str, start_date: str) -> Dict:
        if transport_type == "항공":
            real_flight = self.flight_service.search_flights(dep, dest, start_date)
            if real_flight:
                real_flight['price'] = int(float(real_flight['price']) * 0.13) 
                return real_flight

            airlines = ["대한항공", "아시아나", "제주항공", "진에어", "티웨이"]
            return {
                "type": "항공",
                "carrier": random.choice(airlines),
                "price": random.randint(5, 15),
                "duration": random.randint(50, 80),
                "detail": random.choice(["이코노미", "비즈니스"]),
                "is_real": False
            }
        
        elif transport_type == "기차":
            return {
                "type": "기차",
                "carrier": "KTX/SRT",
                "price": random.randint(4, 10),
                "duration": random.randint(120, 240),
                "detail": "일반실",
                "is_real": False
            }
        else:
            return {
                "type": transport_type,
                "carrier": "일반",
                "price": random.randint(2, 8),
                "duration": random.randint(180, 300),
                "detail": "-",
                "is_real": False
            }

    def get_accommodations(self, dest: str, min_rating: int) -> List[Dict]:
        # 1. Check Mock DB first
        if dest in self.mock_db and 'accommodations' in self.mock_db[dest]:
            return self.mock_db[dest]['accommodations']
            
        # 2. Generic Fallback
        types = ["호텔", "리조트", "펜션", "게스트하우스", "한옥"]
        names = ["그랜드", "스테이", "오션뷰", "코지", "센트럴", "헤리티지"]
        return [{
            "id": f"AC-{uuid.uuid4().hex[:4]}",
            "name": f"{random.choice(names)} {dest}",
            "type": random.choice(types),
            "stars": random.randint(min_rating, 5),
            "price_per_night": random.randint(5, 40),
            "amenities": random.sample(["수영장", "와이파이", "조식", "주차장", "BBQ"], k=3),
            "lat": 33.5 + random.random()*0.1, 
            "lng": 126.5 + random.random()*0.1
        } for _ in range(10)]

    def get_spots(self, dest: str, styles: List[str]) -> List[Dict]:
        """Hybrid Spot Search: Korea (Kakao+TourAPI) vs Global (Google+Wikipedia)"""
        result = []
        target_styles = styles if styles else ["관광명소", "맛집"]
        
        # [HYBRID LOGIC] Korea vs Global
        if is_korea_city(dest):
            # === KOREA PATH: Kakao + TourAPI ===
            print(f"[Korea Mode] Using Kakao + TourAPI for {dest}")
            
            # 1. Try Kakao Local Search
            for style in target_styles:
                kakao_places = self.kakao_service.search_places(dest, style)
                if kakao_places:
                    result.extend(kakao_places)
            
            # 2. If Kakao fails, try TourAPI
            if not result:
                tour_places = self.tour_service.get_area_based_list(dest)
                if tour_places:
                    for tp in tour_places:
                        result.append({
                            "name": tp['name'],
                            "category": "관광명소",
                            "source": "TourAPI",
                            "url": "#",
                            "image": tp.get('image') or f"https://source.unsplash.com/400x300/?{dest},{tp['name']}",
                            "lat": tp['lat'],
                            "lng": tp['lng'],
                            "rating": 4.5,
                            "desc": tp.get('desc', '관광지 설명')
                        })
        else:
            # === GLOBAL PATH: Google + Wikipedia ===
            print(f"[Global Mode] Using Google + Wikipedia for {dest}")
            
            # 1. Try Google Places API
            for style in target_styles:
                query = f"{dest} {style}"
                if style == "휴양/힐링": query = f"{dest} 공원/해변"
                elif style == "맛집탐방": query = f"{dest} 맛집"
                
                google_places = self.google_service.search_places(query)
                if google_places:
                    for gp in google_places:
                        gp['category'] = style
                        # 2. Enrich with Wikipedia
                        wiki_desc = self.wiki_service.search_by_coords(gp['lat'], gp['lng'])
                        gp['desc'] = wiki_desc
                        result.append(gp)
        
        # [FALLBACK] If all APIs fail, use Mock DB
        if not result:
            city_data = self.mock_db.get(dest)
            if city_data:
                for spot in city_data['spots']:
                    if any(s in spot['category'] for s in target_styles) or len(target_styles) == 0:
                        result.append({
                            "name": spot['name'],
                            "category": spot['category'],
                            "source": "Mock(Predefined)",
                            "url": f"https://www.google.com/maps/search/?api=1&query={spot['lat']},{spot['lng']}",
                            "image": f"https://source.unsplash.com/400x300/?{dest},{spot['name']}",
                            "lat": spot['lat'], "lng": spot['lng'],
                            "rating": spot['rating'],
                            "desc": f"{spot['name']}는 {dest}의 대표적인 {spot['category']} 명소입니다."
                        })
            else:
                # Generic Mock
                base_lat, base_lng = 37.5665, 126.9780
                if dest == "제주": base_lat, base_lng = 33.4996, 126.5312
                elif dest == "부산": base_lat, base_lng = 35.1796, 129.0756
                
                mock_names = [f"{dest} 대표 명소", f"{dest} 시내 중심가", f"{dest} 맛집 거리"]
                for i, name in enumerate(mock_names):
                    result.append({
                        "name": name,
                        "category": "기본",
                        "source": "Mock(Generic)",
                        "url": "#",
                        "image": f"https://source.unsplash.com/400x300/?{dest},travel",
                        "lat": base_lat + (random.random()-0.5)*0.05,
                        "lng": base_lng + (random.random()-0.5)*0.05,
                        "rating": 4.0,
                        "desc": f"{name}에서 {dest}의 매력을 느껴보세요."
                    })

        if not result:
             result.append({
                 "name": f"{dest} 투어 센터", 
                 "category": "기본", 
                 "source":"System", 
                 "url": "#", 
                 "image":None, 
                 "lat":37.5665, 
                 "lng":126.9780, 
                 "rating": 4.5,
                 "desc": f"{dest} 여행의 시작점입니다."
             })
        
        return result

class TravelEngine:
    def __init__(self):
        self.db = HybridDatabase()

    def _calculate_match_rate(self, data: Dict, plan: Dict) -> int:
        score = 100
        user_budget = data.get("price_per_night_manwon", 20)
        plan_price = plan['accommodation']['price_per_night']
        if plan_price > user_budget: 
            score -= min(20, (plan_price - user_budget))
            
        user_styles = set(data.get("style", []))
        if plan.get("theme_tag") in user_styles: score += 5
        
        imp_food = data.get("importance_food", 3)
        imp_sight = data.get("importance_sightseeing", 3)
        
        if "맛집" in plan.get("theme_tag", ""): score += imp_food
        if "관광" in plan.get("theme_tag", ""): score += imp_sight
        
        return max(40, min(99, score + random.randint(-2, 2)))

    def process(self, data: Dict) -> Tuple[List[Dict], float]:
        start_time = time.perf_counter()
        dest = data["dest_city"]
        dep = data.get("dep_city", "서울")
        styles = data.get("style", [])
        people = data.get("people", 2)
        
        density = data.get("schedule_density", "보통")
        spots_per_day = 2 if density == "여유" else (4 if density == "빡빡" else 3)
        
        try:
            d_s = dt.datetime.strptime(data["start_date"], "%Y-%m-%d")
            d_e = dt.datetime.strptime(data["end_date"], "%Y-%m-%d")
            duration = (d_e - d_s).days + 1
            if duration < 1: duration = 1
        except: duration = 3

        candidates = []
        concepts = ["가성비 최적화", "밸런스 추천", "럭셔리/프리미엄"]
        
        user_transports = data.get("transport", ["항공"])
        if not user_transports: user_transports = ["항공"]

        accommodations = self.db.get_accommodations(dest, data.get("star_rating", 3))
        # Shuffle accommodations to ensure variety
        random.shuffle(accommodations)
        
        for i in range(3):
            selected_transport = random.choice(user_transports)
            transport_data = self.db.get_transport_options(dep, dest, selected_transport, data["start_date"])
            
            # Ensure unique accommodation for each plan if possible
            lodge = accommodations[i % len(accommodations)]
            
            all_spots = self.db.get_spots(dest, styles)
            random.shuffle(all_spots)
            
            schedule = []
            spot_idx = 0
            for d in range(duration):
                day_spots = []
                k = min(len(all_spots) - spot_idx, spots_per_day)
                for _ in range(k): 
                    if spot_idx < len(all_spots):
                        day_spots.append(all_spots[spot_idx])
                        spot_idx += 1
                schedule.append(day_spots)

            total_price = (transport_data['price'] + (lodge['price_per_night'] * duration)) * people

            plan = {
                "id": str(uuid.uuid4()),
                "concept": concepts[i],
                "match_rate": 0,
                "flight": transport_data,
                "accommodation": lodge,
                "schedule": schedule,
                "theme_tag": random.choice(styles) if styles else "관광",
                "total_price": total_price,
                "duration": duration
            }
            plan["match_rate"] = self._calculate_match_rate(data, plan)
            candidates.append(plan)
            
        return candidates, (time.perf_counter() - start_time)

# ==============================================================================
# [HELPER] Data Adapter (Engine -> View)
# ==============================================================================
def convert_to_view_model(candidates, start_date_str):
    view_plans = []
    
    for cand in candidates:
        days = []
        for d_idx, day_spots in enumerate(cand['schedule']):
            places = []
            # 1. Accommodation (Morning)
            places.append({
                "time": "09:00",
                "name": f"{cand['accommodation']['name']} (출발)",
                "desc": "숙소에서 하루 시작",
                "type": "숙소",
                "lat": cand['accommodation']['lat'],
                "lng": cand['accommodation']['lng'],
                "rating": cand['accommodation'].get('stars', 3),
                "img": "https://source.unsplash.com/400x300/?hotel"
            })
            
            # 2. Spots
            base_time = 10
            for spot in day_spots:
                places.append({
                    "time": f"{base_time}:00",
                    "name": spot['name'],
                    "desc": f"{spot['category']} 즐기기",
                    "type": spot['category'],
                    "lat": spot['lat'],
                    "lng": spot['lng'],
                    "rating": spot.get('rating', 4.5),
                    "img": spot['image'] or f"https://source.unsplash.com/400x300/?{spot['category']}",
                    "url": spot['url']
                })
                base_time += 3
            
            days.append({"day": d_idx + 1, "places": places})
            
        view_plans.append({
            "theme_name": f"{cand['concept']} ({cand['theme_tag']})",
            "match_score": cand['match_rate'],
            "tags": [cand['theme_tag'], cand['flight']['carrier'], cand['accommodation']['type']],
            "days": days,
            "total_price": cand['total_price'],
            "raw_candidate": cand
        })
    return view_plans

# ==============================================================================
# [HELPER] Map Renderer (FOLIUM)
# ==============================================================================
def render_folium_map(markers, path_coords):
    if not markers:
        return None
    
    # Calculate Center
    avg_lat = sum([m['lat'] for m in markers]) / len(markers)
    avg_lon = sum([m['lng'] for m in markers]) / len(markers)
    
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13)
    
    # Draw Path
    if len(path_coords) > 1:
        points = [(p['lat'], p['lng']) for p in path_coords]
        folium.PolyLine(points, color="blue", weight=2.5, opacity=1).add_to(m)
    
    # Draw Markers
    for marker in markers:
        icon_color = "red" if marker.get('type') == "숙소" else "blue"
        icon = folium.Icon(color=icon_color, icon="info-sign")
        
        popup_html = f"""
        <div style="width:200px">
            <b>{marker['title']}</b><br>
            <img src="{marker['img']}" width="100%"><br>
            {marker['desc']}
        </div>
        """
        folium.Marker(
            [marker['lat'], marker['lng']],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=marker['title'],
            icon=icon
        ).add_to(m)
        
    return m

# ==============================================================================
# [MAIN] Application Flow
# ==============================================================================

# Session State Init
if "step" not in st.session_state: st.session_state["step"] = 1
if "form_data" not in st.session_state: st.session_state["form_data"] = {}
if "view_plans" not in st.session_state: st.session_state["view_plans"] = []

# --- STEP 1: INPUT FORM ---
if st.session_state["step"] == 1:
    st.markdown("""
    <div class="main-header">
        <span class="title-badge">Step 1</span>
        <div class="highlight-title">여행의 시작, 조건을 알려주세요</div>
        <p style="color:#666;">상세한 조건을 입력할수록 더 완벽한 여행 코스가 만들어집니다.</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("travel_form"):
        # Section 1: Basic Info
        st.markdown('<div class="section-box"><div class="section-title">1. 기본 정보</div>', unsafe_allow_html=True)
        c1, c2 = st.columns([3, 2])
        dest_city = c1.text_input("여행지 (도시)", placeholder="예: 바르셀로나, 파리, 도쿄")
        dep_city = c2.text_input("출발지", value="서울")
        
        c3, c4 = st.columns([2, 3])
        start_date = c3.date_input("출발일", value=date.today() + timedelta(days=7))
        end_date = c3.date_input("도착일", value=date.today() + timedelta(days=10))
        
        with c4:
            cc1, cc2 = st.columns(2)
            people = cc1.number_input("인원 수", 1, 10, 2)
            group_type = cc2.selectbox("동반 유형", ["커플", "가족(아동)", "친구", "혼자", "노년층"])
        st.markdown("</div>", unsafe_allow_html=True)

        # Section 2: Style & Budget
        st.markdown('<div class="section-box"><div class="section-title">2. 예산 및 여행 스타일</div>', unsafe_allow_html=True)
        c5, c6 = st.columns(2)
        with c5:
            budget_level = st.selectbox("예산 수준 (1인 기준)", ["저가", "중가", "고가"], index=1)
            transport = st.multiselect("이동 수단 선호", ["항공", "기차", "렌트카", "대중교통"], default=["항공"])
            schedule_density = st.select_slider("일정 밀도", options=["여유", "보통", "빡빡"], value="보통")
        
        with c6:
            styles = st.multiselect("여행 테마", ["관광명소", "휴양/힐링", "맛집탐방", "쇼핑", "액티비티", "자연풍경"], default=["휴양/힐링", "맛집탐방"])
            stay_type = st.multiselect("숙소 유형", ["호텔", "리조트", "펜션", "게스트하우스"], default=["호텔"])
            stay_grade = st.selectbox("숙소 등급/예산", ["2~3성/5만원이하", "3~4성/10만원이하", "4~5성/20만원이하", "럭셔리/20만원이상"], index=1)
        st.markdown("</div>", unsafe_allow_html=True)

        # Section 3: Importance Weights
        st.markdown('<div class="section-box"><div class="section-title">3. 중요도 설정 (가중치)</div><div class="section-subtitle">0~5점 (5점이 가장 중요)</div>', unsafe_allow_html=True)
        c7, c8, c9 = st.columns(3)
        with c7:
            st.markdown('<div class="slider-label">예산</div>', unsafe_allow_html=True)
            imp_budget = st.slider("budget", 0, 5, 3, label_visibility="collapsed")
            st.markdown('<div class="slider-label">휴양/여유</div>', unsafe_allow_html=True)
            imp_rest = st.slider("rest", 0, 5, 3, label_visibility="collapsed")
        with c8:
            st.markdown('<div class="slider-label">관광/명소</div>', unsafe_allow_html=True)
            imp_sight = st.slider("sight", 0, 5, 4, label_visibility="collapsed")
            st.markdown('<div class="slider-label">맛집</div>', unsafe_allow_html=True)
            imp_food = st.slider("food", 0, 5, 3, label_visibility="collapsed")
        with c9:
            st.markdown('<div class="slider-label">쇼핑</div>', unsafe_allow_html=True)
            imp_shop = st.slider("shop", 0, 5, 2, label_visibility="collapsed")
            st.markdown('<div class="slider-label">액티비티</div>', unsafe_allow_html=True)
            imp_act = st.slider("act", 0, 5, 2, label_visibility="collapsed")
        st.markdown("</div>", unsafe_allow_html=True)

        # Section 4: Details
        st.markdown('<div class="section-box"><div class="section-title">4. 상세 조건</div>', unsafe_allow_html=True)
        c10, c11 = st.columns(2)
        with c10:
            food_prefs = st.multiselect("음식 선호/제약", ["미식 위주", "할랄", "채식", "해산물 선호", "알러지 있음"])
            walk_tolerance = st.slider("도보 허용 시간 (분)", 10, 120, 40)
        with c11:
            wishlist = st.text_area("방문 희망 키워드", placeholder="예: 에펠탑, 미슐랭, 루프탑 바")
        st.markdown("</div>", unsafe_allow_html=True)

        submitted = st.form_submit_button("🚀 여행 코스 생성하기", use_container_width=True, type="primary")

        if submitted:
            if not dest_city:
                st.error("여행지를 입력해주세요!")
            else:
                st.session_state["form_data"] = {
                    "dest_city": dest_city,
                    "dep_city": dep_city,
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "people": people,
                    "group_type": group_type,
                    "budget_level": budget_level,
                    "transport": transport,
                    "schedule_density": schedule_density,
                    "style": styles,
                    "lodging_types": stay_type,
                    "stay_grade": stay_grade,
                    "importance_food": imp_food,
                    "importance_sightseeing": imp_sight,
                    "food_prefs": food_prefs,
                    "walk_tolerance": walk_tolerance,
                    "wishlist": wishlist,
                    "star_rating": 3 if "2~3" in stay_grade else (4 if "3~4" in stay_grade else 5),
                    "price_per_night_manwon": 5 if "5만원" in stay_grade else (10 if "10만원" in stay_grade else (20 if "20만원" in stay_grade else 50))
                }
                st.session_state["step"] = 2
                st.rerun()

# --- STEP 2: PROCESSING ---
elif st.session_state["step"] == 2:
    with st.status("✈️ 여행 코스를 설계하고 있습니다...", expanded=True) as status:
        st.write("🔍 여행지 정보를 분석 중입니다...")
        time.sleep(1)
        st.write("🏨 최적의 숙소와 항공편을 찾고 있습니다...")
        
        engine = TravelEngine()
        candidates, p_time = engine.process(st.session_state["form_data"])
        
        st.write("✨ 코스 최적화 중...")
        view_plans = convert_to_view_model(candidates, st.session_state["form_data"]["start_date"])
        st.session_state["view_plans"] = view_plans
        
        status.update(label="✅ 설계가 완료되었습니다!", state="complete", expanded=False)
        time.sleep(1)
        st.session_state["step"] = 3
        st.rerun()

# --- STEP 3: OUTPUT VIEW ---
elif st.session_state["step"] == 3:
    data = st.session_state["form_data"]
    plans = st.session_state["view_plans"]

    # Header
    c1, c2 = st.columns([8, 2])
    with c1:
        st.markdown(f"""
            <div class="main-header">
                <span class="title-badge">Result</span>
                <div class="highlight-title">{data['dest_city']} 맞춤 여행 브리핑</div>
                <p style="color:#666;">{data['start_date']} ~ {data['end_date']} · {data['people']}명 ({data['group_type']})</p>
            </div>
        """, unsafe_allow_html=True)
    with c2:
        if st.button("🔄 다시 입력하기"):
            st.session_state["step"] = 1
            st.rerun()

    # Tabs for Plans
    tabs = st.tabs([p["theme_name"] for p in plans])
    
    for i, tab in enumerate(tabs):
        plan = plans[i]
        with tab:
            # Summary Badge
            st.markdown(f"""
            <div style='margin: 15px 0;'>
                <span class="score-badge">🎯 적합도 <span class="score-val">{plan['match_score']}%</span></span>
                <span class="score-badge">💰 예상 비용 <span class="score-val">{format(int(plan['total_price']), ",")}만원</span></span>
                {' '.join([f'<span class="score-badge">#{t}</span>' for t in plan['tags']])}
            </div>
            """, unsafe_allow_html=True)

            # Map Data Prep
            map_markers = []
            map_path = []
            for day in plan['days']:
                for place in day['places']:
                    if place.get('lat') and place.get('lng'):
                        map_markers.append({
                            "lat": place['lat'], "lng": place['lng'],
                            "title": place['name'],
                            "img": place['img'],
                            "rating": place['rating'],
                            "desc": place['desc'],
                            "type": place['type']
                        })
                        map_path.append({"lat": place['lat'], "lng": place['lng']})
            
            # [FIX] Render Folium Map
            m = render_folium_map(map_markers, map_path)
            if m:
                st_folium(m, width="100%", height=500)
            else:
                st.warning("지도 데이터를 불러올 수 없습니다.")
            
            st.divider()

            # Timeline
            for day in plan['days']:
                with st.expander(f"🗓️ Day {day['day']} 일정 보기", expanded=True):
                    for p_idx, place in enumerate(day['places']):
                        is_last = (p_idx == len(day['places']) - 1)
                        st.markdown(f"""
                        <div class="timeline-container" style="{'border-left:none;' if is_last else ''}">
                            <div class="timeline-dot">{p_idx+1}</div>
                            <div class="time-label">{place['time']} · {place['type']}</div>
                            <div class="place-title">{place['name']}</div>
                            <div class="place-desc">{place['desc']}</div>
                        </div>
                        """, unsafe_allow_html=True)

            # Reservation Action
            st.divider()
            if st.button(f"⚡ '{plan['theme_name']}' 코스로 예약하기", key=f"book_{i}", type="primary", use_container_width=True):
                st.balloons()
                st.success("🎉 예약 요청이 접수되었습니다! 상담원이 곧 연락드립니다.")
