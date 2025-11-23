import streamlit as st
import streamlit.components.v1 as components
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
KAKAO_JS_KEY   = "386153cb9f0ff6dcd75180f93b083872"
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
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# [LOGIC] Backend Engine (Amadeus + Hybrid)
# ==============================================================================

# [NEW] IATA Code Helper
def get_iata_code(city_name: str) -> str:
    # 간단한 매핑 (실제로는 더 많은 도시 필요)
    mapping = {
        "서울": "SEL", "인천": "ICN", "김포": "GMP",
        "제주": "CJU", "부산": "PUS",
        "도쿄": "TYO", "오사카": "OSA", "후쿠오카": "FUK",
        "방콕": "BKK", "다낭": "DAD", "싱가포르": "SIN",
        "파리": "PAR", "런던": "LON", "뉴욕": "NYC"
    }
    return mapping.get(city_name, "ICN") # 기본값 인천

# [NEW] Flight Service
class FlightService:
    def __init__(self):
        self.client = None
        # 키가 설정되어 있고 기본값이 아닐 때만 초기화
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

            # 첫 번째 결과만 파싱 (간소화)
            offer = response.data[0]
            itinerary = offer['itineraries'][0]
            segment = itinerary['segments'][0]
            price = offer['price']['total']
            
            return {
                "type": "항공",
                "carrier": segment['carrierCode'], # 항공사 코드 (예: KE)
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

class HybridDatabase:
    def __init__(self):
        self.flight_service = FlightService()

    def get_transport_options(self, dep: str, dest: str, transport_type: str, start_date: str) -> Dict:
        """이동 수단별 데이터 생성 (Amadeus 연동)"""
        
        # 1. 항공이고 Amadeus 연동 가능하면 시도
        if transport_type == "항공":
            real_flight = self.flight_service.search_flights(dep, dest, start_date)
            if real_flight:
                # 환율 대략 적용 (1 EUR/USD = 1300 KRW 가정하여 만원 단위로 변환)
                real_flight['price'] = int(float(real_flight['price']) * 0.13) 
                return real_flight

            # Fallback to Mock
            airlines = ["대한항공", "아시아나", "제주항공", "진에어", "티웨이"]
            return {
                "type": "항공",
                "carrier": random.choice(airlines),
                "price": random.randint(5, 15), # 편도 만원
                "duration": random.randint(50, 80), # 분
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
        else: # 렌트카, 버스 등
            return {
                "type": transport_type,
                "carrier": "일반",
                "price": random.randint(2, 8),
                "duration": random.randint(180, 300),
                "detail": "-",
                "is_real": False
            }

    def get_accommodations(self, dest: str, min_rating: int) -> List[Dict]:
        # 숙소 Mock 데이터
        types = ["호텔", "리조트", "펜션", "게스트하우스", "한옥"]
        names = ["그랜드", "스테이", "오션뷰", "코지", "센트럴", "헤리티지"]
        return [{
            "id": f"AC-{uuid.uuid4().hex[:4]}",
            "name": f"{random.choice(names)} {dest}",
            "type": random.choice(types),
            "stars": random.randint(min_rating, 5),
            "price_per_night": random.randint(5, 40),
            "amenities": random.sample(["수영장", "와이파이", "조식", "주차장", "BBQ"], k=3),
            "barrier_free": random.choice([True, False]),
            "kids_friendly": random.choice([True, False]),
            "lat": 33.5 + random.random()*0.1, 
            "lng": 126.5 + random.random()*0.1
        } for _ in range(20)]

    def get_spots(self, dest: str, styles: List[str]) -> List[Dict]:
        """Kakao(맛집/쇼핑) + TourAPI(관광/자연) 하이브리드 검색"""
        result = []
        target_styles = styles if styles else ["관광명소", "맛집"]
        
        kakao_header = {"Authorization": f"KakaoAK {KAKAO_REST_KEY}"}
        kakao_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        tour_url = "http://apis.data.go.kr/B551011/KorService1/searchKeyword1"
        
        for style in target_styles:
            # 1. Kakao API: 맛집, 쇼핑, 카페
            if style in ["맛집", "쇼핑", "카페", "식도락"]:
                try:
                    res = requests.get(kakao_url, headers=kakao_header, params={"query": f"{dest} {style}", "size": 3})
                    if res.status_code == 200:
                        for p in res.json().get('documents', []):
                            result.append({
                                "name": p['place_name'],
                                "category": style,
                                "source": "Kakao",
                                "url": p['place_url'],
                                "image": None,
                                "lat": float(p['y']), "lng": float(p['x'])
                            })
                except: pass
            
            # 2. TourAPI: 관광, 자연, 역사, 문화 등
            else:
                keyword = f"{dest} {style}"
                if style == "휴양": keyword = f"{dest} 힐링"
                
                params = {
                    "serviceKey": TOUR_API_KEY, "numOfRows": "3", "pageNo": "1",
                    "MobileOS": "ETC", "MobileApp": "PickNGo", "_type": "json",
                    "listYN": "Y", "arrange": "O", "keyword": keyword
                }
                try:
                    res = requests.get(tour_url, params=params)
                    if res.status_code == 200:
                        items = res.json()['response']['body']['items']['item']
                        for item in items:
                            if item.get('mapx') and item.get('mapy'):
                                result.append({
                                    "name": item.get('title'),
                                    "category": style,
                                    "source": "TourAPI",
                                    "url": f"https://map.kakao.com/link/search/{item.get('title')}",
                                    "image": item.get('firstimage'),
                                    "lat": float(item.get('mapy')), "lng": float(item.get('mapx'))
                                })
                except: pass
        
        if not result: # 데이터 없을 경우 대비
            result.append({"name": f"{dest} 투어 센터", "category": "기본", "source":"System", "url": "#", "image":None, "lat":33.5, "lng":126.5})
        return result

class TravelEngine:
    def __init__(self):
        self.db = HybridDatabase()

    def _calculate_match_rate(self, data: Dict, plan: Dict) -> int:
        score = 100
        # 예산 페널티
        user_budget = data.get("price_per_night_manwon", 20)
        plan_price = plan['accommodation']['price_per_night']
        if plan_price > user_budget: 
            score -= min(20, (plan_price - user_budget))
        # 스타일 보너스
        user_styles = set(data.get("style", []))
        if plan.get("theme_tag") in user_styles: score += 5
        return max(40, min(99, score + random.randint(-2, 2)))

    def process(self, data: Dict) -> Tuple[List[Dict], float]:
        start_time = time.perf_counter()
        dest = data["dest_city"]
        dep = data.get("dep_city", "서울")
        styles = data.get("style", [])
        people = data.get("people", 2)
        
        # 날짜 계산
        try:
            d_s = dt.datetime.strptime(data["start_date"], "%Y-%m-%d")
            d_e = dt.datetime.strptime(data["end_date"], "%Y-%m-%d")
            duration = (d_e - d_s).days + 1
            if duration < 1: duration = 1
        except: duration = 3

        candidates = []
        concepts = ["가성비 최적화", "밸런스 추천", "럭셔리/프리미엄", "현지 감성"]
        
        user_transports = data.get("transport", ["항공"])
        if not user_transports: user_transports = ["항공"]

        accommodations = self.db.get_accommodations(dest, data.get("star_rating", 3))
        
        for i in range(3): # 3개 옵션 생성
            selected_transport = random.choice(user_transports)
            
            # [MODIFIED] Pass start_date to get_transport_options
            transport_data = self.db.get_transport_options(dep, dest, selected_transport, data["start_date"])
            
            lodge = random.choice(accommodations)
            
            # 스팟 검색 및 셔플
            all_spots = self.db.get_spots(dest, styles)
            random.shuffle(all_spots)
            
            schedule = []
            spot_idx = 0
            for d in range(duration):
                day_spots = []
                # 하루 2~3개
                k = min(len(all_spots) - spot_idx, 3)
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
    """TravelEngine의 출력을 app_3.py의 시각화 포맷으로 변환"""
    view_plans = []
    start_date = dt.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    
    for cand in candidates:
        days = []
        for d_idx, day_spots in enumerate(cand['schedule']):
            places = []
            # 1. 숙소 (아침)
            places.append({
                "time": "09:00",
                "name": f"{cand['accommodation']['name']} (출발)",
                "desc": "숙소에서 하루 시작",
                "type": "숙소",
                "lat": cand['accommodation']['lat'],
                "lng": cand['accommodation']['lng'],
                "rating": cand['accommodation']['stars'],
                "img": "https://source.unsplash.com/400x300/?hotel"
            })
            
            # 2. 스팟들
            base_time = 10
            for spot in day_spots:
                places.append({
                    "time": f"{base_time}:00",
                    "name": spot['name'],
                    "desc": f"{spot['category']} 즐기기",
                    "type": spot['category'],
                    "lat": spot['lat'],
                    "lng": spot['lng'],
                    "rating": 4.5,
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
            "raw_candidate": cand # 원본 데이터 보존
        })
    return view_plans

# ==============================================================================
# [HELPER] Map Renderer
# ==============================================================================
def render_kakao_map_html(markers, path_coords):
    if not markers: return "<div>지도 데이터가 없습니다.</div>"
    
    avg_lat = sum([m['lat'] for m in markers]) / len(markers)
    avg_lon = sum([m['lng'] for m in markers]) / len(markers)
    markers_json = json.dumps(markers)
    path_json = json.dumps(path_coords)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            html, body {{ margin: 0; padding: 0; height: 100%; }}
            #map {{ width: 100%; height: 500px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
            .wrap {{ position: absolute; left: 0; bottom: 40px; width: 288px; height: 132px; margin-left: -144px; text-align: left; overflow: hidden; font-size: 12px; font-family: 'Pretendard', sans-serif; line-height: 1.5; }}
            .wrap * {{ padding: 0; margin: 0; }}
            .wrap .info {{ width: 286px; height: 120px; border-radius: 5px; border-bottom: 2px solid #ccc; border-right: 1px solid #ccc; overflow: hidden; background: #fff; box-shadow: 0 1px 2px #888; }}
            .info .title {{ padding: 5px 0 0 10px; height: 30px; background: #eee; border-bottom: 1px solid #ddd; font-size: 14px; font-weight: bold; color: #333; display: flex; justify-content: space-between; align-items: center; }}
            .info .body {{ position: relative; overflow: hidden; display: flex; padding: 10px; }}
            .info .img {{ width: 73px; height: 70px; border: 1px solid #ddd; color: #888; overflow: hidden; margin-right: 10px; }}
            .info .img img {{ width: 100%; height: 100%; object-fit: cover; }}
            .info .desc {{ flex: 1; }}
            .desc .ellipsis {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #333; font-size: 13px; font-weight: 600; }}
            .desc .rating {{ color: #1a73e8; font-weight: 700; margin-top: 4px; }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script type="text/javascript" src="//dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JS_KEY}"></script>
        <script>
            var container = document.getElementById('map');
            var options = {{ center: new kakao.maps.LatLng({avg_lat}, {avg_lon}), level: 9 }};
            var map = new kakao.maps.Map(container, options);
            var markersData = {markers_json};
            var pathData = {path_json};

            var linePath = [];
            pathData.forEach(function(p) {{ linePath.push(new kakao.maps.LatLng(p.lat, p.lng)); }});
            var polyline = new kakao.maps.Polyline({{ path: linePath, strokeWeight: 5, strokeColor: '#1A73E8', strokeOpacity: 0.8, strokeStyle: 'solid' }});
            polyline.setMap(map);

            var overlays = [];
            markersData.forEach(function(m, index) {{
                var position = new kakao.maps.LatLng(m.lat, m.lng);
                var marker = new kakao.maps.Marker({{ map: map, position: position }});
                
                var content = `
                    <div class="wrap">
                        <div class="info">
                            <div class="title">${{(index+1) + '. ' + m.title}}</div>
                            <div class="body">
                                <div class="img"><img src="${{m.img}}" width="73" height="70"></div>
                                <div class="desc">
                                    <div class="rating">⭐ ${{m.rating}}</div>
                                    <div class="jibun">${{m.desc.substring(0, 30) + '...'}}</div>
                                </div>
                            </div>
                        </div>
                    </div>`;
                var overlay = new kakao.maps.CustomOverlay({{ content: content, map: null, position: marker.getPosition() }});
                overlays.push(overlay);

                kakao.maps.event.addListener(marker, 'click', function() {{
                    overlays.forEach(o => o.setMap(null));
                    overlay.setMap(map);
                }});
                kakao.maps.event.addListener(map, 'click', function() {{ overlay.setMap(null); }});
            }});
        </script>
    </body>
    </html>
    """
    return html

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
        <p style="color:#666;">원하는 여행 스타일을 입력하면 AI가 최적의 코스를 설계해드립니다.</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("travel_form"):
        # Section 1: Basic Info
        st.markdown('<div class="section-box"><div class="section-title">1. 기본 정보</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        dest_city = c1.text_input("여행지 (도시)", placeholder="예: 제주, 부산, 도쿄")
        dep_city = c2.text_input("출발지", value="서울")
        
        c3, c4, c5 = st.columns(3)
        start_date = c3.date_input("출발일", value=date.today() + timedelta(days=7))
        end_date = c4.date_input("도착일", value=date.today() + timedelta(days=10))
        people = c5.number_input("인원 수", 1, 10, 2)
        st.markdown("</div>", unsafe_allow_html=True)

        # Section 2: Style & Budget
        st.markdown('<div class="section-box"><div class="section-title">2. 스타일 및 예산</div>', unsafe_allow_html=True)
        c6, c7 = st.columns(2)
        with c6:
            budget_level = st.select_slider("예산 수준", options=["알뜰", "가성비", "럭셔리"], value="가성비")
            transport = st.multiselect("이동 수단", ["항공", "기차", "렌트카", "대중교통"], default=["항공"])
        with c7:
            styles = st.multiselect("여행 테마 (복수 선택)", ["관광명소", "휴양/힐링", "맛집탐방", "쇼핑", "액티비티", "자연풍경"], default=["휴양/힐링", "맛집탐방"])
            stay_type = st.multiselect("숙소 유형", ["호텔", "리조트", "펜션", "게스트하우스"], default=["호텔"])
        
        st.markdown("</div>", unsafe_allow_html=True)

        submitted = st.form_submit_button("🚀 여행 코스 생성하기", use_container_width=True, type="primary")

        if submitted:
            if not dest_city:
                st.error("여행지를 입력해주세요!")
            else:
                # Save to session
                st.session_state["form_data"] = {
                    "dest_city": dest_city,
                    "dep_city": dep_city,
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "people": people,
                    "budget_level": budget_level,
                    "transport": transport,
                    "style": styles,
                    "lodging_types": stay_type,
                    "star_rating": 3 if budget_level == "알뜰" else (4 if budget_level == "가성비" else 5),
                    "price_per_night_manwon": 10 if budget_level == "알뜰" else (20 if budget_level == "가성비" else 50)
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
        # Convert to View Model
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
                <p style="color:#666;">{data['start_date']} ~ {data['end_date']} · {data['people']}명</p>
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

            # Map
            map_markers = []
            map_path = []
            for day in plan['days']:
                for place in day['places']:
                    map_markers.append({
                        "lat": place['lat'], "lng": place['lng'],
                        "title": place['name'],
                        "img": place['img'],
                        "rating": place['rating'],
                        "desc": place['desc']
                    })
                    map_path.append({"lat": place['lat'], "lng": place['lng']})
            
            components.html(render_kakao_map_html(map_markers, map_path), height=450)
            
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
