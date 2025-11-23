# -*- coding: utf-8 -*-
"""
수정사항:
1. [반응형] 창 크기에 따라 좌우 분할(PC) <-> 상하 배치(모바일) 자동 전환 (st.columns 활용)
2. [입력모드] 단계형(Stepper)과 일괄형(One-page) 완벽 구현 및 상태 연동
3. [상세조건] 15개 이상의 상세 입력 필드 복원 (스타일 확장, 기차 추가 등)
4. [UX 개선] 항공 선택 시에만 좌석/수하물 옵션 노출, 키워드 placeholder 적용
5. [알고리즘] 예산, 제약조건, 스타일 매칭 로직 고도화
"""

from __future__ import annotations
import json
import random
import time
import datetime as dt
import uuid
from typing import Dict, Any, List, Tuple
import streamlit as st
import streamlit.components.v1 as components
import requests 

# ==============================================================================
# [설정] API 키 (실제 키로 교체 필요)
# ==============================================================================
KAKAO_REST_KEY = "b8d55948ead19bbcc601ef925ca2e513"
KAKAO_JS_KEY   = "386153cb9f0ff6dcd75180f93b083872"
TOUR_API_KEY   = "f00743a5b81524c48f4b77f29b01f3e5cbca2b37bca2806573aa1e86b8b0babe"

# ==============================================================================
# [SECTION 1] 백엔드 (Hybrid DB & Logic)
# ==============================================================================

class HybridDatabase:
    def get_transport_options(self, dep: str, dest: str, transport_type: str) -> Dict:
        """이동 수단별 가상 데이터 생성"""
        if transport_type == "항공":
            airlines = ["대한항공", "아시아나", "제주항공", "진에어", "티웨이"]
            return {
                "type": "항공",
                "carrier": random.choice(airlines),
                "price": random.randint(5, 15), # 편도 만원
                "duration": random.randint(50, 80), # 분
                "detail": random.choice(["이코노미", "비즈니스"])
            }
        elif transport_type == "기차":
            return {
                "type": "기차",
                "carrier": "KTX/SRT",
                "price": random.randint(4, 10),
                "duration": random.randint(120, 240),
                "detail": "일반실"
            }
        else: # 렌트카, 버스 등
            return {
                "type": transport_type,
                "carrier": "일반",
                "price": random.randint(2, 8),
                "duration": random.randint(180, 300),
                "detail": "-"
            }

    def get_accommodations(self, dest: str, min_rating: int) -> List[Dict]:
        # 숙소 Mock 데이터 (좌표 포함)
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
                    res = requests.get(kakao_url, headers=kakao_header, params={"query": f"{dest} {style}", "size": 2})
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
                    "serviceKey": TOUR_API_KEY, "numOfRows": "2", "pageNo": "1",
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
        # [매칭 알고리즘] 가중치 기반 스코어링
        score = 100
        
        # 1. 예산 페널티
        user_budget = data.get("price_per_night_manwon", 20)
        plan_price = plan['accommodation']['price_per_night']
        if plan_price > user_budget: 
            score -= min(20, (plan_price - user_budget))

        # 2. 제약 조건 페널티 (Hard Constraints)
        if data.get("barrier_free") and not plan['accommodation']['barrier_free']: score -= 30
        if data.get("with_kids") and not plan['accommodation']['kids_friendly']: score -= 20
        
        # 3. 선호 옵션 페널티 (Soft Constraints)
        if data.get("lodging_types") and plan['accommodation']['type'] not in data["lodging_types"]: score -= 15
        
        # 4. 스타일 보너스
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
            duration = (d_e - d_s).days
            if duration < 1: duration = 1
        except: duration = 3

        candidates = []
        concepts = ["가성비 최적화", "밸런스 추천", "럭셔리/프리미엄", "현지 감성"]
        
        # 사용자가 선택한 이동수단 중 하나 랜덤 배정 (없으면 항공 기본)
        user_transports = data.get("transport", ["항공"])
        if not user_transports: user_transports = ["항공"]

        accommodations = self.db.get_accommodations(dest, data.get("star_rating", 3))
        
        for i in range(4):
            selected_transport = random.choice(user_transports)
            transport_data = self.db.get_transport_options(dep, dest, selected_transport)
            
            lodge = random.choice(accommodations)
            
            # 스팟 검색 및 셔플
            all_spots = self.db.get_spots(dest, styles)
            random.shuffle(all_spots)
            
            schedule = []
            for _ in range(duration):
                if not all_spots: break
                day_spots = []
                # 하루 2~3개
                k = min(len(all_spots), 3)
                for _ in range(k): day_spots.append(all_spots.pop(0))
                schedule.append(day_spots)

            total_price = (transport_data['price'] + (lodge['price_per_night'] * duration)) * people

            plan = {
                "id": str(uuid.uuid4()),
                "concept": concepts[i],
                "match_rate": 0, # 계산 전
                "flight": transport_data, # flight 키를 쓰지만 실제론 transport info
                "accommodation": lodge,
                "schedule": schedule,
                "theme_tag": random.choice(styles) if styles else "관광",
                "total_price": total_price
            }
            plan["match_rate"] = self._calculate_match_rate(data, plan)
            candidates.append(plan)
            
        return candidates, (time.perf_counter() - start_time)

# ==============================================================================
# [SECTION 2] 지도 시각화 (Kakao Map JS)
# ==============================================================================
def draw_kakao_map(places: List[Dict]):
    if not places: return
    places_json = json.dumps(places, ensure_ascii=False)
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>html, body, #map {{ margin: 0; padding: 0; width: 100%; height: 100%; }}</style>
    </head>
    <body>
        <div id="map"></div>
        <script type="text/javascript" src="//dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JS_KEY}&libraries=services"></script>
        <script>
            var places = {places_json};
            var container = document.getElementById('map');
            var options = {{ center: new kakao.maps.LatLng(33.450701, 126.570667), level: 9 }};
            var map = new kakao.maps.Map(container, options);
            var bounds = new kakao.maps.LatLngBounds();
            var linePath = [];

            for (var i = 0; i < places.length; i++) {{
                var p = places[i];
                var latlng = new kakao.maps.LatLng(p.lat, p.lng);
                var marker = new kakao.maps.Marker({{ map: map, position: latlng, title: p.name }});
                linePath.push(latlng);
                bounds.extend(latlng);
            }}
            
            var polyline = new kakao.maps.Polyline({{
                path: linePath, strokeWeight: 5, strokeColor: '#FF3300', strokeOpacity: 0.8, strokeStyle: 'solid'
            }});
            polyline.setMap(map);

            if (places.length > 0) {{ map.setBounds(bounds); }}
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=300)

# ==============================================================================
# [SECTION 3] 프론트엔드 (UI)
# ==============================================================================
st.set_page_config(page_title="픽앤고트래블 Pro", page_icon="✈️", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.box{ border: 1px solid #e7ebf0; border-radius: 14px; padding: 20px; background: white; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 1rem;}
.hero-title{ font-weight: 800; font-size: 2.0rem; margin-top: 0.5rem; color: #14447a; text-align: center;}
.spot-link{ text-decoration: none; color: #0b5ed7; font-weight: 600; }
.spot-link:hover{ text-decoration: underline; }
img { border-radius: 8px; margin-bottom: 5px; }
.step-nav { display: flex; justify-content: space-between; margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero-title">픽앤고트래블 Pick&Go Travel</div>', unsafe_allow_html=True)

# 세션 상태 초기화 (입력값 공유를 위해)
session_keys = [
    "dep_city", "dest_city", "start_date", "end_date", "people", "companions", "budget_level",
    "style", "transport", "lodging", "star", "price", "foods", "allergy",
    "kids", "barrier", "weather", "keywords", "seat", "bag", "transfers", "step"
]
for key in session_keys:
    if key not in st.session_state:
        # 기본값 설정
        if key == "step": st.session_state[key] = 1
        elif key == "people": st.session_state[key] = 2
        elif key == "start_date": st.session_state[key] = dt.date.today() + dt.timedelta(days=7)
        elif key == "end_date": st.session_state[key] = dt.date.today() + dt.timedelta(days=10)
        elif key == "style": st.session_state[key] = ["휴양"]
        elif key == "transport": st.session_state[key] = ["항공"]
        elif key == "lodging": st.session_state[key] = ["호텔"]
        elif key == "star": st.session_state[key] = 4
        elif key == "price": st.session_state[key] = 15
        else: st.session_state[key] = None

if "candidates" not in st.session_state: st.session_state["candidates"] = []
engine = TravelEngine()

st.write("")
# 입력 모드 선택
mode = st.radio("입력 방식 선택", ["단계형(Stepper)", "일괄형(One-page)"], horizontal=True)
st.divider()

# ==============================================================================
# UI 컴포넌트 함수 (재사용을 위해 분리)
# ==============================================================================
def render_step1():
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("Step 1. 기본 정보")
    c1, c2 = st.columns(2)
    st.session_state["dep_city"] = c1.text_input("출발 도시", value=st.session_state["dep_city"] or "서울/김포")
    st.session_state["dest_city"] = c2.text_input("도착 도시", value=st.session_state["dest_city"] or "제주")
    
    c3, c4, c5 = st.columns(3)
    st.session_state["start_date"] = c3.date_input("출발일", value=st.session_state["start_date"])
    st.session_state["end_date"] = c4.date_input("도착일", value=st.session_state["end_date"])
    st.session_state["people"] = c5.number_input("인원(2~8명)", 2, 8, value=st.session_state["people"])
    
    st.session_state["companions"] = st.multiselect("동반 유형", ["커플", "가족(아동)", "친구", "혼자", "부모님"], default=st.session_state["companions"] or [])
    st.session_state["budget_level"] = st.radio("예산 수준", ["저", "중", "고"], horizontal=True, index=1)
    st.markdown('</div>', unsafe_allow_html=True)

def render_step2():
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("Step 2. 상세 조건")
    
    # [수정] 선호 스타일 확장
    style_opts = ["휴양", "관광", "맛집", "쇼핑", "자연", "액티비티", "역사", "문화", "카페", "호캉스"]
    st.session_state["style"] = st.multiselect("선호 스타일", style_opts, default=st.session_state["style"])
    
    # [수정] 기차 추가
    trans_opts = ["항공", "기차", "렌트카", "대중교통", "자가용"]
    st.session_state["transport"] = st.multiselect("이동 수단", trans_opts, default=st.session_state["transport"])
    
    st.session_state["lodging"] = st.multiselect("숙소 유형", ["호텔", "리조트", "펜션", "한옥", "게스트하우스"], default=st.session_state["lodging"])
    
    l1, l2 = st.columns(2)
    st.session_state["star"] = l1.slider("숙소 등급", 2, 5, value=st.session_state["star"])
    st.session_state["price"] = l2.slider("1박 예산(만원)", 5, 100, value=st.session_state["price"])
    
    st.session_state["foods"] = st.multiselect("음식 선호", ["미식", "현지식", "할랄", "채식", "해산물"], default=st.session_state["foods"] or [])
    st.session_state["allergy"] = st.text_input("알러지 정보", value=st.session_state["allergy"] or "")
    
    k1, k2, k3 = st.columns(3)
    st.session_state["kids"] = k1.checkbox("아이 동반", value=st.session_state["kids"])
    st.session_state["barrier"] = k2.checkbox("무장애(BF)", value=st.session_state["barrier"])
    st.session_state["weather"] = k3.checkbox("우천 시 실내 위주", value=st.session_state["weather"])
    st.markdown('</div>', unsafe_allow_html=True)

def render_step3():
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("Step 3. 옵션 & 동의")
    
    # [수정] placeholder 적용
    st.session_state["keywords"] = st.text_area("방문 희망 키워드", value=st.session_state["keywords"] or "", placeholder="예: 성산일출봉, 흑돼지, 감성카페 (콤마로 구분)")
    
    # [수정] 항공 선택 시에만 옵션 노출
    if "항공" in (st.session_state["transport"] or []):
        st.info("✈️ 항공편 이용 시 추가 옵션")
        f1, f2, f3 = st.columns(3)
        st.session_state["seat"] = f1.selectbox("좌석 선호", ["무관", "창가", "통로"], index=0)
        st.session_state["bag"] = f2.selectbox("수하물", ["기내만", "위탁 포함"], index=0)
        st.session_state["transfers"] = f3.slider("최대 환승", 0, 2, 0)
    
    st.markdown("---")
    st.caption("개인정보 보호 및 API 호출 비용 절감을 위해 정보 제공 동의가 필요합니다.")
    agree = st.checkbox("위 조건으로 추천받기 동의 *")
    st.markdown('</div>', unsafe_allow_html=True)
    return agree

# ==============================================================================
# 입력 로직 처리
# ==============================================================================
input_data = None
is_submitted = False

if mode == "일괄형(One-page)":
    # [수정] 반응형 레이아웃: 1:1 비율 (창 작으면 자동 상하 배치됨)
    left_col, right_col = st.columns([1, 1], gap="large")
    
    with left_col:
        st.markdown("#### 📝 여행 조건 입력")
        with st.form("onepage_form"):
            render_step1()
            render_step2()
            agree = render_step3()
            submitted = st.form_submit_button("🚀 추천 일정 보기", type="primary")
            
            if submitted:
                if not agree:
                    st.error("동의에 체크해주세요.")
                elif not st.session_state["dest_city"]:
                    st.error("도착 도시를 입력해주세요.")
                elif st.session_state["start_date"] > st.session_state["end_date"]:
                    st.error("도착일이 출발일보다 빠릅니다.")
                else:
                    is_submitted = True

else: # 단계형(Stepper)
    step = st.session_state["step"]
    st.markdown(f"#### 👣 Step {step} / 3")
    st.progress(step/3)
    
    if step == 1:
        render_step1()
        if st.button("다음 단계 →", type="primary"):
            st.session_state["step"] = 2
            st.rerun()
            
    elif step == 2:
        render_step2()
        c1, c2 = st.columns(2)
        if c1.button("← 이전"):
            st.session_state["step"] = 1
            st.rerun()
        if c2.button("다음 단계 →", type="primary"):
            st.session_state["step"] = 3
            st.rerun()
            
    elif step == 3:
        agree = render_step3()
        c1, c2 = st.columns(2)
        if c1.button("← 이전"):
            st.session_state["step"] = 2
            st.rerun()
        if c2.button("🚀 추천 일정 보기", type="primary"):
            if agree:
                is_submitted = True
            else:
                st.error("동의가 필요합니다.")

# ==============================================================================
# 결과 처리 및 출력
# ==============================================================================
# 일괄형의 경우 우측 컬럼, 단계형의 경우 하단에 표시
result_container = right_col if mode == "일괄형(One-page)" else st.container()

with result_container:
    if is_submitted:
        # 데이터 패키징
        input_data = {
            "dep_city": st.session_state["dep_city"], "dest_city": st.session_state["dest_city"],
            "start_date": str(st.session_state["start_date"]), "end_date": str(st.session_state["end_date"]),
            "people": st.session_state["people"], "style": st.session_state["style"],
            "transport": st.session_state["transport"], "lodging_types": st.session_state["lodging"],
            "star_rating": st.session_state["star"], "price_per_night_manwon": st.session_state["price"],
            "barrier_free": st.session_state["barrier"], "with_kids": st.session_state["kids"],
            "seat_pref": st.session_state.get("seat"), "baggage": st.session_state.get("bag"),
            "max_transfers": st.session_state.get("transfers", 0)
        }
        
        with st.spinner(f"'{input_data['dest_city']}' 여행 코스를 설계 중입니다..."):
            try:
                candidates, p_time = engine.process(input_data)
                st.session_state["candidates"] = candidates
                st.session_state["p_time"] = p_time
            except Exception as e:
                st.error(f"시스템 오류: {e}")

    # 결과 렌더링
    if st.session_state["candidates"]:
        if mode == "일괄형(One-page)":
            st.markdown("#### 🎯 추천 결과")
        else:
            st.divider()
            st.markdown("### 🎯 추천 결과")

        st.success(f"분석 완료! ({st.session_state.get('p_time', 0):.2f}초)")
        
        for idx, plan in enumerate(st.session_state["candidates"]):
            fl = plan['flight']
            acc = plan['accommodation']
            sch = plan['schedule']
            
            with st.container():
                st.markdown(f"""
                <div class="box">
                    <div style="display:flex; justify-content:space-between;">
                        <h3 style="margin:0; color:#0b5ed7;">Option {idx+1}. {plan['concept']}</h3>
                        <span style="background:#eef5ff; color:#0b5ed7; padding:4px 10px; border-radius:10px; font-weight:bold;">
                            일치율 {plan['match_rate']}%
                        </span>
                    </div>
                    <hr>
                    <div style="font-size:0.9rem; display:flex; gap:15px; flex-wrap:wrap;">
                        <div>🚆 <b>{fl['carrier']}</b> ({fl['detail']})</div>
                        <div>🏨 <b>{acc['name']}</b> ({acc['type']})</div>
                        <div>💰 총 <b>{format(plan['total_price'], ",")}만원</b></div>
                    </div>
                """, unsafe_allow_html=True)
                
                # 1일차 지도 표시
                day1 = [s for s in sch[0] if 'lat' in s]
                if day1:
                    st.caption("🗺️ 1일차 이동 경로")
                    draw_kakao_map(day1)
                
                st.markdown("<b>✨ 상세 일정</b>", unsafe_allow_html=True)
                for d_idx, day_spots in enumerate(sch):
                    st.markdown(f"**Day {d_idx+1}**")
                    cols = st.columns(len(day_spots))
                    for s_idx, spot in enumerate(day_spots):
                        with cols[s_idx]:
                            if spot.get("image"): st.image(spot["image"], use_container_width=True)
                            source = "Kakao" if spot.get("source") == "Kakao" else "TourAPI"
                            color = "orange" if source=="Kakao" else "green"
                            st.markdown(f"<span style='color:{color};font-size:0.8em;'>[{source}]</span><br><a href='{spot['url']}' target='_blank' class='spot-link'>{spot['name']}</a>", unsafe_allow_html=True)
                    st.divider()
                st.markdown("</div>", unsafe_allow_html=True)
    elif not is_submitted and mode == "일괄형(One-page)":
        st.info("조건을 입력하고 버튼을 눌러주세요.")