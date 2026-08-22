import streamlit as st
import pandas as pd
import io
import math
import matplotlib.pyplot as plt
from geopy.geocoders import Nominatim # 주소 변환 라이브러리

st.set_page_config(page_title="사외매설배관 간섭 검토 시스템", layout="wide")
st.title("🚧 지하 매설배관 굴착공사 간섭 검토 프로그램")

# --- (UI 입력 부분은 이전과 동일하므로 생략. 아래는 분석 버튼 클릭 이후 로직) ---
is_agreed = st.checkbox("네, 위 주의사항을 확인했으며 해당 양식에 맞게 파일을 준비했습니다.")
contractor_file = st.file_uploader("굴착 공사 구간 CAD 파일 업로드 (.dxf)", type=['dxf'])

if is_agreed and contractor_file and st.button("간섭 및 이격거리 분석 실행"):
    with st.spinner("데이터 분석 및 도면 시각화 생성 중..."):
        
        # 1. 주변 시설물 더미 데이터 (실제로는 '2. 시설물' Layer에서 추출)
        facilities = [
            {"name": "통신맨홀", "x": 120, "y": 150},
            {"name": "가스밸브", "x": 240, "y": 260}
        ]
        
        # 2. 교차점 더미 데이터 (CAD 좌표 X,Y 및 위경도 포함)
        clash_points = [
            {"id": "P-1", "x": 100, "y": 100, "lon": 126.7403398, "lat": 37.31553271, "d_center": 250.0, "company_depth": 1500.0, "r_comp": 108.15}
        ]
        
        report_data = []
        r_cont = 161.0 / 2 # 업체 배관 외경 절반 (테스트용)
        contractor_depth = 500.0 # 업체 심도 (테스트용)
        
        # 주소 변환기 초기화
        geolocator = Nominatim(user_agent="pipe_checker")
        
        for cp in clash_points:
            # --- 이격거리 판정 로직 ---
            d_actual = cp["d_center"] - (cp["r_comp"] + r_cont)
            delta_z_adjusted = abs((contractor_depth + r_cont) - cp["company_depth"])
            
            if d_actual > 300: status = "✅ 간섭없음"
            elif d_actual <= 300 and delta_z_adjusted >= 300: status = "⚠️ 간섭 (보호테이프 노출)"
            else: status = "🚨 간섭 (배관 영향 있음)"
            
            # --- 위경도를 주소로 변환 ---
            try:
                location = geolocator.reverse((cp["lat"], cp["lon"]), exactly_one=True)
                address = location.address if location else "주소 변환 실패"
            except:
                address = "API 연결 오류"
                
            # --- 가장 가까운 시설물 찾기 ---
            nearest_fac = "없음"
            min_dist = float('inf')
            for fac in facilities:
                dist = math.sqrt((cp["x"] - fac["x"])**2 + (cp["y"] - fac["y"])**2)
                if dist < min_dist:
                    min_dist = dist
                    nearest_fac = fac["name"]
            
            # 리포트에 데이터 추가
            report_data.append({
                "검토 지점명": cp["id"],
                "위치(주소)": address,
                "인접 시설물": nearest_fac,
                "실제 이격거리(mm)": round(d_actual, 1),
                "심도 차이(mm)": round(delta_z_adjusted, 1),
                "판정 결과": status
            })

        # --- 화면 출력: 표 ---
        df_report = pd.DataFrame(report_data)
        st.markdown("### 📋 전체 간섭 검토 상세 리스트")
        st.dataframe(df_report, use_container_width=True)

        # --- 도면 시각화 (Matplotlib) ---
        st.markdown("### 🗺️ 공사 구간 및 배관 간섭 위치도")
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 선 그리기 (예시 좌표)
        ax.plot([0, 300], [0, 300], color='blue', linewidth=3, label='Company Pipe (U/G)')
        ax.plot([0, 300], [200, 0], color='orange', linewidth=3, label='Contractor Pipe', linestyle='--')
        
        # 교차점 및 시설물 마킹
        ax.scatter(100, 100, color='red', s=150, zorder=5, label='Clash Point (P-1)')
        ax.scatter(120, 150, color='green', marker='s', s=100, zorder=5, label='Facility (Manhole)')
        
        ax.legend()
        ax.grid(True, linestyle=':', alpha=0.6)
        st.pyplot(fig)
