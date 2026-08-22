import streamlit as st
import pandas as pd
import io
import math
import matplotlib.pyplot as plt
from geopy.geocoders import Nominatim

st.set_page_config(page_title="사외매설배관 간섭 검토 시스템", layout="wide")
st.title("🚧 지하 매설배관 굴착공사 간섭 검토 프로그램")

st.subheader("👷 [공사업체용] 굴착 공사 정보 입력")

pipe_options = [
    "선택 안함", "1. 스팀 배관", "2. 도시가스 배관", "3. 수도관", 
    "4. 전력케이블 관", "5. 통신관", "6. 오수관", "7. 기타"
]
pipe_type = st.selectbox("공사(매설)할 배관의 종류를 선택해주세요:", pipe_options)

if pipe_type == "7. 기타":
    custom_pipe_type = st.text_input("구체적인 공사 배관/시설물의 종류를 작성해주세요:")

col_od, col_depth = st.columns(2)
with col_od:
    contractor_od = st.number_input("공사 배관 외경 사이즈 기입 (mm)", min_value=0.0, step=1.0)
with col_depth:
    contractor_depth = st.number_input("공사 배관 심도 기입 (관 중심 기준, mm)", min_value=0.0, step=1.0)

st.markdown("---")

st.info("💡 **[필독 주의사항]**\n\nCAD 파일 업로드 시, 공사구간에 대한 정보는 반드시 **[2D 평면 선 + 심도 텍스트 표기]** 형태로 저장된 파일로 업로드 부탁드립니다.")
is_agreed = st.checkbox("네, 위 주의사항을 확인했으며 해당 양식에 맞게 파일을 준비했습니다.")

if is_agreed:
    contractor_file = st.file_uploader("굴착 공사 구간 CAD 파일 업로드 (.dxf)", type=['dxf'], key='contractor')
    
    if contractor_file and st.button("간섭 및 이격거리 분석 실행"):
        if pipe_type == "선택 안함" or contractor_od <= 0 or contractor_depth <= 0:
            st.warning("배관 종류, 외경 사이즈, 심도를 모두 정확히 입력해주세요.")
        else:
            with st.spinner("데이터 분석 및 도면 시각화 생성 중..."):
                final_pipe_name = custom_pipe_type if pipe_type == "7. 기타" else pipe_type
                
                # --- 1. 주변 시설물 더미 데이터 (구체적 명칭으로 수정) ---
                facilities = [
                    {"name": "TB33", "x": 120, "y": 150},
                    {"name": "GM17", "x": 240, "y": 260}
                ]
                
                # --- 2. 교차점 더미 데이터 ---
                clash_points = [
                    {"id": "P-1", "x": 100, "y": 100, "lon": 126.7403398, "lat": 37.31553271, "d_center": 250.0, "company_depth": 1500.0, "r_comp": 108.15}
                ]
                
                report_data = []
                r_cont = contractor_od / 2
                
                geolocator = Nominatim(user_agent="pipe_checker")
                
                for cp in clash_points:
                    d_actual = cp["d_center"] - (cp["r_comp"] + r_cont)
                    delta_z_adjusted = abs((contractor_depth + r_cont) - cp["company_depth"])
                    
                    if d_actual > 300:
                        status = "✅ 간섭없음"
                    elif d_actual <= 300 and delta_z_adjusted >= 300:
                        status = "⚠️ 간섭 (보호테이프 노출)"
                    else:
                        status = "🚨 간섭 (배관 영향 있음)"
                    
                    # --- 3. 주소 포맷 변경 로직 (우편번호 제거 및 OO도 OO시 OO동 형태로 조합) ---
                    try:
                        location = geolocator.reverse((cp["lat"], cp["lon"]), exactly_one=True)
                        if location:
                            addr = location.raw.get('address', {})
                            # 필요한 요소만 추출
                            do = addr.get('province', '')
                            si = addr.get('city', addr.get('town', ''))
                            gu = addr.get('borough', addr.get('county', ''))
                            dong = addr.get('suburb', addr.get('neighbourhood', ''))
                            jibun = addr.get('house_number', addr.get('residential', ''))
                            
                            # 중복 제거 및 조합
                            address_parts = [do, si, gu, dong, jibun]
                            clean_address = " ".join([p for p in address_parts if p])
                            address = clean_address if clean_address else location.address
                        else:
                            address = "주소 변환 실패"
                    except:
                        address = "API 연결 오류"
                        
                    # --- 4. 가장 가까운 시설물 매칭 ---
                    nearest_fac = "없음"
                    min_dist = float('inf')
                    for fac in facilities:
                        dist = math.sqrt((cp["x"] - fac["x"])**2 + (cp["y"] - fac["y"])**2)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_fac = fac["name"]
                    
                    report_data.append({
                        "검토 지점명": cp["id"],
                        "위치(주소)": address,
                        "인접 시설물": nearest_fac,
                        "실제 이격거리(mm)": round(d_actual, 1),
                        "심도 차이(mm)": round(delta_z_adjusted, 1),
                        "판정 결과": status
                    })

                # --- 화면 출력 및 시각화 생략 (이전 코드와 동일하게 유지하시면 됩니다) ---
                df_report = pd.DataFrame(report_data)
                st.success(f"분석이 완료되었습니다. (대상: {final_pipe_name})")
                st.markdown("### 📋 전체 간섭 검토 상세 리스트")
                st.dataframe(df_report, use_container_width=True)

                # 시각화 부분
                st.markdown("### 🗺️ 공사 구간 및 배관 간섭 위치도")
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.plot([0, 300], [0, 300], color='blue', linewidth=3, label='Company Pipe (U/G)')
                ax.plot([0, 300], [200, 0], color='orange', linewidth=3, label='Contractor Pipe', linestyle='--')
                ax.scatter(100, 100, color='red', s=150, zorder=5, label='Clash Point (P-1)')
                
                # 구체적 명칭으로 시각화 마킹
                ax.scatter(120, 150, color='green', marker='s', s=100, zorder=5, label='Facility (TB33)')
                
                ax.legend()
                ax.grid(True, linestyle=':', alpha=0.6)
                st.pyplot(fig)
else:
    st.warning("⚠️ 파일 업로드를 위해 먼저 위 안내사항을 확인하고 체크박스를 선택해주세요.")
